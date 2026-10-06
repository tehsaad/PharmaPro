"""Aggregations for the Analytics and Dashboard screens.

Heavy lifting happens in SQL (GROUP BY); pandas is used to fill gaps in the
time series so charts show every day/month in the range, including zero days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, select

from app.database.database import Database
from app.database.repositories import day_bounds
from app.models import Medicine, Sale, SaleItem

PRESETS = ["Today", "Yesterday", "This Week", "This Month", "Last Month", "This Year", "Custom Range"]


def resolve_range(preset: str, today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    if preset == "Today":
        return today, today
    if preset == "Yesterday":
        y = today - timedelta(days=1)
        return y, y
    if preset == "This Week":
        return today - timedelta(days=today.weekday()), today
    if preset == "This Month":
        return today.replace(day=1), today
    if preset == "Last Month":
        last_end = today.replace(day=1) - timedelta(days=1)
        return last_end.replace(day=1), last_end
    if preset == "This Year":
        return today.replace(month=1, day=1), today
    if preset == "Last 30 Days":
        return today - timedelta(days=29), today
    raise ValueError(f"Unknown preset {preset}")


@dataclass
class TopMedicine:
    code: str
    name: str
    category: str
    quantity: int
    revenue: Decimal
    profit: Decimal


def _to_dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return (Decimal(int(value or 0)) / 100).quantize(Decimal("0.01"))


class AnalyticsService:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def granularity(start: date, end: date) -> str:
        return "day" if (end - start).days <= 62 else "month"

    def timeseries(self, start: date, end: date) -> pd.DataFrame:
        """Revenue, cost, gross profit and sale count per day or month."""
        gran = self.granularity(start, end)
        fmt = "%Y-%m-%d" if gran == "day" else "%Y-%m"
        lo, hi = day_bounds(start, end)
        period = func.strftime(fmt, Sale.sale_date)
        q = (
            select(period, func.count(Sale.id), func.sum(Sale.total), func.sum(Sale.cost_of_goods), func.sum(Sale.gross_profit))
            .where(Sale.sale_date >= lo, Sale.sale_date < hi)
            .group_by(period)
        )
        with self.db.read() as s:
            rows = s.execute(q).all()
        data = {
            p: {"count": int(c), "revenue": float(_to_dec(r)), "cost": float(_to_dec(k)), "profit": float(_to_dec(g))}
            for p, c, r, k, g in rows
        }
        if gran == "day":
            index = pd.date_range(start, end, freq="D")
            keys = [d.strftime(fmt) for d in index]
        else:
            index = pd.date_range(start.replace(day=1), end, freq="MS")
            keys = [d.strftime(fmt) for d in index]
        df = pd.DataFrame(
            [data.get(k, {"count": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0}) for k in keys],
            index=index,
        )
        df.index.name = "period"
        return df

    def top_selling(self, start: date, end: date, limit: int = 10) -> list[TopMedicine]:
        lo, hi = day_bounds(start, end)
        qty = func.sum(SaleItem.quantity)
        q = (
            select(Medicine.code, Medicine.name, Medicine.category, qty, func.sum(SaleItem.total), func.sum(SaleItem.profit))
            .join(SaleItem, SaleItem.medicine_id == Medicine.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.sale_date >= lo, Sale.sale_date < hi)
            .group_by(Medicine.id)
            .order_by(qty.desc(), Medicine.name)
        )
        if limit:
            q = q.limit(limit)
        with self.db.read() as s:
            rows = s.execute(q).all()
        return [TopMedicine(c, n, cat, int(qn), _to_dec(r), _to_dec(p)) for c, n, cat, qn, r, p in rows]

    def sales_by_category(self, start: date, end: date) -> list[tuple[str, Decimal]]:
        lo, hi = day_bounds(start, end)
        cat = func.coalesce(func.nullif(Medicine.category, ""), "Uncategorised")
        q = (
            select(cat, func.sum(SaleItem.total))
            .join(SaleItem, SaleItem.medicine_id == Medicine.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.sale_date >= lo, Sale.sale_date < hi)
            .group_by(cat)
            .order_by(func.sum(SaleItem.total).desc())
        )
        with self.db.read() as s:
            return [(c, _to_dec(t)) for c, t in s.execute(q).all()]
