from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QSplitter
from PySide6.QtCore import Qt

from app.context import AppContext
from app.ui.base import Page
from app.ui.range_picker import RangePicker
from app.ui.widgets import Card, Column, DataTable, PageHeader, SearchField, button, hbox, label
from app.utils.formatting import fmt_date, money


class PurchasesPage(Page):
    title = "Purchases"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.navigate = lambda *a, **k: None
        header = PageHeader("Purchases", "Stock received from suppliers, with the exact cost of every batch.")
        add = header.add_action(button("Add stock", "package-plus", "primary"))
        add.clicked.connect(lambda: self.navigate("add_stock"))
        self.body.addWidget(header)

        card = Card()
        self.range = RangePicker("This Month")
        self.range.changed.connect(lambda *_: self.refresh())
        self.search = SearchField("Supplier or invoice number   (Ctrl+F)")
        self.search.search.connect(lambda _t: self.refresh())
        self.summary = label("", "Muted")
        card.add(hbox(self.range, self.search, None, self.summary))

        split = QSplitter(Qt.Vertical)
        self.table = DataTable([
            Column("Date", lambda p: p.purchase_date, "date", width=130),
            Column("Supplier", lambda p: p.supplier, width=260, bold=True),
            Column("Invoice", lambda p: p.invoice_number or "—", width=160),
            Column("Recorded", lambda p: p.created_at, "datetime", width=200),
            Column("Amount", lambda p: p.total_amount, "money", width=140, stretch=True),
        ], "No purchases in this period", "Use Add Stock to record a supplier invoice.", "truck", sort=None)
        self.table.selection_changed.connect(self._show_items)
        split.addWidget(self.table)

        lower = Card(padding=12)
        self.items_title = label("Select a purchase to see its items", "SectionTitle")
        lower.add(self.items_title)
        self.items = DataTable([
            Column("Code", lambda i: i.medicine.code, width=100),
            Column("Medicine", lambda i: i.medicine.name, width=220, bold=True),
            Column("Batch", lambda i: i.batch.batch_number, width=120),
            Column("Expiry", lambda i: i.batch.expiry_date, "expiry", width=120),
            Column("Qty", lambda i: i.quantity, "int", width=80),
            Column("Purchase Price", lambda i: i.purchase_price, "money", width=130),
            Column("Selling Price", lambda i: i.selling_price, "money", width=130),
            Column("Line Total", lambda i: i.total, "money", width=130, stretch=True),
        ], "No purchase selected", "", "file-text", row_height=36, sort=None)
        lower.add(self.items, 1)
        split.addWidget(lower)
        split.setSizes([400, 300])
        card.add(split, 1)
        self.body.addWidget(card, 1)

    def refresh(self) -> None:
        start, end = self.range.range()
        rows = self.ctx.purchases.list(start, end, self.search.text())
        self.table.set_rows(rows)
        total = sum((p.total_amount for p in rows), Decimal("0"))
        self.summary.setText(f"{len(rows)} purchase(s) · {money(total)}")
        self.items.set_rows([])
        self.items_title.setText("Select a purchase to see its items")

    def _show_items(self, p):
        if p is None:
            return
        full = self.ctx.purchases.get(p.id)
        self.items_title.setText(f"{full.supplier} · {full.invoice_number or 'no invoice no.'} · {fmt_date(full.purchase_date)}")
        self.items.set_rows(full.items)

    def focus_search(self) -> bool:
        self.search.setFocus()
        return True
