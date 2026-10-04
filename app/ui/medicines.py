from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QMenu

from app.context import AppContext
from app.ui.base import Page
from app.ui.dialogs.common_dialogs import BatchesDialog
from app.ui.dialogs.medicine_dialog import MedicineDialog
from app.ui.icons import icon
from app.ui.widgets import (
    FAILED,
    Card,
    Column,
    DataTable,
    PageHeader,
    SearchField,
    Toast,
    button,
    confirm,
    hbox,
    label,
    run_safely,
)
from app.utils import constants as C


class MedicinesPage(Page):
    title = "Medicines"

    STATUS_FILTERS = ["All statuses", "Active", C.STATUS_LOW, C.STATUS_OUT, C.STATUS_EXPIRING, C.STATUS_EXPIRED, C.STATUS_INACTIVE]

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.navigate = lambda *a, **k: None
        header = PageHeader("Medicines", "Your medicine catalogue with live stock, prices and expiry.")
        stock = header.add_action(button("Add stock", "package-plus"))
        stock.clicked.connect(lambda: self.navigate("add_stock"))
        add = header.add_action(button("Add medicine", "plus", "primary"))
        add.clicked.connect(self.add_medicine)
        self.body.addWidget(header)

        card = Card()
        self.search = SearchField("Search by code, name, generic name or manufacturer   (Ctrl+F)")
        self.search.search.connect(self._apply_filters)
        self.category = QComboBox()
        self.category.setMinimumWidth(190)
        self.category.currentIndexChanged.connect(self._apply_filters)
        self.status = QComboBox()
        self.status.addItems(self.STATUS_FILTERS)
        self.status.setCurrentIndex(1)
        self.status.currentIndexChanged.connect(self._apply_filters)
        self.count = label("", "Muted")
        card.add(hbox(self.search, self.category, self.status, None, self.count))

        self.table = DataTable([
            Column("Code", lambda m: m.code, width=90, bold=True),
            Column("Name", lambda m: f"{m.name} {m.strength}".strip(), stretch=True),
            Column("Generic Name", lambda m: m.generic_name, width=160),
            Column("Category", lambda m: m.category, width=140),
            Column("Manufacturer", lambda m: m.manufacturer, width=120),
            Column("Stock", lambda m: m.sellable_stock, "int", width=75),
            Column("Selling Price", lambda m: m.selling_price, "money", width=110),
            Column("Nearest Expiry", lambda m: m.nearest_expiry, "expiry", width=115),
            Column("Status", lambda m: m.status, "status", width=135),
        ], "No medicines found", "Try a different search, or add a new medicine.", "pill")
        self.table.activated.connect(lambda m: self.edit_medicine(m))
        self.table.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.view.customContextMenuRequested.connect(self._context_menu)
        self.table.selection_changed.connect(self._update_buttons)
        card.add(self.table, 1)

        self.btn_edit = button("Edit", "edit")
        self.btn_edit.clicked.connect(lambda: self.edit_medicine(self.table.selected()))
        self.btn_batches = button("View batches", "layers")
        self.btn_batches.clicked.connect(lambda: self.view_batches(self.table.selected()))
        self.btn_toggle = button("Deactivate", "ban")
        self.btn_toggle.clicked.connect(lambda: self.toggle_active(self.table.selected()))
        self.btn_delete = button("Delete", "trash", "danger")
        self.btn_delete.clicked.connect(lambda: self.delete_medicine(self.table.selected()))
        card.add(hbox(self.btn_edit, self.btn_batches, self.btn_toggle, None, self.btn_delete))
        self.body.addWidget(card, 1)
        self._update_buttons(None)

    # ----------------------------------------------------------------- data
    def refresh(self) -> None:
        today = date.today()
        rows = self.ctx.medicines.summaries(include_inactive=True, today=today)
        for m in rows:
            m.status = self.ctx.inventory.medicine_status(m, today)
        current = self.category.currentText()
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("All categories")
        self.category.addItems(sorted({m.category for m in rows if m.category}))
        idx = self.category.findText(current)
        self.category.setCurrentIndex(max(idx, 0))
        self.category.blockSignals(False)
        self.table.set_rows(rows)
        self._apply_filters()

    def _apply_filters(self, *_):
        cat = self.category.currentText()
        status = self.status.currentText()

        def keep(m):
            if cat and cat != "All categories" and m.category != cat:
                return False
            if status == "All statuses":
                return True
            if status == "Active":
                return m.active
            return m.status == status

        self.table.set_predicate(keep)
        self.table.search(self.search.text())
        total = self.table.model.rowCount()
        shown = self.table.proxy.rowCount()
        self.count.setText(f"{shown:,} of {total:,} medicines")

    def focus_search(self) -> bool:
        self.search.setFocus()
        self.search.selectAll()
        return True

    def _update_buttons(self, m):
        for b in (self.btn_edit, self.btn_batches, self.btn_toggle, self.btn_delete):
            b.setEnabled(m is not None)
        if m is not None:
            self.btn_toggle.setText("Deactivate" if m.active else "Activate")

    # -------------------------------------------------------------- actions
    def add_medicine(self):
        dlg = MedicineDialog(self.ctx, self)
        if dlg.exec():
            Toast.show_message(self, "Medicine added")
            self.refresh()

    def edit_medicine(self, m):
        if m is None:
            return
        dlg = MedicineDialog(self.ctx, self, medicine_id=m.id)
        if dlg.exec():
            Toast.show_message(self, "Changes saved")
            self.refresh()

    def view_batches(self, m):
        if m is None:
            return
        dlg = BatchesDialog(self.ctx, m.id, self)
        dlg.exec()
        if dlg.changed:
            self.refresh()

    def toggle_active(self, m):
        if m is None:
            return
        if m.active and not confirm(self, "Deactivate medicine?",
                                    f"{m.name} will be hidden from sales and stock entry.\n"
                                    "Its sales history is kept. You can activate it again at any time.", "Deactivate"):
            return
        if run_safely(self, self.ctx.medicines.set_active, m.id, not m.active) is not FAILED:
            Toast.show_message(self, f"{m.name} {'deactivated' if m.active else 'activated'}")
            self.refresh()

    def delete_medicine(self, m):
        if m is None:
            return
        if not confirm(self, "Remove medicine?",
                       f"Remove {m.name} ({m.code})?\n\nIf it has stock or sales history it will be "
                       "deactivated instead, so your records stay complete.", "Remove", danger=True):
            return
        result = run_safely(self, self.ctx.medicines.remove, m.id)
        if result is FAILED:
            return
        if result == "deactivated":
            Toast.show_message(self, f"{m.name} has transaction history, so it was deactivated instead of deleted.", "info", 4500)
        else:
            Toast.show_message(self, f"{m.name} removed")
        self.refresh()

    def _context_menu(self, pos):
        m = self.table.selected()
        if m is None:
            return
        menu = QMenu(self)
        menu.addAction(icon("edit"), "Edit…", lambda: self.edit_medicine(m))
        menu.addAction(icon("layers"), "View batches…", lambda: self.view_batches(m))
        menu.addAction(icon("package-plus"), "Add stock…", lambda: self.navigate("add_stock", medicine_id=m.id))
        menu.addSeparator()
        menu.addAction(icon("ban"), "Deactivate" if m.active else "Activate", lambda: self.toggle_active(m))
        menu.addAction(icon("trash", "#B91C1C"), "Remove…", lambda: self.delete_medicine(m))
        menu.exec(self.table.view.viewport().mapToGlobal(pos))
