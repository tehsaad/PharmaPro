"""Query helpers for sales, purchases and expenses."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, Medicine, Purchase, PurchaseItem, Sale, SaleItem


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive date range -> [start 00:00, day-after-end 00:00)."""
    return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)


class SaleRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, sale_id: int) -> Sale | None:
        return self.s.scalar(
            select(Sale)
            .options(selectinload(Sale.items).selectinload(SaleItem.medicine), selectinload(Sale.items).selectinload(SaleItem.batch))
            .where(Sale.id == sale_id)
        )

    def get_by_receipt(self, receipt_number: str) -> Sale | None:
        sid = self.s.scalar(select(Sale.id).where(Sale.receipt_number == receipt_number.strip().upper()))
        return self.get(sid) if sid else None

    def last_receipt_for_prefix(self, prefix: str) -> str | None:
        return self.s.scalar(
            select(Sale.receipt_number)
            .where(Sale.receipt_number.like(f"{prefix}%"))
            .order_by(Sale.receipt_number.desc())
            .limit(1)
        )

    def list_between(self, start: date, end: date, search: str = "", limit: int | None = None) -> list[Sale]:
        lo, hi = day_bounds(start, end)
        q = select(Sale).where(Sale.sale_date >= lo, Sale.sale_date < hi)
        if search:
            term = f"%{search.strip()}%"
            sub = (
                select(SaleItem.sale_id)
                .join(Medicine, Medicine.id == SaleItem.medicine_id)
                .where(or_(Medicine.name.ilike(term), Medicine.code.ilike(term)))
            )
            q = q.where(or_(Sale.receipt_number.ilike(term), Sale.id.in_(sub)))
        q = q.order_by(Sale.sale_date.desc())
        if limit:
            q = q.limit(limit)
        return list(self.s.scalars(q))

    def totals_between(self, start: date, end: date) -> dict:
        lo, hi = day_bounds(start, end)
        row = self.s.execute(
            select(
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.subtotal), 0),
                func.coalesce(func.sum(Sale.discount), 0),
                func.coalesce(func.sum(Sale.total), 0),
                func.coalesce(func.sum(Sale.cost_of_goods), 0),
                func.coalesce(func.sum(Sale.gross_profit), 0),
            ).where(Sale.sale_date >= lo, Sale.sale_date < hi)
        ).one()
        count, subtotal, discount, total, cogs, profit = row
        return {
            "count": int(count),
            "subtotal": _dec(subtotal),
            "discount": _dec(discount),
            "revenue": _dec(total),
            "cogs": _dec(cogs),
            "gross_profit": _dec(profit),
        }


class PurchaseRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, purchase_id: int) -> Purchase | None:
        return self.s.scalar(
            select(Purchase)
            .options(selectinload(Purchase.items).selectinload(PurchaseItem.medicine), selectinload(Purchase.items).selectinload(PurchaseItem.batch))
            .where(Purchase.id == purchase_id)
        )

    def list_between(self, start: date, end: date, search: str = "") -> list[Purchase]:
        q = select(Purchase).where(Purchase.purchase_date >= start, Purchase.purchase_date <= end)
        if search:
            term = f"%{search.strip()}%"
            q = q.where(or_(Purchase.supplier.ilike(term), Purchase.invoice_number.ilike(term)))
        return list(self.s.scalars(q.order_by(Purchase.purchase_date.desc(), Purchase.id.desc())))

    def suppliers(self) -> list[str]:
        return list(self.s.scalars(select(Purchase.supplier).distinct().order_by(Purchase.supplier)))


class ExpenseRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, expense_id: int) -> Expense | None:
        return self.s.get(Expense, expense_id)

    def list_between(self, start: date, end: date, search: str = "", category: str = "") -> list[Expense]:
        q = select(Expense).where(Expense.date >= start, Expense.date <= end)
        if category:
            q = q.where(Expense.category == category)
        if search:
            term = f"%{search.strip()}%"
            q = q.where(or_(Expense.title.ilike(term), Expense.description.ilike(term)))
        return list(self.s.scalars(q.order_by(Expense.date.desc(), Expense.id.desc())))

    def total_between(self, start: date, end: date) -> Decimal:
        val = self.s.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.date >= start, Expense.date <= end))
        return _dec(val)

    def by_category(self, start: date, end: date) -> list[tuple[str, Decimal]]:
        rows = self.s.execute(
            select(Expense.category, func.sum(Expense.amount))
            .where(Expense.date >= start, Expense.date <= end)
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
        )
        return [(cat, _dec(total)) for cat, total in rows]


def _dec(value) -> Decimal:
    """Aggregates of Money columns come back as Decimal; COALESCE(…, 0) may give raw int 0."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return (Decimal(int(value or 0)) / 100).quantize(Decimal("0.01"))
