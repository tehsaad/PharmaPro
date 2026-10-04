"""ADD STOCK: receive many medicines from one supplier invoice in a single transaction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
)

from app.context import AppContext
from app.services.purchase_service import StockLine
from app.ui import theme
from app.ui.base import Page
from app.ui.dialogs.medicine_dialog import MedicineDialog
from app.ui.medicine_picker import MedicinePicker
from app.ui.widgets import (
    FAILED,
    Banner,
    Card,
    PageHeader,
    Toast,
    button,
    confirm,
    date_edit,
    field,
    from_qdate,
    hbox,
    label,
    money_edit,
    run_safely,
    to_decimal,
    to_qdate,
    warn,
)
from app.utils.formatting import fmt_date, money


@dataclass
class EntryRow:
    medicine_id: int
    code: str
    name: str
    batch: str
    expiry: date
    quantity: int
    cost: Decimal
    price: Decimal

    @property
    def total(self) -> Decimal:
        return self.cost * self.quantity


class AddStockPage(Page):
    title = "Add Stock"
    COLS = ["Code", "Medicine", "Batch", "Expiry", "Quantity", "Purchase Price", "Selling Price", "Line Total", ""]

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.navigate = lambda *a, **k: None
        self.rows: list[EntryRow] = []
        self.current_medicine: int | None = None

        header = PageHeader("Add Stock", "Receive a supplier invoice — add as many medicines as you need, then save once.")
        self.body.addWidget(header)

        # ---- invoice header
        inv = Card(padding=16)
        self.supplier = QComboBox()
        self.supplier.setEditable(True)
        self.supplier.setInsertPolicy(QComboBox.NoInsert)
        self.supplier.lineEdit().setPlaceholderText("Supplier name")
        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText("e.g. INV-1023")
        self.pdate = date_edit(date.today(), allow_future=False)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.addWidget(field("Supplier *", self.supplier), 0, 0)
        g.addWidget(field("Invoice number", self.invoice), 0, 1)
        g.addWidget(field("Purchase date", self.pdate), 0, 2)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(1, 2)
        g.setColumnStretch(2, 1)
        inv.add(g)
        self.body.addWidget(inv)

        # ---- line entry
        entry = Card(padding=16)
        entry.add(label("Add a medicine to this invoice", "SectionTitle"))
        self.picker = MedicinePicker(ctx, "Type code or name, then choose…")
        self.picker.picked.connect(self._medicine_chosen)
        self.picker.not_found.connect(self._offer_new_medicine)
        self.picker.textEdited.connect(lambda _t: setattr(self, "current_medicine", None))
        new_med = button("New medicine", "plus", "ghost", "Create a medicine that is not in the catalogue yet")
        new_med.clicked.connect(lambda: self._offer_new_medicine(self.picker.text(), ask=False))
        self.batch = QLineEdit()
        self.batch.setPlaceholderText("e.g. P123")
        self.expiry = date_edit(date.today() + timedelta(days=365))
        self.expiry.setMinimumDate(to_qdate(date.today() + timedelta(days=1)))
        self.qty = QSpinBox()
        self.qty.setRange(1, 10_000_000)
        self.qty.setGroupSeparatorShown(True)
        self.cost = money_edit()
        self.price = money_edit()
        self.cost.valueChanged.connect(self._check_margin)
        self.price.valueChanged.connect(self._check_margin)
        self.add_btn = button("Add to list", "plus", "primary")
        self.add_btn.clicked.connect(self._add_line)
        for w in (self.batch, self.qty, self.cost, self.price):
            if isinstance(w, QLineEdit):
                w.returnPressed.connect(self._add_line)
            else:
                w.lineEdit().returnPressed.connect(self._add_line)

        g2 = QGridLayout()
        g2.setHorizontalSpacing(12)
        g2.addWidget(field("Medicine *", self.picker), 0, 0)
        g2.addWidget(field("Batch no. *", self.batch), 0, 1)
        g2.addWidget(field("Expiry date *", self.expiry), 0, 2)
        g2.addWidget(field("Quantity *", self.qty), 0, 3)
        g2.addWidget(field("Purchase price (each)", self.cost), 0, 4)
        g2.addWidget(field("Selling price (each)", self.price), 0, 5)
        g2.setColumnStretch(0, 4)
        for c in range(1, 6):
            g2.setColumnStretch(c, 2)
        entry.add(g2)
        self.margin = label("", "Muted")
        entry.add(hbox(new_med, self.margin, None, self.add_btn))
        self.body.addWidget(entry)

        # ---- lines
        lines = Card(padding=16)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i, w in enumerate([100, 0, 110, 110, 90, 130, 130, 130, 44]):
            if w:
                self.table.setColumnWidth(i, w)
        self.table.doubleClicked.connect(lambda idx: self._edit_line(idx.row()))
        self.table.setToolTip("Double-click a row to change it")
        lines.add(self.table, 1)
        self.warning = Banner("", "warn")
        self.warning.hide()
        lines.add(self.warning)

        remove = button("Remove", "trash")
        remove.clicked.connect(self._remove_selected)
        clear = button("Clear", "x")
        clear.clicked.connect(self._clear)
        self.summary = label("", "SectionTitle")
        self.save_btn = button("Save Stock", "save", "big", "Ctrl+S")
        self.save_btn.clicked.connect(self.handle_save)
        lines.add(hbox(remove, clear, None, self.summary, self.save_btn, spacing=12))
        self.body.addWidget(lines, 1)
        self._render()

    # ---------------------------------------------------------------- page hooks
    def refresh(self) -> None:
        self.picker.reload()
        current = self.supplier.currentText()
        self.supplier.clear()
        self.supplier.addItems(self.ctx.purchases.suppliers())
        self.supplier.setCurrentText(current)

    def preselect(self, medicine_id: int) -> None:
        self._medicine_chosen(medicine_id)

    def focus_search(self) -> bool:
        self.picker.setFocus()
        self.picker.selectAll()
        return True

    # ---------------------------------------------------------------- entry form
    def _medicine_chosen(self, medicine_id: int) -> None:
        med = self.ctx.medicines.get(medicine_id)
        self.current_medicine = medicine_id
        self.picker.blockSignals(True)
        self.picker.setText(f"{med.code}  —  {med.name} {med.strength}".strip())
        self.picker.blockSignals(False)
        batches = self.ctx.medicines.batches(medicine_id)
        if batches:  # prefill with the most recent prices as a convenience
            last = max(batches, key=lambda b: b.id)
            self.cost.setValue(float(last.purchase_price))
            self.price.setValue(float(last.selling_price))
        self.batch.setFocus()

    def _offer_new_medicine(self, text: str, ask: bool = True) -> None:
        if ask and not confirm(self, "Medicine not found",
                               f"No medicine matches “{text}”.\n\nCreate a new medicine now?", "Create medicine"):
            return
        code = text if text and " " not in text.strip() else ""
        dlg = MedicineDialog(self.ctx, self, initial_code=code)
        if dlg.exec() and dlg.saved_id:
            self.picker.reload()
            self._medicine_chosen(dlg.saved_id)

    def _check_margin(self, *_):
        cost, price = to_decimal(self.cost), to_decimal(self.price)
        if price and cost and price < cost:
            self.margin.setText("⚠ Selling price is below the purchase price")
            self.margin.setStyleSheet(f"color: {theme.WARN}; font-weight: 600;")
        elif price and cost:
            pct = (price - cost) / price * 100
            self.margin.setText(f"Margin {money(price - cost)} per unit ({pct:.1f}%)")
            self.margin.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        else:
            self.margin.setText("")

    def _add_line(self) -> None:
        if self.current_medicine is None:
            warn(self, "Choose a medicine", "Please choose a medicine from the list first.")
            self.picker.setFocus()
            return
        batch = self.batch.text().strip().upper()
        if not batch:
            warn(self, "Batch number needed", "Please enter the batch number printed on the pack.")
            self.batch.setFocus()
            return
        expiry = from_qdate(self.expiry.date())
        if expiry <= from_qdate(self.pdate.date()):
            warn(self, "Check expiry date", "The expiry date must be after the purchase date. Expired stock cannot be added.")
            return
        if any(r.medicine_id == self.current_medicine and r.batch == batch for r in self.rows):
            warn(self, "Already in the list", f"Batch {batch} of this medicine is already in the list. "
                                               "Double-click it to change the quantity.")
            return
        med = self.ctx.medicines.get(self.current_medicine)
        self.rows.append(EntryRow(med.id, med.code, f"{med.name} {med.strength}".strip(), batch, expiry,
                                  self.qty.value(), to_decimal(self.cost), to_decimal(self.price)))
        self._reset_entry()
        self._render()

    def _reset_entry(self) -> None:
        self.current_medicine = None
        self.picker.clear()
        self.batch.clear()
        self.qty.setValue(1)
        self.cost.setValue(0)
        self.price.setValue(0)
        self.expiry.setDate(to_qdate(date.today() + timedelta(days=365)))
        self.margin.setText("")
        self.picker.setFocus()

    def _edit_line(self, row: int) -> None:
        if not (0 <= row < len(self.rows)):
            return
        r = self.rows.pop(row)
        self._medicine_chosen(r.medicine_id)
        self.batch.setText(r.batch)
        self.expiry.setDate(to_qdate(r.expiry))
        self.qty.setValue(r.quantity)
        self.cost.setValue(float(r.cost))
        self.price.setValue(float(r.price))
        self._render()
        Toast.show_message(self, "Row moved to the form above — change it and press “Add to list”.", "info")

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.rows.pop(row)
            self._render()

    def _clear(self) -> None:
        if self.rows and not confirm(self, "Clear all rows?", "Remove every medicine from this stock entry?", "Clear", danger=True):
            return
        self.rows.clear()
        self._render()

    # ---------------------------------------------------------------- table
    def _render(self) -> None:
        self.table.setRowCount(len(self.rows))
        below = []
        for i, r in enumerate(self.rows):
            values = [r.code, r.name, r.batch, fmt_date(r.expiry), f"{r.quantity:,}", money(r.cost), money(r.price), money(r.total)]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                if c >= 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 6 and r.price < r.cost:
                    item.setForeground(Qt.darkYellow)
                self.table.setItem(i, c, item)
            rm = button("", "x", "ghost", "Remove this row")
            rm.clicked.connect(lambda _=False, row=i: (self.rows.pop(row), self._render()))
            self.table.setCellWidget(i, 8, rm)
            if r.price < r.cost:
                below.append(f"{r.name} (batch {r.batch})")
        units = sum(r.quantity for r in self.rows)
        total = sum((r.total for r in self.rows), Decimal("0"))
        self.summary.setText(f"{len(self.rows)} item(s) · {units:,} units · Total {money(total)}" if self.rows else "No items yet")
        self.save_btn.setEnabled(bool(self.rows))
        if below:
            self.warning.set_text("Selling price is below purchase cost for: " + ", ".join(below))
            self.warning.show()
        else:
            self.warning.hide()

    # ---------------------------------------------------------------- save
    def handle_save(self) -> bool:
        if not self.rows:
            warn(self, "Nothing to save", "Add at least one medicine to the list first.")
            return True
        supplier = self.supplier.currentText().strip()
        if not supplier:
            warn(self, "Supplier needed", "Please enter the supplier's name.")
            self.supplier.setFocus()
            return True
        lines = [StockLine(r.medicine_id, r.batch, r.expiry, r.quantity, r.cost, r.price) for r in self.rows]
        below = self.ctx.purchases.below_cost_rows(lines)
        if below and not confirm(self, "Selling below cost?",
                                 f"{len(below)} item(s) have a selling price lower than the purchase price.\n\nSave anyway?",
                                 "Save anyway"):
            return True
        total = sum((r.total for r in self.rows), Decimal("0"))
        if not confirm(self, "Save stock?",
                       f"Supplier: {supplier}\nItems: {len(self.rows)}   ·   Units: {sum(r.quantity for r in self.rows):,}\n"
                       f"Invoice total: {money(total)}\n\nStock will be added to inventory.", "Save stock"):
            return True
        res = run_safely(self, self.ctx.purchases.add_stock, supplier, self.invoice.text(),
                         from_qdate(self.pdate.date()), lines)
        if res is FAILED:
            return True  # nothing was saved - the transaction rolled back
        Toast.show_message(self, f"Stock saved — {res.line_count} item(s), {res.units:,} units, {money(res.total_amount)}")
        self.rows.clear()
        self.invoice.clear()
        self._reset_entry()
        self._render()
        self.refresh()
        return True
