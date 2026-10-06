from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Integer, func, select, type_coerce
from sqlalchemy.orm import Session, joinedload

from app.models import Batch, Medicine, Money


class BatchRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, batch_id: int) -> Batch | None:
        return self.s.get(Batch, batch_id)

    def find(self, medicine_id: int, batch_number: str) -> Batch | None:
        return self.s.scalar(
            select(Batch).where(
                Batch.medicine_id == medicine_id,
                func.upper(Batch.batch_number) == batch_number.strip().upper(),
            )
        )

    def for_medicine(self, medicine_id: int, in_stock_only: bool = False) -> list[Batch]:
        q = select(Batch).where(Batch.medicine_id == medicine_id)
        if in_stock_only:
            q = q.where(Batch.quantity_remaining > 0)
        return list(self.s.scalars(q.order_by(Batch.expiry_date, Batch.id)))

    def fefo_candidates(self, medicine_id: int) -> list[Batch]:
        """Batches with stock, nearest expiry first (First Expiry, First Out)."""
        q = (
            select(Batch)
            .where(Batch.medicine_id == medicine_id, Batch.quantity_remaining > 0)
            .order_by(Batch.expiry_date, Batch.purchase_date, Batch.id)
        )
        return list(self.s.scalars(q))

    def all_with_medicine(self, include_depleted: bool = False) -> list[Batch]:
        q = select(Batch).options(joinedload(Batch.medicine)).join(Medicine)
        if not include_depleted:
            q = q.where(Batch.quantity_remaining > 0)
        return list(self.s.scalars(q.order_by(Medicine.name, Batch.expiry_date)))

    def stock_value(self, today: date, sellable_only: bool = True) -> Decimal:
        """Value of stock on hand at actual purchase cost."""
        raw = func.sum(Batch.quantity_remaining * type_coerce(Batch.purchase_price, Integer))
        q = select(type_coerce(func.coalesce(raw, 0), Money)).where(Batch.quantity_remaining > 0)
        if sellable_only:
            q = q.where(Batch.expiry_date > today)
        return self.s.scalar(q) or Decimal("0.00")

    def retail_value(self, today: date) -> Decimal:
        raw = func.sum(Batch.quantity_remaining * type_coerce(Batch.selling_price, Integer))
        q = select(type_coerce(func.coalesce(raw, 0), Money)).where(
            Batch.quantity_remaining > 0, Batch.expiry_date > today
        )
        return self.s.scalar(q) or Decimal("0.00")
