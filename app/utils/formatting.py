"""Display formatting helpers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

_currency = {"symbol": "Rs."}


def set_currency(symbol: str) -> None:
    _currency["symbol"] = (symbol or "Rs.").strip()


def currency_symbol() -> str:
    return _currency["symbol"]


def money(value, symbol: str | None = None) -> str:
    sym = _currency["symbol"] if symbol is None else symbol
    amount = Decimal(str(value or 0))
    sign = "-" if amount < 0 else ""
    return f"{sign}{sym} {abs(amount):,.2f}".strip()


def money_short(value) -> str:
    """Compact money for dashboard cards, e.g. Rs. 18,500."""
    amount = Decimal(str(value or 0))
    if amount == amount.to_integral_value():
        return f"{_currency['symbol']} {amount:,.0f}"
    return money(amount)


def number(value) -> str:
    return f"{int(value or 0):,}"


def fmt_date(d: date | datetime | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d %b %Y")


def fmt_datetime(d: datetime | None) -> str:
    if d is None:
        return "—"
    return d.strftime("%d %b %Y, %I:%M %p")


def fmt_expiry(d: date | None) -> str:
    return "—" if d is None else d.strftime("%b %Y")
