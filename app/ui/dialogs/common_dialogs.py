"""Smaller dialogs: batches, sale details, held sales, batch picker, expenses, about."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.config import APP_NAME, APP_VERSION
from app.context import AppContext
from app.ui import theme
from app.ui.icons import logo_pixmap
from app.ui.widgets import (
    FAILED,
    Column,
    DataTable,
    button,
    date_edit,
    field,
    from_qdate,
    hbox,
    label,
    money_edit,
    run_safely,
    to_decimal,
)
from app.utils.constants import EXPENSE_CATEGORIES
from app.utils.formatting import fmt_date, fmt_datetime, money


def _status_for_batch(b, today: date, warn_days: int) -> str:
    if b.expiry_date <= today:
        return "Expired"
    if b.quantity_remaining <= 0:
        return "Out of Stock"
    if (b.expiry_date - today).days <= warn_days:
        return "Expiring Soon"
    return "Normal"


class BatchesDialog(QDialog):
    """All batches of one medicine, with option to change a batch's selling price."""

    def __init__(self, ctx: AppContext, medicine_id: int, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.medicine_id = medicine_id
        self.changed = False
        med = ctx.medicines.get(medicine_id)
        self.setWindowTitle(f"Batches — {med.name}")
        self.resize(940, 520)
        today = date.today()
        warn = ctx.settings.expiry_warning_days
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(label(f"{med.name}  ·  {med.code}", "PageTitle"))
        lay.addWidget(label("Every batch keeps its own purchase cost, selling price and expiry date.", "Muted"))
        self.table = DataTable([
            Column("Batch", lambda b: b.batch_number, width=120, bold=True),
            Column("Received", lambda b: b.purchase_date, "date", width=110),
            Column("Expiry", lambda b: b.expiry_date, "expiry", width=110),
            Column("Received Qty", lambda b: b.quantity_received, "int", width=100),
            Column("Remaining", lambda b: b.quantity_remaining, "int", width=90),
            Column("Cost", lambda b: b.purchase_price, "money", width=100),
            Column("Selling", lambda b: b.selling_price, "money", width=100),
            Column("Supplier", lambda b: b.supplier, stretch=True),
            Column("Status", lambda b: _status_for_batch(b, today, warn), "status", width=130),
        ], "No batches yet", "Use Add Stock to receive this medicine.", "layers", sort=None)
        lay.addWidget(self.table, 1)
        price = button("Change selling price", "edit")
        price.clicked.connect(self._change_price)
        close = button("Close")
        close.clicked.connect(self.accept)
        lay.addLayout(hbox(price, None, close))
        self._load()

    def _load(self):
        self.table.set_rows(self.ctx.medicines.batches(self.medicine_id))

    def _change_price(self):
        b = self.table.selected()
        if b is None:
            return
        value, ok = QInputDialog.getDouble(
            self, "Change selling price",
            f"New selling price for batch {b.batch_number}.\nPast sales keep the price they were sold at.",
            float(b.selling_price), 0, 100_000_000, 2)
        if ok and run_safely(self, self.ctx.medicines.update_batch_selling_price, b.id, Decimal(str(value))) is not FAILED:
            self.changed = True
            self._load()


class SaleDetailDialog(QDialog):
    """Read-only view of a completed sale, with reprint."""

    def __init__(self, ctx: AppContext, sale_id: int, parent=None, on_print=None, show_profit: bool = True):
        super().__init__(parent)
        sale = ctx.sales.get(sale_id)
        self.setWindowTitle(f"Sale {sale.receipt_number}")
        self.resize(820, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(label(f"Receipt {sale.receipt_number}", "PageTitle"))
        lay.addWidget(label(fmt_datetime(sale.sale_date), "Muted"))
        cols = [
            Column("Code", lambda i: i.medicine.code, width=90),
            Column("Medicine", lambda i: i.medicine.name, stretch=True, bold=True),
            Column("Batch", lambda i: i.batch.batch_number, width=100),
            Column("Qty", lambda i: i.quantity, "int", width=60),
            Column("Price", lambda i: i.selling_price, "money", width=100),
            Column("Total", lambda i: i.total, "money", width=110),
        ]
        if show_profit:
            cols += [Column("Cost", lambda i: i.cost_total, "money", width=100),
                     Column("Profit", lambda i: i.profit, "money", width=100)]
        table = DataTable(cols, sort=None)
        table.set_rows(sale.items)
        lay.addWidget(table, 1)
        summary = (f"Subtotal {money(sale.subtotal)}   ·   Discount {money(sale.discount)}   ·   "
                   f"<b>Total {money(sale.total)}</b>")
        if show_profit:
            summary += f"   ·   Cost {money(sale.cost_of_goods)}   ·   <b style='color:{theme.GOOD}'>Profit {money(sale.gross_profit)}</b>"
        s = QLabel(summary)
        s.setTextFormat(Qt.RichText)
        lay.addWidget(s)
        close = button("Close")
        close.clicked.connect(self.accept)
        row = [None, close]
        if on_print:
            reprint = button("Print / PDF", "printer", "primary")
            reprint.clicked.connect(lambda: on_print(sale_id))
            row = [None, reprint, close]
        lay.addLayout(hbox(*row))


class HeldSalesDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.chosen_id: int | None = None
        self.setWindowTitle("Held sales")
        self.resize(480, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(label("Held sales", "PageTitle"))
        lay.addWidget(label("Resume a parked sale. Stock is checked again when you complete it.", "Muted", wrap=True))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self._resume())
        lay.addWidget(self.list, 1)
        discard = button("Discard", "trash", "danger")
        discard.clicked.connect(self._discard)
        resume = button("Resume sale", "play", "primary")
        resume.clicked.connect(self._resume)
        close = button("Close")
        close.clicked.connect(self.reject)
        lay.addLayout(hbox(discard, None, close, resume))
        self._load()

    def _load(self):
        self.list.clear()
        for h in self.ctx.sales.held_sales():
            import json
            n = len(json.loads(h.payload).get("lines", []))
            item = QListWidgetItem(f"{h.label or 'Held sale'}   ·   {n} item(s)   ·   {h.created_at:%d %b, %I:%M %p}")
            item.setData(Qt.UserRole, h.id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _resume(self):
        hid = self._current()
        if hid:
            self.chosen_id = hid
            self.accept()

    def _discard(self):
        hid = self._current()
        if hid:
            self.ctx.sales.discard_held(hid)
            self._load()


class BatchPickerDialog(QDialog):
    """Choose a specific batch instead of automatic FEFO. Expired batches cannot be chosen."""

    AUTO = -1

    def __init__(self, ctx: AppContext, medicine_id: int, parent=None, current: int | None = None):
        super().__init__(parent)
        self.chosen: int | None = None
        med = ctx.medicines.get(medicine_id)
        self.setWindowTitle(f"Choose batch — {med.name}")
        self.resize(560, 400)
        today = date.today()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(label("Choose batch", "PageTitle"))
        lay.addWidget(label("Automatic (recommended) sells the batch that expires first.", "Muted", wrap=True))
        self.list = QListWidget()
        auto = QListWidgetItem("Automatic — First Expiry, First Out")
        auto.setData(Qt.UserRole, self.AUTO)
        self.list.addItem(auto)
        for b in ctx.sales.sellable_batches(medicine_id):
            expired = b.is_expired(today) or b.purchase_date > today
            text = (f"Batch {b.batch_number}   ·   {b.quantity_remaining} left   ·   exp {fmt_date(b.expiry_date)}"
                    f"   ·   {money(b.selling_price)}")
            if b.is_expired(today):
                text += "   ·   EXPIRED – cannot be sold"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, b.id)
            if expired:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.list.addItem(item)
            if b.id == current:
                self.list.setCurrentItem(item)
        if self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _i: self._ok())
        lay.addWidget(self.list, 1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        ok = button("Use batch", "check", "primary")
        ok.clicked.connect(self._ok)
        lay.addLayout(hbox(None, cancel, ok))

    def _ok(self):
        item = self.list.currentItem()
        if item is None:
            return
        self.chosen = item.data(Qt.UserRole)
        self.accept()


class ExpenseDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None, expense=None):
        super().__init__(parent)
        self.ctx = ctx
        self.expense = expense
        self.setWindowTitle("Edit expense" if expense else "Add expense")
        self.setMinimumWidth(480)
        self.title = QLineEdit(expense.title if expense else "")
        self.title.setPlaceholderText("e.g. Electricity bill – May")
        self.category = QComboBox()
        self.category.addItems(EXPENSE_CATEGORIES)
        if expense:
            self.category.setCurrentText(expense.category)
        self.amount = money_edit()
        if expense:
            self.amount.setValue(float(expense.amount))
        self.date = date_edit(expense.date if expense else date.today(), allow_future=False)
        self.description = QPlainTextEdit(expense.description if expense else "")
        self.description.setFixedHeight(70)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(label(self.windowTitle(), "PageTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.addWidget(field("Title *", self.title), 0, 0, 1, 2)
        grid.addWidget(field("Category", self.category), 1, 0)
        grid.addWidget(field("Amount *", self.amount), 1, 1)
        grid.addWidget(field("Date", self.date), 2, 0)
        grid.addWidget(field("Description", self.description), 3, 0, 1, 2)
        lay.addLayout(grid)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        save = button("Save expense", "check", "primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        lay.addLayout(hbox(None, cancel, save))

    def _save(self):
        args = (self.title.text(), self.category.currentText(), to_decimal(self.amount),
                from_qdate(self.date.date()), self.description.toPlainText())
        if self.expense:
            res = run_safely(self, self.ctx.expenses.update, self.expense.id, *args)
        else:
            res = run_safely(self, self.ctx.expenses.add, *args)
        if res is not FAILED:
            self.accept()


class AboutDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(56))
        lay.addWidget(logo)
        lay.addWidget(label(f"{APP_NAME} {APP_VERSION}", "PageTitle"))
        lay.addWidget(label("Offline pharmacy management — inventory, batches, sales, receipts and profit.", "Muted", wrap=True))
        lay.addSpacing(6)
        lay.addWidget(label("<b>Works completely offline.</b> No internet, accounts, telemetry or cloud. "
                            "All data stays on this computer.", wrap=True))
        lay.addWidget(label(f"Database: {ctx.db.path}", "Muted", wrap=True))
        lay.addWidget(label(f"Backups: {ctx.paths.backups}", "Muted", wrap=True))
        lay.addSpacing(6)
        lay.addWidget(label("Keyboard: Ctrl+N new sale · Ctrl+F search · Ctrl+S save · Ctrl+P print receipt · "
                            "F1–F10 switch screens · Esc close dialog", "Muted", wrap=True))
        close = button("Close", variant="primary")
        close.clicked.connect(self.accept)
        lay.addLayout(hbox(None, close))
