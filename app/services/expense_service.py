from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.database.database import Database
from app.database.repositories import ExpenseRepository
from app.models import Expense
from app.services.errors import NotFoundError, ValidationError
from app.utils.constants import EXPENSE_CATEGORIES
from app.utils.validators import clean_text, parse_date, parse_money, require_text


class ExpenseService:
    def __init__(self, db: Database):
        self.db = db

    def _validated(self, title, category, amount, on, description) -> dict:
        category = clean_text(category, 60) or "Other"
        if category not in EXPENSE_CATEGORIES:
            raise ValidationError("Please choose a valid expense category.")
        d = parse_date(on, "Expense date")
        if d > date.today():
            raise ValidationError("Expense date cannot be in the future.")
        return {
            "title": require_text(title, "Title"),
            "category": category,
            "amount": parse_money(amount, "Amount", allow_zero=False),
            "date": d,
            "description": clean_text(description, 2000),
        }

    def add(self, title: str, category: str, amount, on: date | str, description: str = "") -> Expense:
        values = self._validated(title, category, amount, on, description)
        with self.db.session() as s:
            exp = Expense(**values)
            s.add(exp)
            s.flush()
            return exp

    def update(self, expense_id: int, title: str, category: str, amount, on, description: str = "") -> None:
        values = self._validated(title, category, amount, on, description)
        with self.db.session() as s:
            exp = s.get(Expense, expense_id)
            if exp is None:
                raise NotFoundError("This expense no longer exists.")
            for k, v in values.items():
                setattr(exp, k, v)

    def delete(self, expense_id: int) -> None:
        with self.db.session() as s:
            exp = s.get(Expense, expense_id)
            if exp is not None:
                s.delete(exp)

    def list(self, start: date, end: date, search: str = "", category: str = "") -> list[Expense]:
        with self.db.read() as s:
            return ExpenseRepository(s).list_between(start, end, search, category)

    def total(self, start: date, end: date) -> Decimal:
        with self.db.read() as s:
            return ExpenseRepository(s).total_between(start, end)

    def by_category(self, start: date, end: date) -> list[tuple[str, Decimal]]:
        with self.db.read() as s:
            return ExpenseRepository(s).by_category(start, end)
