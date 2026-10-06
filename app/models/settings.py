from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now


class Setting(Base):
    """Simple key/value store for pharmacy, receipt and inventory settings."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)


class HeldSale(Base):
    """A cart parked with *Hold Sale* so another customer can be served first."""

    __tablename__ = "held_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON cart lines
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
