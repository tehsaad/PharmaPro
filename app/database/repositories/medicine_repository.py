"""Query helpers for medicines. All queries are parameterised by SQLAlchemy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Batch, Medicine, PurchaseItem, SaleItem


@dataclass
class MedicineSummary:
    id: int
    code: str
    barcode: str
    name: str
    generic_name: str
    category: str
    manufacturer: str
    dosage: str
    strength: str
    unit: str
    reorder_level: int
    active: bool
    total_stock: int
    sellable_stock: int
    expired_stock: int
    nearest_expiry: date | None
    selling_price: Decimal | None


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class MedicineRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, medicine_id: int) -> Medicine | None:
        return self.s.get(Medicine, medicine_id)

    def get_by_code(self, code: str) -> Medicine | None:
        return self.s.scalar(select(Medicine).where(func.upper(Medicine.code) == code.strip().upper()))

    def get_by_barcode(self, barcode: str) -> Medicine | None:
        return self.s.scalar(select(Medicine).where(Medicine.barcode == barcode.strip()))

    def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        q = select(Medicine.id).where(func.upper(Medicine.code) == code.upper())
        if exclude_id:
            q = q.where(Medicine.id != exclude_id)
        return self.s.scalar(q) is not None

    def barcode_exists(self, barcode: str, exclude_id: int | None = None) -> bool:
        q = select(Medicine.id).where(Medicine.barcode == barcode)
        if exclude_id:
            q = q.where(Medicine.id != exclude_id)
        return self.s.scalar(q) is not None

    def search(self, term: str, limit: int = 25, active_only: bool = True) -> list[Medicine]:
        term = (term or "").strip()
        q = select(Medicine)
        if active_only:
            q = q.where(Medicine.active.is_(True))
        if term:
            pattern = _like(term)
            q = q.where(
                or_(
                    Medicine.code.ilike(pattern, escape="\\"),
                    Medicine.name.ilike(pattern, escape="\\"),
                    Medicine.generic_name.ilike(pattern, escape="\\"),
                    Medicine.manufacturer.ilike(pattern, escape="\\"),
                    Medicine.barcode == term,
                )
            )
            upper = term.upper()
            rank = case(
                (func.upper(Medicine.code) == upper, 0),
                (Medicine.barcode == term, 0),
                (func.upper(Medicine.code).like(_like(upper)[1:], escape="\\"), 1),
                (Medicine.name.ilike(_like(term)[1:], escape="\\"), 2),
                else_=3,
            )
            q = q.order_by(rank, Medicine.name)
        else:
            q = q.order_by(Medicine.name)
        return list(self.s.scalars(q.limit(limit)))

    def categories(self) -> list[str]:
        rows = self.s.scalars(select(Medicine.category).where(Medicine.category != "").distinct().order_by(Medicine.category))
        return list(rows)

    def has_history(self, medicine_id: int) -> bool:
        for model in (SaleItem, PurchaseItem, Batch):
            if self.s.scalar(select(model.id).where(model.medicine_id == medicine_id).limit(1)) is not None:
                return True
        return False

    def summaries(self, today: date, include_inactive: bool = True, medicine_ids: list[int] | None = None) -> list[MedicineSummary]:
        """One row per medicine with aggregated stock - a single query."""
        not_expired = Batch.expiry_date > today
        agg = (
            select(
                Batch.medicine_id.label("mid"),
                func.coalesce(func.sum(Batch.quantity_remaining), 0).label("total"),
                func.coalesce(func.sum(case((not_expired, Batch.quantity_remaining), else_=0)), 0).label("sellable"),
                func.coalesce(func.sum(case((not_expired, 0), else_=Batch.quantity_remaining)), 0).label("expired"),
                func.min(case((and_(not_expired, Batch.quantity_remaining > 0), Batch.expiry_date))).label("nearest"),
            )
            .group_by(Batch.medicine_id)
            .subquery()
        )
        next_price = (
            select(Batch.selling_price)
            .where(Batch.medicine_id == Medicine.id, Batch.quantity_remaining > 0, not_expired)
            .order_by(Batch.expiry_date, Batch.id)
            .limit(1)
            .correlate(Medicine)
            .scalar_subquery()
        )
        last_price = (
            select(Batch.selling_price)
            .where(Batch.medicine_id == Medicine.id)
            .order_by(Batch.id.desc())
            .limit(1)
            .correlate(Medicine)
            .scalar_subquery()
        )
        q = (
            select(
                Medicine,
                func.coalesce(agg.c.total, 0),
                func.coalesce(agg.c.sellable, 0),
                func.coalesce(agg.c.expired, 0),
                agg.c.nearest,
                func.coalesce(next_price, last_price),
            )
            .outerjoin(agg, agg.c.mid == Medicine.id)
            .order_by(Medicine.name)
        )
        if not include_inactive:
            q = q.where(Medicine.active.is_(True))
        if medicine_ids is not None:
            q = q.where(Medicine.id.in_(medicine_ids))
        out: list[MedicineSummary] = []
        for med, total, sellable, expired, nearest, price in self.s.execute(q):
            if isinstance(nearest, str):  # SQLite returns MIN(date) as text
                nearest = date.fromisoformat(nearest)
            if price is not None and not isinstance(price, Decimal):
                price = (Decimal(int(price)) / 100).quantize(Decimal("0.01"))
            out.append(
                MedicineSummary(
                    id=med.id, code=med.code, barcode=med.barcode or "", name=med.name,
                    generic_name=med.generic_name, category=med.category, manufacturer=med.manufacturer,
                    dosage=med.dosage, strength=med.strength, unit=med.unit,
                    reorder_level=med.reorder_level, active=med.active,
                    total_stock=int(total), sellable_stock=int(sellable), expired_stock=int(expired),
                    nearest_expiry=nearest, selling_price=price,
                )
            )
        return out
