from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, now


class Batch(Base):
    """A specific lot of a medicine with its own cost, price and expiry.

    Each batch keeps the purchase price it was actually bought at, so profit
    on any sale is always computed from the true cost of the units sold.
    """

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(60), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    supplier: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    medicine = relationship("Medicine", back_populates="batches")

    __table_args__ = (
        # RULE 1: stock can never become negative - enforced by the database itself.
        CheckConstraint("quantity_remaining >= 0", name="ck_batch_remaining_non_negative"),
        CheckConstraint("quantity_remaining <= quantity_received", name="ck_batch_remaining_le_received"),
        CheckConstraint("quantity_received > 0", name="ck_batch_received_positive"),
        CheckConstraint("purchase_price >= 0", name="ck_batch_purchase_price"),
        CheckConstraint("selling_price >= 0", name="ck_batch_selling_price"),
        UniqueConstraint("medicine_id", "batch_number", name="uq_batch_medicine_number"),
        Index("ix_batches_medicine_expiry", "medicine_id", "expiry_date"),
        Index("ix_batches_expiry", "expiry_date"),
    )

    def is_expired(self, on: date) -> bool:
        """A batch is treated as expired on and after its expiry date."""
        return self.expiry_date <= on
