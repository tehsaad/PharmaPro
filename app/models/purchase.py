from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, now


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier: Mapped[str] = mapped_column(String(150), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_purchases_date", "purchase_date"),)
