from __future__ import annotations

from sqlalchemy import select

from app.database.database import Database
from app.models import Setting
from app.services.errors import ValidationError
from app.utils.constants import DEFAULT_SETTINGS, PAPER_SIZES
from app.utils.formatting import set_currency


class SettingsService:
    def __init__(self, db: Database):
        self.db = db
        self._cache: dict[str, str] | None = None

    def all(self) -> dict[str, str]:
        if self._cache is None:
            values = dict(DEFAULT_SETTINGS)
            with self.db.read() as s:
                for row in s.scalars(select(Setting)):
                    values[row.key] = row.value
            self._cache = values
            set_currency(values.get("currency_symbol", "Rs."))
        return dict(self._cache)

    def get(self, key: str, default: str = "") -> str:
        return self.all().get(key, DEFAULT_SETTINGS.get(key, default))

    def get_int(self, key: str) -> int:
        try:
            return int(self.get(key))
        except ValueError:
            return int(DEFAULT_SETTINGS.get(key, "0"))

    def get_bool(self, key: str) -> bool:
        return self.get(key) in ("1", "true", "True", "yes")

    @property
    def low_stock_threshold(self) -> int:
        return max(0, self.get_int("low_stock_threshold"))

    @property
    def expiry_warning_days(self) -> int:
        return max(1, self.get_int("expiry_warning_days"))

    def update(self, values: dict[str, str]) -> None:
        cleaned = {k: ("" if v is None else str(v).strip()) for k, v in values.items() if k in DEFAULT_SETTINGS}
        if "pharmacy_name" in cleaned and not cleaned["pharmacy_name"]:
            raise ValidationError("Pharmacy name cannot be empty.")
        for key in ("low_stock_threshold", "expiry_warning_days", "backup_keep"):
            if key in cleaned:
                if not cleaned[key].isdigit():
                    raise ValidationError("Thresholds and day counts must be whole numbers.")
        if "expiry_warning_days" in cleaned and int(cleaned["expiry_warning_days"]) < 1:
            raise ValidationError("Expiry warning days must be at least 1.")
        if "receipt_paper" in cleaned and cleaned["receipt_paper"] not in PAPER_SIZES:
            raise ValidationError("Please choose a valid receipt paper size.")
        if "currency_symbol" in cleaned and not cleaned["currency_symbol"]:
            raise ValidationError("Currency symbol cannot be empty.")
        with self.db.session() as s:
            for key, value in cleaned.items():
                row = s.get(Setting, key)
                if row is None:
                    s.add(Setting(key=key, value=value))
                else:
                    row.value = value
        self._cache = None
        self.all()

    def invalidate(self) -> None:
        self._cache = None
