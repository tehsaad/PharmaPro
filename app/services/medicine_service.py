"""Medicine catalogue: create, edit, search, deactivate."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.database.database import Database
from app.database.repositories import BatchRepository, MedicineRepository, MedicineSummary
from app.models import Batch, Medicine
from app.services.errors import DuplicateCodeError, InUseError, NotFoundError, ValidationError
from app.utils.validators import clean_text, normalize_code, parse_non_negative_int, require_text


@dataclass
class MedicineInput:
    code: str
    name: str
    generic_name: str = ""
    category: str = ""
    manufacturer: str = ""
    dosage: str = ""
    strength: str = ""
    unit: str = "Unit"
    reorder_level: int = 0
    description: str = ""
    barcode: str = ""
    active: bool = True
    extra: dict = field(default_factory=dict)


class MedicineService:
    def __init__(self, db: Database):
        self.db = db

    # ---------------------------------------------------------------- helpers
    def _validated(self, data: MedicineInput) -> dict:
        barcode = clean_text(data.barcode, 64)
        return {
            "code": normalize_code(data.code),
            "barcode": barcode or None,
            "name": require_text(data.name, "Medicine name"),
            "generic_name": clean_text(data.generic_name, 150),
            "category": clean_text(data.category, 80),
            "manufacturer": clean_text(data.manufacturer, 150),
            "dosage": clean_text(data.dosage, 80),
            "strength": clean_text(data.strength, 80),
            "unit": clean_text(data.unit, 40) or "Unit",
            "reorder_level": parse_non_negative_int(data.reorder_level, "Reorder level"),
            "description": clean_text(data.description, 2000),
            "active": bool(data.active),
        }

    # ------------------------------------------------------------------ write
    def create(self, data: MedicineInput) -> Medicine:
        values = self._validated(data)
        try:
            with self.db.session() as s:
                repo = MedicineRepository(s)
                if repo.code_exists(values["code"]):
                    raise DuplicateCodeError("This medicine code already exists. Please choose another code.")
                if values["barcode"] and repo.barcode_exists(values["barcode"]):
                    raise DuplicateCodeError("This barcode is already assigned to another medicine.")
                med = Medicine(**values)
                s.add(med)
                s.flush()
                return med
        except IntegrityError:
            raise DuplicateCodeError("This medicine code already exists. Please choose another code.") from None

    def update(self, medicine_id: int, data: MedicineInput) -> Medicine:
        values = self._validated(data)
        try:
            with self.db.session() as s:
                repo = MedicineRepository(s)
                med = repo.get(medicine_id)
                if med is None:
                    raise NotFoundError("This medicine no longer exists.")
                if repo.code_exists(values["code"], exclude_id=medicine_id):
                    raise DuplicateCodeError("This medicine code already exists. Please choose another code.")
                if values["barcode"] and repo.barcode_exists(values["barcode"], exclude_id=medicine_id):
                    raise DuplicateCodeError("This barcode is already assigned to another medicine.")
                for key, value in values.items():
                    setattr(med, key, value)
                return med
        except IntegrityError:
            raise DuplicateCodeError("This medicine code already exists. Please choose another code.") from None

    def set_active(self, medicine_id: int, active: bool) -> None:
        with self.db.session() as s:
            med = s.get(Medicine, medicine_id)
            if med is None:
                raise NotFoundError("This medicine no longer exists.")
            med.active = active

    def remove(self, medicine_id: int) -> str:
        """Delete a medicine with no history; otherwise deactivate it (RULE 8).

        Returns ``"deleted"`` or ``"deactivated"`` so the UI can tell the user.
        """
        with self.db.session() as s:
            repo = MedicineRepository(s)
            med = repo.get(medicine_id)
            if med is None:
                raise NotFoundError("This medicine no longer exists.")
            if repo.has_history(medicine_id):
                med.active = False
                return "deactivated"
            s.delete(med)
            return "deleted"

    def delete_permanently(self, medicine_id: int) -> None:
        with self.db.session() as s:
            repo = MedicineRepository(s)
            med = repo.get(medicine_id)
            if med is None:
                raise NotFoundError("This medicine no longer exists.")
            if repo.has_history(medicine_id):
                raise InUseError("This medicine cannot be removed because it has transaction history. You can deactivate it instead.")
            s.delete(med)

    # ------------------------------------------------------------------- read
    def get(self, medicine_id: int) -> Medicine:
        with self.db.read() as s:
            med = s.get(Medicine, medicine_id)
            if med is None:
                raise NotFoundError("This medicine no longer exists.")
            return med

    def find_by_code(self, code: str) -> Medicine | None:
        code = (code or "").strip()
        if not code:
            return None
        with self.db.read() as s:
            repo = MedicineRepository(s)
            return repo.get_by_code(code) or repo.get_by_barcode(code)

    def search(self, term: str, limit: int = 25, active_only: bool = True) -> list[Medicine]:
        with self.db.read() as s:
            return MedicineRepository(s).search(term, limit=limit, active_only=active_only)

    def categories(self) -> list[str]:
        with self.db.read() as s:
            return MedicineRepository(s).categories()

    def summaries(self, include_inactive: bool = True, today: date | None = None) -> list[MedicineSummary]:
        with self.db.read() as s:
            return MedicineRepository(s).summaries(today or date.today(), include_inactive=include_inactive)

    def summary(self, medicine_id: int, today: date | None = None) -> MedicineSummary | None:
        with self.db.read() as s:
            rows = MedicineRepository(s).summaries(today or date.today(), medicine_ids=[medicine_id])
            return rows[0] if rows else None

    def batches(self, medicine_id: int, in_stock_only: bool = False) -> list[Batch]:
        with self.db.read() as s:
            return BatchRepository(s).for_medicine(medicine_id, in_stock_only=in_stock_only)

    def update_batch_selling_price(self, batch_id: int, price) -> None:
        """Change the selling price for future sales of a batch. History is unaffected."""
        from app.utils.validators import parse_money

        new_price = parse_money(price, "Selling price")
        with self.db.session() as s:
            batch = s.get(Batch, batch_id)
            if batch is None:
                raise NotFoundError("This batch no longer exists.")
            batch.selling_price = new_price

    def ensure_unique_code(self, code: str, exclude_id: int | None = None) -> None:
        code = normalize_code(code)
        with self.db.read() as s:
            if MedicineRepository(s).code_exists(code, exclude_id):
                raise ValidationError("This medicine code already exists. Please choose another code.")
