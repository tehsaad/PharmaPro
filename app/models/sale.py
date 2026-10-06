from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, now


class Sale(Base):
    """A completed sale. All amounts are frozen at the moment of sale."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    sale_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_of_goods: Mapped[Decimal] = mapped_column(Money, nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount_received: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    print_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.id")

    __table_args__ = (
        CheckConstraint("discount >= 0", name="ck_sale_discount"),
        CheckConstraint("total >= 0", name="ck_sale_total"),
        Index("ix_sales_date", "sale_date"),
    )
