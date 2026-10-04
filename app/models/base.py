"""Declarative base and shared column types."""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    """Convert any numeric input to a Decimal rounded to 2 places."""
    if value is None or value == "":
        return ZERO
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


class Money(TypeDecorator):
    """Exact money storage: Decimal in Python, integer minor units (paisa) in SQLite.

    Storing integers avoids floating-point drift in profit and stock-value totals.
    """

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return int((to_money(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return (Decimal(int(value)) / 100).quantize(CENT)


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Base(DeclarativeBase):
    pass
