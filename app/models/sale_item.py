from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money


class SaleItem(Base):
    """One batch-specific line of a sale.

    ``cost_price`` and ``selling_price`` are copied from the batch at the moment
    of sale, so later price changes never alter historical profit (RULES 9-11).
    """

    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    profit: Mapped[Decimal] = mapped_column(Money, nullable=False)

    sale = relationship("Sale", back_populates="items")
    medicine = relationship("Medicine")
    batch = relationship("Batch")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_item_qty"),
        Index("ix_sale_items_sale", "sale_id"),
        Index("ix_sale_items_medicine", "medicine_id"),
    )
