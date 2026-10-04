from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    dosage: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    strength: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="Unit", nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    batches = relationship("Batch", back_populates="medicine", order_by="Batch.expiry_date")

    __table_args__ = (
        Index("ix_medicines_name", "name"),
        Index("ix_medicines_generic", "generic_name"),
        Index("ix_medicines_category", "category"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Medicine {self.code} {self.name}>"
