from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)

    purchase = relationship("Purchase", back_populates="items")
    medicine = relationship("Medicine")
    batch = relationship("Batch")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_item_qty"),
        Index("ix_purchase_items_purchase", "purchase_id"),
        Index("ix_purchase_items_medicine", "medicine_id"),
    )
