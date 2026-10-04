"""Add Stock: record a supplier purchase with many medicines in one transaction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.database.database import Database
from app.database.repositories import BatchRepository, MedicineRepository, PurchaseRepository
from app.models import Batch, Purchase, PurchaseItem
from app.services.errors import NotFoundError, ValidationError
from app.utils.validators import clean_text, parse_date, parse_money, parse_quantity, require_text


@dataclass
class StockLine:
    medicine_id: int
    batch_number: str
    expiry_date: date | str
    quantity: int | str
    purchase_price: Decimal | str | float
    selling_price: Decimal | str | float


@dataclass
class PurchaseResult:
    purchase_id: int
    total_amount: Decimal
    line_count: int
    units: int


class PurchaseService:
    def __init__(self, db: Database):
        self.db = db

    def validate_lines(self, lines: list[StockLine], purchase_date: date) -> list[dict]:
        if not lines:
            raise ValidationError("Please add at least one medicine before saving the stock.")
        cleaned: list[dict] = []
        seen: set[tuple[int, str]] = set()
        for n, line in enumerate(lines, start=1):
            where = f"Row {n}: "
            try:
                batch_no = require_text(line.batch_number, "Batch number", 60).upper()
                expiry = parse_date(line.expiry_date, "Expiry date")
                qty = parse_quantity(line.quantity)
                cost = parse_money(line.purchase_price, "Purchase price")
                price = parse_money(line.selling_price, "Selling price")
            except ValidationError as exc:
                raise ValidationError(where + str(exc)) from None
            if expiry <= purchase_date:
                raise ValidationError(where + "Expiry date must be after the purchase date. Expired stock cannot be added.")
            key = (line.medicine_id, batch_no)
            if key in seen:
                raise ValidationError(where + f"Batch {batch_no} appears twice for the same medicine. Combine them into one row.")
            seen.add(key)
            cleaned.append(
                {"medicine_id": line.medicine_id, "batch_number": batch_no, "expiry_date": expiry,
                 "quantity": qty, "purchase_price": cost, "selling_price": price}
            )
        return cleaned

    @staticmethod
    def below_cost_rows(lines: list[StockLine]) -> list[int]:
        """Row numbers (1-based) where the selling price is below cost - used for a warning."""
        out = []
        for n, line in enumerate(lines, start=1):
            try:
                if parse_money(line.selling_price, "x") < parse_money(line.purchase_price, "x"):
                    out.append(n)
            except ValidationError:
                continue
        return out

    def add_stock(self, supplier: str, invoice_number: str, purchase_date: date | str,
                  lines: list[StockLine], notes: str = "") -> PurchaseResult:
        """Atomically create the purchase, its items and the batches.

        If anything fails, nothing is saved (the session rolls back).
        """
        supplier = require_text(supplier, "Supplier")
        invoice = clean_text(invoice_number, 80)
        pdate = parse_date(purchase_date, "Purchase date")
        if pdate > date.today():
            raise ValidationError("Purchase date cannot be in the future.")
        cleaned = self.validate_lines(lines, pdate)

        with self.db.session() as s:
            meds = MedicineRepository(s)
            batches = BatchRepository(s)
            purchase = Purchase(supplier=supplier, invoice_number=invoice, purchase_date=pdate,
                                total_amount=Decimal("0"), notes=clean_text(notes, 1000))
            s.add(purchase)
            total = Decimal("0.00")
            units = 0
            for n, line in enumerate(cleaned, start=1):
                med = meds.get(line["medicine_id"])
                if med is None:
                    raise NotFoundError(f"Row {n}: this medicine no longer exists.")
                if not med.active:
                    raise ValidationError(f"Row {n}: {med.name} is deactivated. Re-activate it before adding stock.")
                batch = batches.find(med.id, line["batch_number"])
                if batch is None:
                    batch = Batch(
                        medicine_id=med.id, batch_number=line["batch_number"], purchase_date=pdate,
                        expiry_date=line["expiry_date"], quantity_received=line["quantity"],
                        quantity_remaining=line["quantity"], purchase_price=line["purchase_price"],
                        selling_price=line["selling_price"], supplier=supplier,
                    )
                    s.add(batch)
                    s.flush()
                else:
                    # Re-stocking an existing batch is only safe when it is truly the same lot:
                    # same expiry and same cost, so the batch's cost stays accurate (RULE 5).
                    if batch.expiry_date != line["expiry_date"]:
                        raise ValidationError(
                            f"Row {n}: batch {batch.batch_number} of {med.name} already exists with expiry "
                            f"{batch.expiry_date:%d-%m-%Y}. Please check the batch number or expiry date."
                        )
                    if batch.purchase_price != line["purchase_price"]:
                        raise ValidationError(
                            f"Row {n}: batch {batch.batch_number} of {med.name} was bought earlier at a different "
                            "purchase price. Please enter it with a different batch number so both costs are kept."
                        )
                    batch.quantity_received += line["quantity"]
                    batch.quantity_remaining += line["quantity"]
                    batch.selling_price = line["selling_price"]
                line_total = (line["purchase_price"] * line["quantity"]).quantize(Decimal("0.01"))
                purchase.items.append(
                    PurchaseItem(
                        medicine_id=med.id, batch_id=batch.id, quantity=line["quantity"],
                        purchase_price=line["purchase_price"], selling_price=line["selling_price"], total=line_total,
                    )
                )
                total += line_total
                units += line["quantity"]
            purchase.total_amount = total
            s.flush()
            return PurchaseResult(purchase.id, total, len(cleaned), units)

    def list(self, start: date, end: date, search: str = "") -> list[Purchase]:
        with self.db.read() as s:
            return PurchaseRepository(s).list_between(start, end, search)

    def get(self, purchase_id: int) -> Purchase:
        with self.db.read() as s:
            p = PurchaseRepository(s).get(purchase_id)
            if p is None:
                raise NotFoundError("This purchase record no longer exists.")
            return p

    def suppliers(self) -> list[str]:
        with self.db.read() as s:
            return PurchaseRepository(s).suppliers()
