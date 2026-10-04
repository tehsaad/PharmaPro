"""Revenue, cost of goods sold, gross and net profit from stored transactions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.database.database import Database
from app.database.repositories import ExpenseRepository, SaleRepository


@dataclass
class ProfitSummary:
    start: date
    end: date
    sales_count: int
    subtotal: Decimal
    discount: Decimal
    revenue: Decimal          # amount actually charged (after discount)
    cogs: Decimal             # actual batch cost of the units sold
    gross_profit: Decimal     # revenue - cogs
    expenses: Decimal
    net_profit: Decimal       # gross_profit - expenses

    @property
    def average_sale(self) -> Decimal:
        if not self.sales_count:
            return Decimal("0.00")
        return (self.revenue / self.sales_count).quantize(Decimal("0.01"))

    @property
    def margin_pct(self) -> float:
        return float(self.gross_profit / self.revenue * 100) if self.revenue else 0.0


class ProfitService:
    def __init__(self, db: Database):
        self.db = db

    def summary(self, start: date, end: date) -> ProfitSummary:
        with self.db.read() as s:
            t = SaleRepository(s).totals_between(start, end)
            expenses = ExpenseRepository(s).total_between(start, end)
        return ProfitSummary(
            start=start, end=end, sales_count=t["count"], subtotal=t["subtotal"], discount=t["discount"],
            revenue=t["revenue"], cogs=t["cogs"], gross_profit=t["gross_profit"], expenses=expenses,
            net_profit=t["gross_profit"] - expenses,
        )
