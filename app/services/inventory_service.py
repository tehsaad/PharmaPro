"""Stock levels, statuses and expiry monitoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.database.database import Database
from app.database.repositories import BatchRepository, MedicineRepository, MedicineSummary
from app.services.settings_service import SettingsService
from app.utils.constants import (
    STATUS_EXPIRED,
    STATUS_EXPIRING,
    STATUS_INACTIVE,
    STATUS_LOW,
    STATUS_NORMAL,
    STATUS_OUT,
)

FILTER_ALL = "All"
FILTER_LOW = STATUS_LOW
FILTER_OUT = STATUS_OUT
FILTER_EXPIRING = STATUS_EXPIRING
FILTER_EXPIRED = STATUS_EXPIRED
STOCK_FILTERS = [FILTER_ALL, FILTER_LOW, FILTER_OUT, FILTER_EXPIRING, FILTER_EXPIRED]


@dataclass
class StockRow:
    batch_id: int | None
    medicine_id: int
    code: str
    medicine: str
    category: str
    batch_number: str
    quantity_remaining: int
    quantity_received: int
    purchase_price: Decimal | None
    selling_price: Decimal | None
    expiry_date: date | None
    supplier: str
    stock_value: Decimal
    status: str
    days_to_expiry: int | None


class InventoryService:
    def __init__(self, db: Database, settings: SettingsService):
        self.db = db
        self.settings = settings

    # ---------------------------------------------------------- thresholds
    def reorder_point(self, reorder_level: int) -> int:
        return reorder_level if reorder_level > 0 else self.settings.low_stock_threshold

    def is_low(self, summary: MedicineSummary) -> bool:
        return 0 < summary.sellable_stock <= self.reorder_point(summary.reorder_level)

    def medicine_status(self, m: MedicineSummary, today: date | None = None) -> str:
        today = today or date.today()
        if not m.active:
            return STATUS_INACTIVE
        if m.sellable_stock <= 0:
            return STATUS_EXPIRED if m.expired_stock > 0 else STATUS_OUT
        if m.nearest_expiry and (m.nearest_expiry - today).days <= self.settings.expiry_warning_days:
            return STATUS_EXPIRING
        if self.is_low(m):
            return STATUS_LOW
        return STATUS_NORMAL

    # ------------------------------------------------------------- batches
    def stock_rows(self, status_filter: str = FILTER_ALL, today: date | None = None) -> list[StockRow]:
        """Batch-level inventory, optionally filtered by status.

        "Out of Stock" is a medicine-level condition, so that filter (and the
        "All" view) also lists active medicines that have no sellable stock left.
        """
        today = today or date.today()
        warn = self.settings.expiry_warning_days
        with self.db.read() as s:
            summaries = {m.id: m for m in MedicineRepository(s).summaries(today, include_inactive=False)}
            batches = [] if status_filter == FILTER_OUT else BatchRepository(s).all_with_medicine()

        rows: list[StockRow] = []
        for b in batches:
            m = summaries.get(b.medicine_id)
            if m is None:  # inactive medicine
                continue
            days = (b.expiry_date - today).days
            if b.expiry_date <= today:
                status = STATUS_EXPIRED
            elif days <= warn:
                status = STATUS_EXPIRING
            elif self.is_low(m):
                status = STATUS_LOW
            else:
                status = STATUS_NORMAL
            if status_filter != FILTER_ALL and status != status_filter:
                continue
            rows.append(
                StockRow(
                    batch_id=b.id, medicine_id=b.medicine_id, code=m.code, medicine=m.name, category=m.category,
                    batch_number=b.batch_number, quantity_remaining=b.quantity_remaining,
                    quantity_received=b.quantity_received, purchase_price=b.purchase_price,
                    selling_price=b.selling_price, expiry_date=b.expiry_date, supplier=b.supplier,
                    stock_value=(b.purchase_price * b.quantity_remaining).quantize(Decimal("0.01")),
                    status=status, days_to_expiry=days,
                )
            )
        if status_filter in (FILTER_ALL, FILTER_OUT):
            for m in summaries.values():
                if m.sellable_stock == 0 and (status_filter == FILTER_OUT or m.total_stock == 0):
                    rows.append(
                        StockRow(
                            batch_id=None, medicine_id=m.id, code=m.code, medicine=m.name, category=m.category,
                            batch_number="—", quantity_remaining=0, quantity_received=0, purchase_price=None,
                            selling_price=m.selling_price, expiry_date=None, supplier="",
                            stock_value=Decimal("0.00"), status=STATUS_OUT, days_to_expiry=None,
                        )
                    )
        return rows

    # ----------------------------------------------------------- dashboards
    def low_stock(self, today: date | None = None) -> list[MedicineSummary]:
        """Active medicines at or below their reorder point (including zero)."""
        today = today or date.today()
        with self.db.read() as s:
            meds = MedicineRepository(s).summaries(today, include_inactive=False)
        return sorted(
            (m for m in meds if m.sellable_stock <= self.reorder_point(m.reorder_level)),
            key=lambda m: (m.sellable_stock, m.name),
        )

    def expiring_batches(self, within_days: int, today: date | None = None) -> list[StockRow]:
        today = today or date.today()
        limit = today + timedelta(days=within_days)
        return [
            r for r in self.stock_rows(FILTER_ALL, today)
            if r.batch_id and r.quantity_remaining > 0 and r.expiry_date and today < r.expiry_date <= limit
        ]

    def expired_batches(self, today: date | None = None) -> list[StockRow]:
        return [r for r in self.stock_rows(FILTER_EXPIRED, today) if r.quantity_remaining > 0]

    def expiry_buckets(self, today: date | None = None) -> dict[str, int]:
        today = today or date.today()
        rows = [r for r in self.stock_rows(FILTER_ALL, today) if r.batch_id and r.quantity_remaining > 0]
        out = {"expired": 0, "30": 0, "60": 0, "90": 0}
        for r in rows:
            d = r.days_to_expiry
            if d is None:
                continue
            if d <= 0:
                out["expired"] += 1
            if 0 < d <= 30:
                out["30"] += 1
            if 0 < d <= 60:
                out["60"] += 1
            if 0 < d <= 90:
                out["90"] += 1
        return out

    def stock_value(self, today: date | None = None) -> Decimal:
        with self.db.read() as s:
            return BatchRepository(s).stock_value(today or date.today())

    def retail_value(self, today: date | None = None) -> Decimal:
        with self.db.read() as s:
            return BatchRepository(s).retail_value(today or date.today())

    def expired_value(self, today: date | None = None) -> Decimal:
        today = today or date.today()
        with self.db.read() as s:
            repo = BatchRepository(s)
            return repo.stock_value(today, sellable_only=False) - repo.stock_value(today)
