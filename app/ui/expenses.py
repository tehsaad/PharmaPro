from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox

from app.context import AppContext
from app.ui import theme
from app.ui.base import Page
from app.ui.dialogs.common_dialogs import ExpenseDialog
from app.ui.range_picker import RangePicker
from app.ui.widgets import (
    FAILED,
    Card,
    Column,
    DataTable,
    PageHeader,
    SearchField,
    StatCard,
    Toast,
    button,
    confirm,
    hbox,
    run_safely,
)
from app.utils.constants import EXPENSE_CATEGORIES
from app.utils.formatting import money_short


class ExpensesPage(Page):
    title = "Expenses"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        header = PageHeader("Expenses", "Running costs such as rent, electricity and salaries — used for net profit.")
        add = header.add_action(button("Add expense", "plus", "primary"))
        add.clicked.connect(self.add_expense)
        self.body.addWidget(header)

        cards = hbox(spacing=14)
        self.c_total = StatCard("Expenses in period", "wallet", theme.CRITICAL, theme.CRITICAL_BG)
        self.c_gross = StatCard("Gross profit in period", "trending", theme.GOOD, theme.GOOD_BG)
        self.c_net = StatCard("Net profit", "coins")
        self.c_top = StatCard("Largest category", "chart", theme.TEXT_2, theme.NEUTRAL_BG)
        for c in (self.c_total, self.c_gross, self.c_net, self.c_top):
            cards.addWidget(c)
        self.body.addLayout(cards)

        card = Card()
        self.range = RangePicker("This Month")
        self.range.changed.connect(lambda *_: self.refresh())
        self.category = QComboBox()
        self.category.addItems(["All categories"] + EXPENSE_CATEGORIES)
        self.category.currentIndexChanged.connect(lambda *_: self.refresh())
        self.search = SearchField("Search title or description   (Ctrl+F)")
        self.search.search.connect(lambda _t: self.refresh())
        card.add(hbox(self.range, self.category, None, self.search))
        self.table = DataTable([
            Column("Date", lambda e: e.date, "date", width=130),
            Column("Title", lambda e: e.title, width=260, bold=True),
            Column("Category", lambda e: e.category, width=150),
            Column("Amount", lambda e: e.amount, "money", width=130),
            Column("Description", lambda e: e.description, stretch=True),
        ], "No expenses in this period", "Record rent, bills and salaries to see true net profit.", "wallet", sort=None)
        self.table.activated.connect(self.edit_expense)
        card.add(self.table, 1)
        edit = button("Edit", "edit")
        edit.clicked.connect(lambda: self.edit_expense(self.table.selected()))
        delete = button("Delete", "trash", "danger")
        delete.clicked.connect(lambda: self.delete_expense(self.table.selected()))
        card.add(hbox(edit, None, delete))
        self.body.addWidget(card, 1)

    def refresh(self) -> None:
        start, end = self.range.range()
        cat = self.category.currentText()
        rows = self.ctx.expenses.list(start, end, self.search.text(), "" if cat == "All categories" else cat)
        self.table.set_rows(rows)
        summary = self.ctx.profit.summary(start, end)
        shown = sum((e.amount for e in rows), Decimal("0"))
        self.c_total.set(money_short(summary.expenses), f"{len(rows)} shown · {money_short(shown)}")
        self.c_gross.set(money_short(summary.gross_profit), f"From {summary.sales_count} sale(s)")
        color = theme.GOOD if summary.net_profit >= 0 else theme.CRITICAL
        self.c_net.set(money_short(summary.net_profit), "Gross profit − expenses", color)
        cats = self.ctx.expenses.by_category(start, end)
        self.c_top.set(cats[0][0] if cats else "—", money_short(cats[0][1]) if cats else "No expenses")

    def focus_search(self) -> bool:
        self.search.setFocus()
        return True

    def add_expense(self):
        if ExpenseDialog(self.ctx, self).exec():
            Toast.show_message(self, "Expense saved")
            self.refresh()

    def edit_expense(self, e):
        if e is not None and ExpenseDialog(self.ctx, self, e).exec():
            Toast.show_message(self, "Expense updated")
            self.refresh()

    def delete_expense(self, e):
        if e is None:
            return
        if confirm(self, "Delete expense?", f"Delete “{e.title}”? This cannot be undone.", "Delete", danger=True):
            if run_safely(self, self.ctx.expenses.delete, e.id) is not FAILED:
                Toast.show_message(self, "Expense deleted")
                self.refresh()
