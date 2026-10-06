"""Inventory screen: every batch on hand with status, value and expiry."""
from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QPushButton

from app.context import AppContext
from app.services.inventory_service import STOCK_FILTERS
from app.ui import theme
from app.ui.base import Page
from app.ui.dialogs.common_dialogs import BatchesDialog
from app.ui.widgets import Card, Column, DataTable, PageHeader, SearchField, StatCard, button, hbox, label
from app.utils.formatting import money_short


def _days_color(r):
    if r.days_to_expiry is None:
        return None
    if r.days_to_expiry <= 0:
        return theme.CRITICAL
    if r.days_to_expiry <= 30:
        return theme.SERIOUS
    return None


class StockPage(Page):
    title = "Inventory"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.navigate = lambda *a, **k: None
        self.filter = "All"
        header = PageHeader("Inventory", "Every batch on hand — quantities, costs, prices and expiry.")
        add = header.add_action(button("Add stock", "package-plus", "primary"))
        add.clicked.connect(lambda: self.navigate("add_stock"))
        self.body.addWidget(header)

        cards = hbox(spacing=14)
        self.c_value = StatCard("Stock value (cost)", "package")
        self.c_retail = StatCard("Retail value", "coins", theme.SERIES[0], "#E8F1FB")
        self.c_units = StatCard("Units on hand", "layers", theme.TEXT_2, theme.NEUTRAL_BG)
        self.c_expired = StatCard("Expired stock value", "ban", theme.CRITICAL, theme.CRITICAL_BG)
        for c in (self.c_value, self.c_retail, self.c_units, self.c_expired):
            cards.addWidget(c)
        self.body.addLayout(cards)

        card = Card()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.filter_buttons: dict[str, QPushButton] = {}
        seg = hbox(spacing=6)
        for name in STOCK_FILTERS:
            b = QPushButton(name)
            b.setCheckable(True)
            b.setProperty("variant", "ghost")
            b.setStyleSheet(
                f"QPushButton:checked {{ background: {theme.ACCENT_SOFT}; color: {theme.ACCENT_HOVER}; "
                f"border: 1px solid #B5DED8; }}")
            b.clicked.connect(lambda _=False, n=name: self.set_filter(n))
            self.group.addButton(b)
            self.filter_buttons[name] = b
            seg.addWidget(b)
        self.filter_buttons["All"].setChecked(True)
        self.search = SearchField("Search medicine, code, batch or supplier   (Ctrl+F)")
        self.search.search.connect(lambda t: (self.table.search(t), self._update_count()))
        self.count = label("", "Muted")
        card.add(hbox(seg, None, self.search, self.count))

        self.table = DataTable([
            Column("Medicine", lambda r: r.medicine, stretch=True, bold=True),
            Column("Code", lambda r: r.code, width=80),
            Column("Batch", lambda r: r.batch_number, width=95),
            Column("Qty", lambda r: r.quantity_remaining, "int", width=65),
            Column("Cost", lambda r: r.purchase_price, "money", width=95),
            Column("Price", lambda r: r.selling_price, "money", width=95),
            Column("Expiry", lambda r: r.expiry_date, "expiry", width=105, color=_days_color),
            Column("Days", lambda r: r.days_to_expiry, "int", width=60, color=_days_color),
            Column("Supplier", lambda r: r.supplier, width=150),
            Column("Value", lambda r: r.stock_value, "money", width=110),
            Column("Status", lambda r: r.status, "status", width=135),
        ], "Nothing to show", "No batches match this filter.", "package")
        self.table.activated.connect(self._open)
        card.add(self.table, 1)
        hint = label("Double-click a row to see all batches of that medicine. Expired batches are blocked at the till.", "Muted")
        card.add(hint)
        self.body.addWidget(card, 1)

    def set_filter(self, name: str) -> None:
        if name in self.filter_buttons:
            self.filter = name
            self.filter_buttons[name].setChecked(True)
            self.refresh()

    def refresh(self) -> None:
        inv = self.ctx.inventory
        rows = inv.stock_rows(self.filter)
        self.table.set_rows(rows)
        self.table.search(self.search.text())
        all_rows = rows if self.filter == "All" else inv.stock_rows("All")
        sellable_units = sum(r.quantity_remaining for r in all_rows if r.status != "Expired")
        self.c_value.set(money_short(inv.stock_value()), "Sellable stock only")
        self.c_retail.set(money_short(inv.retail_value()), "At current selling prices")
        self.c_units.set(f"{sellable_units:,}", f"{sum(1 for r in all_rows if r.batch_id)} batches")
        self.c_expired.set(money_short(inv.expired_value()), "Cannot be sold", theme.CRITICAL if inv.expired_value() else None)
        counts = {name: 0 for name in self.filter_buttons}
        for r in all_rows:
            counts["All"] += 1
            if r.status in counts:
                counts[r.status] += 1
        counts["Out of Stock"] = len(inv.stock_rows("Out of Stock"))
        for name, b in self.filter_buttons.items():
            b.setText(f"{name}  {counts.get(name, 0)}")
        self._update_count()

    def _update_count(self):
        self.count.setText(f"{self.table.proxy.rowCount():,} rows")

    def focus_search(self) -> bool:
        self.search.setFocus()
        self.search.selectAll()
        return True

    def _open(self, r):
        dlg = BatchesDialog(self.ctx, r.medicine_id, self)
        dlg.exec()
        if dlg.changed:
            self.refresh()
