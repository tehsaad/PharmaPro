"""Input validation helpers that raise friendly :class:`ValidationError` messages."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.base import to_money
from app.services.errors import ValidationError

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_./]*$")


def clean_text(value, max_len: int = 255) -> str:
    text = "" if value is None else str(value).strip()
    return text[:max_len]


def require_text(value, field: str, max_len: int = 150) -> str:
    text = clean_text(value, 10_000)
    if not text:
        raise ValidationError(f"{field} cannot be empty.")
    if len(text) > max_len:
        raise ValidationError(f"{field} is too long (maximum {max_len} characters).")
    return text


def normalize_code(value) -> str:
    code = clean_text(value, 100).upper()
    if not code:
        raise ValidationError("Medicine code cannot be empty.")
    if len(code) > 40:
        raise ValidationError("Medicine code is too long (maximum 40 characters).")
    if not CODE_RE.match(code):
        raise ValidationError("Medicine code may contain only letters, numbers and - _ . /")
    return code


def parse_money(value, field: str, allow_zero: bool = True) -> Decimal:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip() or "0"
        amount = to_money(value)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field} must be a number.") from None
    if amount < 0:
        raise ValidationError(f"{field} cannot be negative.")
    if not allow_zero and amount == 0:
        raise ValidationError(f"{field} must be greater than zero.")
    if amount > Decimal("100000000"):
        raise ValidationError(f"{field} is unrealistically large. Please check it.")
    return amount


def parse_quantity(value, field: str = "Quantity") -> int:
    try:
        if isinstance(value, str):
            value = value.strip()
        qty_dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field} must be a whole number.") from None
    if qty_dec != qty_dec.to_integral_value():
        raise ValidationError(f"{field} must be a whole number.")
    qty = int(qty_dec)
    if qty <= 0:
        raise ValidationError(f"{field} must be greater than zero.")
    if qty > 10_000_000:
        raise ValidationError(f"{field} is unrealistically large. Please check it.")
    return qty


def parse_non_negative_int(value, field: str) -> int:
    try:
        n = int(str(value).strip() or "0")
    except (ValueError, TypeError):
        raise ValidationError(f"{field} must be a whole number.") from None
    if n < 0:
        raise ValidationError(f"{field} cannot be negative.")
    return n


def parse_date(value, field: str = "Date") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Month-only expiry such as 2028-05 -> last day of that month.
    for fmt in ("%Y-%m", "%m/%Y", "%m-%Y"):
        try:
            d = datetime.strptime(text, fmt).date()
            return last_day_of_month(d)
        except ValueError:
            continue
    raise ValidationError(f"{field} is not a valid date. Use the format YYYY-MM-DD.")


def last_day_of_month(d: date) -> date:
    nxt = date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)
