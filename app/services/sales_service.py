"""Point of sale: FEFO batch allocation, stock deduction, profit and receipts.

Business rules enforced here:

* Stock never goes negative (also enforced by a DB CHECK constraint).
* Expired batches are never sold.
* Batches are consumed First-Expiry-First-Out unless a specific batch is chosen.
* Each sale line records the batch, its actual cost and the price charged, so
  historical revenue and profit never change when prices change later.
* The whole sale is one database transaction - all or nothing.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import Database
from app.database.repositories import BatchRepository, MedicineRepository, SaleRepository
from app.models import Batch, HeldSale, Medicine, Sale, SaleItem
from app.models.base import now, to_money
from app.services.errors import ExpiredStockError, InsufficientStockError, NotFoundError, ValidationError
from app.utils.validators import parse_money, parse_quantity

TWO = Decimal("0.01")


@dataclass
class CartLine:
    medicine_id: int
    quantity: int
    batch_id: int | None = None  # None = automatic FEFO


@dataclass
class Allocation:
    batch_id: int
    batch_number: str
    expiry_date: date
    quantity: int
    selling_price: Decimal
    cost_price: Decimal

    @property
    def total(self) -> Decimal:
        return (self.selling_price * self.quantity).quantize(TWO)

    @property
    def cost_total(self) -> Decimal:
        return (self.cost_price * self.quantity).quantize(TWO)


@dataclass
class LinePreview:
    medicine_id: int
    code: str
    name: str
    unit: str
    quantity: int
    allocations: list[Allocation] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((a.total for a in self.allocations), Decimal("0.00"))

    @property
    def unit_price(self) -> Decimal:
        return (self.total / self.quantity).quantize(TWO) if self.quantity else Decimal("0.00")

    @property
    def mixed_prices(self) -> bool:
        return len({a.selling_price for a in self.allocations}) > 1

    @property
    def batch_label(self) -> str:
        return ", ".join(a.batch_number for a in self.allocations)


@dataclass
class SaleResult:
    sale_id: int
    receipt_number: str
    total: Decimal
    gross_profit: Decimal


def _allocate(session: Session, medicine: Medicine, quantity: int, on: date,
              batch_id: int | None, reserved: dict[int, int]) -> list[Allocation]:
    """Pick batches for ``quantity`` units without touching the database.

    ``reserved`` holds units already promised to earlier lines of the same cart,
    so two lines of the same medicine cannot both claim the same units.
    """
    if not medicine.active:
        raise ValidationError(f"{medicine.name} is deactivated and cannot be sold.")

    def free(b: Batch) -> int:
        return b.quantity_remaining - reserved.get(b.id, 0)

    if batch_id is not None:
        batch = session.get(Batch, batch_id)
        if batch is None or batch.medicine_id != medicine.id:
            raise NotFoundError(f"The selected batch of {medicine.name} no longer exists.")
        if batch.is_expired(on):
            raise ExpiredStockError(
                f"Batch {batch.batch_number} of {medicine.name} expired on {batch.expiry_date:%d %b %Y}.\n\n"
                "Expired medicine cannot be sold. Please remove it from the shelf."
            )
        if free(batch) < quantity:
            raise InsufficientStockError(
                f"Insufficient stock.\n\nBatch {batch.batch_number} of {medicine.name} has only "
                f"{max(free(batch), 0)} {medicine.unit.lower()}(s) available."
            )
        return [Allocation(batch.id, batch.batch_number, batch.expiry_date, quantity, batch.selling_price, batch.purchase_price)]

    candidates = BatchRepository(session).fefo_candidates(medicine.id)
    # Only batches already received on the sale date (matters for back-dated entries).
    valid = [b for b in candidates if not b.is_expired(on) and b.purchase_date <= on and free(b) > 0]
    expired_units = sum(b.quantity_remaining for b in candidates if b.is_expired(on))
    available = sum(free(b) for b in valid)

    if available < quantity:
        if available == 0 and expired_units > 0:
            raise ExpiredStockError(
                f"All remaining stock of {medicine.name} ({expired_units} units) has expired.\n\n"
                "Expired medicine cannot be sold."
            )
        msg = f"Insufficient stock.\n\nOnly {available} {medicine.unit.lower()}(s) of {medicine.name} available"
        if expired_units:
            msg += f" ({expired_units} more are expired and cannot be sold)"
        raise InsufficientStockError(msg + ".")

    out: list[Allocation] = []
    need = quantity
    for b in valid:  # nearest expiry first
        take = min(need, free(b))
        out.append(Allocation(b.id, b.batch_number, b.expiry_date, take, b.selling_price, b.purchase_price))
        need -= take
        if need == 0:
            break
    return out


class SalesService:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------- preview
    def preview(self, lines: list[CartLine], on: date | None = None) -> list[LinePreview]:
        """Price and allocate a whole cart. Raises friendly errors if not sellable."""
        on = on or date.today()
        out: list[LinePreview] = []
        with self.db.read() as s:
            reserved: dict[int, int] = {}
            for line in lines:
                med = s.get(Medicine, line.medicine_id)
                if med is None:
                    raise NotFoundError("A medicine in this sale no longer exists.")
                qty = parse_quantity(line.quantity)
                allocs = _allocate(s, med, qty, on, line.batch_id, reserved)
                for a in allocs:
                    reserved[a.batch_id] = reserved.get(a.batch_id, 0) + a.quantity
                out.append(LinePreview(med.id, med.code, med.name, med.unit, qty, allocs))
        return out

    def available_quantity(self, medicine_id: int, on: date | None = None) -> int:
        on = on or date.today()
        with self.db.read() as s:
            return sum(b.quantity_remaining for b in BatchRepository(s).fefo_candidates(medicine_id) if not b.is_expired(on))

    def sellable_batches(self, medicine_id: int) -> list[Batch]:
        with self.db.read() as s:
            return BatchRepository(s).fefo_candidates(medicine_id)

    # -------------------------------------------------------------- commit
    def complete_sale(self, lines: list[CartLine], discount=0, sale_date: datetime | None = None,
                      amount_received=None) -> SaleResult:
        if not lines:
            raise ValidationError("The sale is empty. Add at least one medicine.")
        discount = parse_money(discount, "Discount")
        received = None if amount_received in (None, "") else parse_money(amount_received, "Amount received")
        when = (sale_date or now()).replace(microsecond=0)
        on = when.date()

        for attempt in range(3):
            try:
                return self._commit_sale(lines, discount, when, on, received)
            except IntegrityError as exc:
                # Only a receipt-number race can cause this; retry with the next number.
                if "receipt_number" not in str(exc.orig) or attempt == 2:
                    raise
        raise RuntimeError("unreachable")

    def _commit_sale(self, lines, discount, when, on, received) -> SaleResult:
        with self.db.session() as s:  # BEGIN IMMEDIATE: holds the write lock for the whole sale
            reserved: dict[int, int] = {}
            sale = Sale(sale_date=when, subtotal=Decimal("0"), discount=discount, total=Decimal("0"),
                        cost_of_goods=Decimal("0"), gross_profit=Decimal("0"), amount_received=received,
                        receipt_number=self._next_receipt_number(s, on))
            subtotal = Decimal("0.00")
            cogs = Decimal("0.00")
            for line in lines:
                med = s.get(Medicine, line.medicine_id)
                if med is None:
                    raise NotFoundError("A medicine in this sale no longer exists.")
                qty = parse_quantity(line.quantity)
                for a in _allocate(s, med, qty, on, line.batch_id, reserved):
                    reserved[a.batch_id] = reserved.get(a.batch_id, 0) + a.quantity
                    sale.items.append(
                        SaleItem(medicine_id=med.id, batch_id=a.batch_id, quantity=a.quantity,
                                 selling_price=a.selling_price, cost_price=a.cost_price, total=a.total,
                                 cost_total=a.cost_total, profit=a.total - a.cost_total)
                    )
                    subtotal += a.total
                    cogs += a.cost_total
            if discount > subtotal:
                raise ValidationError("Discount cannot be more than the subtotal.")
            total = subtotal - discount
            if received is not None and received < total:
                raise ValidationError("Amount received is less than the total due.")
            sale.subtotal, sale.total, sale.cost_of_goods = subtotal, total, cogs
            sale.gross_profit = total - cogs  # discount reduces profit
            s.add(sale)

            # Deduct stock last, after every line has been validated.
            for batch_id, qty in reserved.items():
                batch = s.get(Batch, batch_id)
                if batch.quantity_remaining < qty:  # defensive; cannot happen under the write lock
                    raise InsufficientStockError("Insufficient stock. Stock changed while completing the sale.")
                batch.quantity_remaining -= qty
            s.flush()
            return SaleResult(sale.id, sale.receipt_number, total, sale.gross_profit)

    @staticmethod
    def _next_receipt_number(s: Session, on: date) -> str:
        prefix = f"RX-{on:%Y%m%d}-"
        last = SaleRepository(s).last_receipt_for_prefix(prefix)
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:04d}"

    # -------------------------------------------------------------- history
    def get(self, sale_id: int) -> Sale:
        with self.db.read() as s:
            sale = SaleRepository(s).get(sale_id)
            if sale is None:
                raise NotFoundError("This sale record no longer exists.")
            return sale

    def find_receipt(self, receipt_number: str) -> Sale | None:
        with self.db.read() as s:
            return SaleRepository(s).get_by_receipt(receipt_number)

    def list(self, start: date, end: date, search: str = "", limit: int | None = None) -> list[Sale]:
        with self.db.read() as s:
            return SaleRepository(s).list_between(start, end, search, limit)

    def last_sale(self) -> Sale | None:
        with self.db.read() as s:
            sid = s.scalar(select(Sale.id).order_by(Sale.id.desc()).limit(1))
            return SaleRepository(s).get(sid) if sid else None

    def mark_printed(self, sale_id: int) -> int:
        with self.db.session() as s:
            sale = s.get(Sale, sale_id)
            if sale is None:
                raise NotFoundError("This sale record no longer exists.")
            sale.print_count += 1
            return sale.print_count

    # ------------------------------------------------------------ held sales
    def hold(self, lines: list[CartLine], discount=0, label: str = "") -> int:
        if not lines:
            raise ValidationError("There is nothing to hold.")
        payload = json.dumps({"lines": [asdict(line) for line in lines], "discount": str(to_money(discount))})
        with self.db.session() as s:
            held = HeldSale(label=label[:120], payload=payload)
            s.add(held)
            s.flush()
            return held.id

    def held_sales(self) -> list[HeldSale]:
        with self.db.read() as s:
            return list(s.scalars(select(HeldSale).order_by(HeldSale.created_at)))

    def resume(self, held_id: int) -> tuple[list[CartLine], Decimal]:
        with self.db.session() as s:
            held = s.get(HeldSale, held_id)
            if held is None:
                raise NotFoundError("This held sale no longer exists.")
            data = json.loads(held.payload)
            s.delete(held)
        lines = [CartLine(**line) for line in data.get("lines", [])]
        return lines, to_money(data.get("discount", "0"))

    def discard_held(self, held_id: int) -> None:
        with self.db.session() as s:
            held = s.get(HeldSale, held_id)
            if held is not None:
                s.delete(held)

    def lookup(self, text: str) -> Medicine | None:
        """Exact code / barcode match, used by the scanner field."""
        text = (text or "").strip()
        if not text:
            return None
        with self.db.read() as s:
            repo = MedicineRepository(s)
            med = repo.get_by_code(text) or repo.get_by_barcode(text)
            return med if med and med.active else None
