"""Sales / POS: scan or type, build the cart, complete the sale, print the receipt.

The cart is re-validated against live stock (FEFO, expiry, quantities) every
time it changes, so problems are caught while the customer is still at the
counter - and validated once more inside the sale transaction itself.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.services.errors import PharmaError
from app.services.sales_service import CartLine, LinePreview
from app.ui import theme
from app.ui.base import Page
from app.ui.dialogs.common_dialogs import BatchPickerDialog, HeldSalesDialog, SaleDetailDialog
from app.ui.dialogs.receipt_dialog import ReceiptActions, SaleCompletedDialog
from app.ui.icons import pixmap
from app.ui.medicine_picker import MedicinePicker
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
    date_edit,
    field,
    from_qdate,
    hbox,
    label,
    money_edit,
    run_safely,
    show_exception,
    to_decimal,
    warn,
)
from app.utils.formatting import money


class SalesPage(Page):
    title = "Sales / POS"
    COLS = ["Code", "Medicine", "Batch", "Qty", "Unit Price", "Total", ""]

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.navigate = lambda *a, **k: None
        self.lines: list[CartLine] = []
        self.previews: list[LinePreview] = []
        self.receipts = ReceiptActions(ctx, self)
        self.last_sale_id: int | None = None

        header = PageHeader("Sales / POS", "Scan a barcode or type a medicine code, then press Enter.")
        self.held_btn = header.add_action(button("Held sales", "pause"))
        self.held_btn.clicked.connect(self.open_held)
        hist = header.add_action(button("Sales history", "clock"))
        hist.clicked.connect(self.open_history)
        self.body.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.body.addLayout(row, 1)

        # ----------------------------------------------------- left: scan + cart
        left = Card(padding=16)
        scan_row = QHBoxLayout()
        scan_icon = label()
        scan_icon.setPixmap(pixmap("scan", theme.ACCENT, 26))
        self.scan = MedicinePicker(ctx, "Scan barcode, or type code (e.g. XX101) or name…", scanner_mode=True)
        self.scan.setObjectName("ScanField")
        self.scan.picked.connect(lambda mid: self.add_medicine(mid, 1))
        self.scan.not_found.connect(lambda t: warn(self, "Medicine not found",
                                                   f"No active medicine matches “{t}”.\nCheck the code, or add it under Medicines."))
        self.qty_next = QSpinBox()
        self.qty_next.setRange(1, 100_000)
        self.qty_next.setPrefix("Qty  ")
        self.qty_next.setToolTip("Quantity added per scan")
        self.qty_next.setFixedWidth(110)
        scan_row.addWidget(scan_icon)
        scan_row.addWidget(self.scan, 1)
        scan_row.addWidget(self.qty_next)
        left.add(scan_row)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i, w in enumerate([90, 0, 140, 150, 115, 120, 44]):
            if w:
                self.table.setColumnWidth(i, w)
        self.table.doubleClicked.connect(lambda idx: self.choose_batch(idx.row()))
        left.add(self.table, 1)

        self.empty_hint = label("The cart is empty. Scan or type a medicine code above to start a sale.", "Muted")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        left.add(self.empty_hint)

        self.btn_remove = button("Remove item", "trash", tooltip="Delete")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_batch = button("Choose batch", "layers", tooltip="Sell from a specific batch instead of automatic FEFO")
        self.btn_batch.clicked.connect(lambda: self.choose_batch(self.table.currentRow()))
        self.btn_clear = button("Clear sale", "x")
        self.btn_clear.clicked.connect(self.clear_sale)
        self.btn_hold = button("Hold sale", "pause")
        self.btn_hold.clicked.connect(self.hold_sale)
        left.add(hbox(self.btn_remove, self.btn_batch, None, self.btn_hold, self.btn_clear))
        row.addWidget(left, 3)

        # ----------------------------------------------------- right: totals
        right = QFrame()
        right.setObjectName("TotalsPanel")
        right.setFixedWidth(360)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(22, 22, 22, 22)
        rl.setSpacing(10)
        rl.addWidget(label("CURRENT SALE"))
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        self.lbl_items = label("0")
        self.lbl_subtotal = label(money(0))
        for w in (self.lbl_items, self.lbl_subtotal):
            w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            w.setStyleSheet("color: white; font-weight: 600; font-size: 11pt;")
        grid.addWidget(label("Items"), 0, 0)
        grid.addWidget(self.lbl_items, 0, 1)
        grid.addWidget(label("Subtotal"), 1, 0)
        grid.addWidget(self.lbl_subtotal, 1, 1)
        self.discount = money_edit()
        self.discount.valueChanged.connect(self._update_totals)
        grid.addWidget(label("Discount"), 2, 0)
        grid.addWidget(self.discount, 2, 1)
        rl.addLayout(grid)
        rl.addSpacing(6)
        rl.addWidget(label("TOTAL"))
        self.lbl_total = label(money(0), "GrandTotal")
        self.lbl_total.setAlignment(Qt.AlignRight)
        rl.addWidget(self.lbl_total)
        line = QFrame()
        line.setStyleSheet("background: #2B4466; max-height: 1px;")
        rl.addWidget(line)
        cash_grid = QGridLayout()
        cash_grid.setVerticalSpacing(10)
        self.received = money_edit()
        self.received.setToolTip("Optional: cash handed over by the customer")
        self.received.valueChanged.connect(self._update_totals)
        self.lbl_change = label(money(0))
        self.lbl_change.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_change.setStyleSheet("color: white; font-weight: 700; font-size: 13pt;")
        cash_grid.addWidget(label("Cash received"), 0, 0)
        cash_grid.addWidget(self.received, 0, 1)
        cash_grid.addWidget(label("Change"), 1, 0)
        cash_grid.addWidget(self.lbl_change, 1, 1)
        rl.addLayout(cash_grid)
        rl.addStretch(1)
        self.complete_btn = button("Complete Sale", "check", "big", "Ctrl+Enter")
        self.complete_btn.setMinimumHeight(56)
        self.complete_btn.clicked.connect(self.complete_sale)
        rl.addWidget(self.complete_btn)
        self.print_btn = button("Print last receipt", "printer", "onDark", "Ctrl+P")
        self.print_btn.clicked.connect(self.handle_print)
        rl.addWidget(self.print_btn)
        rl.addWidget(label("Ctrl+N new sale · Ctrl+Enter complete\nDel remove item · Ctrl+P print", wrap=True))
        row.addWidget(right)

        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(seq), self, activated=self.complete_sale)
        QShortcut(QKeySequence(Qt.Key_Delete), self.table, activated=self.remove_selected)
        self._render()

    # ---------------------------------------------------------------- page hooks
    def refresh(self) -> None:
        self.scan.reload()
        self._update_held()
        if self.lines:
            self._apply(list(self.lines), silent=True)
        self.scan.setFocus()

    def focus_search(self) -> bool:
        self.scan.setFocus()
        self.scan.selectAll()
        return True

    def handle_print(self) -> bool:
        sale_id = self.last_sale_id
        if sale_id is None:
            last = self.ctx.sales.last_sale()
            sale_id = last.id if last else None
        if sale_id is None:
            warn(self, "No receipt yet", "Complete a sale first, then its receipt can be printed.")
            return True
        dlg = SaleDetailDialog(self.ctx, sale_id, self, on_print=self._receipt_menu, show_profit=False)
        dlg.exec()
        return True

    def new_sale(self) -> None:
        if self.lines and not confirm(self, "Start a new sale?",
                                      "The current cart will be cleared. Use “Hold sale” if you want to keep it.",
                                      "Start new sale"):
            return
        self._reset()

    # ---------------------------------------------------------------- cart ops
    def _apply(self, new_lines: list[CartLine], silent: bool = False) -> bool:
        """Validate a candidate cart against live stock; keep the old cart if invalid."""
        try:
            previews = self.ctx.sales.preview(new_lines) if new_lines else []
        except PharmaError as exc:
            if not silent:
                show_exception(self, exc)
                self.scan.setFocus()
            else:
                # stock changed elsewhere (e.g. restore) - drop lines that can no longer be sold
                Toast.show_message(self, str(exc).split("\n")[0], "warn", 5000)
                return False
            return False
        except Exception as exc:  # noqa: BLE001
            show_exception(self, exc)
            return False
        self.lines = new_lines
        self.previews = previews
        self._render()
        return True

    def add_medicine(self, medicine_id: int, qty: int | None = None) -> None:
        qty = self.qty_next.value() if qty in (None, 1) else qty
        new = [CartLine(l.medicine_id, l.quantity, l.batch_id) for l in self.lines]
        for i, l in enumerate(new):
            if l.medicine_id == medicine_id and l.batch_id is None:
                new[i] = CartLine(medicine_id, l.quantity + qty)  # same item scanned again: increase qty
                target = i
                break
        else:
            new.append(CartLine(medicine_id, qty))
            target = len(new) - 1
        if self._apply(new):
            self.table.selectRow(target)
        self.qty_next.setValue(1)
        self.scan.setFocus()

    def set_quantity(self, row: int, qty: int) -> None:
        if not (0 <= row < len(self.lines)) or self.lines[row].quantity == qty:
            return
        new = [CartLine(l.medicine_id, l.quantity, l.batch_id) for l in self.lines]
        new[row] = CartLine(new[row].medicine_id, qty, new[row].batch_id)
        if not self._apply(new):
            self._render()  # restore the previous quantity in the spin box

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        self.remove_row(row)

    def remove_row(self, row: int) -> None:
        if 0 <= row < len(self.lines):
            new = self.lines[:row] + self.lines[row + 1:]
            self._apply(new)
            self.scan.setFocus()

    def choose_batch(self, row: int) -> None:
        if not (0 <= row < len(self.lines)):
            return
        line = self.lines[row]
        dlg = BatchPickerDialog(self.ctx, line.medicine_id, self, current=line.batch_id)
        if dlg.exec() and dlg.chosen is not None:
            batch_id = None if dlg.chosen == BatchPickerDialog.AUTO else dlg.chosen
            new = [CartLine(l.medicine_id, l.quantity, l.batch_id) for l in self.lines]
            new[row] = CartLine(line.medicine_id, line.quantity, batch_id)
            self._apply(new)

    def clear_sale(self) -> None:
        if self.lines and not confirm(self, "Clear this sale?", "Remove all items from the cart?", "Clear", danger=True):
            return
        self._reset()

    def _reset(self) -> None:
        self.lines, self.previews = [], []
        self.discount.setValue(0)
        self.received.setValue(0)
        self._render()
        self.scan.clear()
        self.scan.setFocus()

    # ---------------------------------------------------------------- render
    def _render(self) -> None:
        self.table.setRowCount(len(self.previews))
        for i, p in enumerate(self.previews):
            batch_text = p.batch_label if self.lines[i].batch_id else f"Auto · {p.batch_label}"
            unit = p.unit_price if not p.mixed_prices else p.unit_price
            values = [p.code, p.name, batch_text, None, money(unit) + (" avg" if p.mixed_prices else ""), money(p.total)]
            for c, v in enumerate(values):
                if v is None:
                    continue
                item = QTableWidgetItem(v)
                if c >= 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 1:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                if c == 2:
                    item.setToolTip("Double-click to choose a specific batch")
                    item.setForeground(Qt.darkGray)
                self.table.setItem(i, c, item)
            spin = QSpinBox()
            spin.setRange(1, 1_000_000)
            spin.setValue(p.quantity)
            spin.setKeyboardTracking(False)
            spin.setAlignment(Qt.AlignCenter)
            spin.setToolTip(p.unit)
            spin.valueChanged.connect(lambda v, row=i: self.set_quantity(row, v))
            minus = button("", "minus", tooltip="One less")
            minus.setObjectName("Stepper")
            minus.clicked.connect(lambda _=False, row=i, q=p.quantity: self.set_quantity(row, q - 1) if q > 1 else None)
            plus = button("", "plus", tooltip="One more")
            plus.setObjectName("Stepper")
            plus.clicked.connect(lambda _=False, row=i, q=p.quantity: self.set_quantity(row, q + 1))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(2, 4, 2, 4)
            hl.setSpacing(4)
            hl.addWidget(minus)
            hl.addWidget(spin, 1)
            hl.addWidget(plus)
            self.table.setCellWidget(i, 3, holder)
            rm = button("", "x", "ghost", "Remove item")
            rm.clicked.connect(lambda _=False, row=i: self.remove_row(row))
            self.table.setCellWidget(i, 6, rm)
        has = bool(self.previews)
        self.table.setVisible(True)
        self.empty_hint.setVisible(not has)
        for b in (self.btn_remove, self.btn_batch, self.btn_clear, self.btn_hold, self.complete_btn):
            b.setEnabled(has)
        self._update_totals()

    def _subtotal(self) -> Decimal:
        return sum((p.total for p in self.previews), Decimal("0.00"))

    def _update_totals(self, *_):
        subtotal = self._subtotal()
        discount = to_decimal(self.discount)
        over = discount > subtotal
        self.discount.setStyleSheet(f"border: 1.5px solid {theme.CRITICAL};" if over else "")
        total = max(subtotal - discount, Decimal("0"))
        self.lbl_items.setText(f"{sum(p.quantity for p in self.previews):,}")
        self.lbl_subtotal.setText(money(subtotal))
        self.lbl_total.setText(money(total))
        received = to_decimal(self.received)
        if received:
            change = received - total
            self.lbl_change.setText(money(change) if change >= 0 else f"Short {money(-change)}")
            self.lbl_change.setStyleSheet(f"color: {'white' if change >= 0 else '#FCA5A5'}; font-weight: 700; font-size: 13pt;")
        else:
            self.lbl_change.setText("—")
            self.lbl_change.setStyleSheet("color: white; font-weight: 700; font-size: 13pt;")

    # ---------------------------------------------------------------- complete
    def complete_sale(self) -> None:
        if not self.lines:
            return
        discount = to_decimal(self.discount)
        subtotal = self._subtotal()
        if discount > subtotal:
            warn(self, "Discount too large", "The discount cannot be more than the subtotal.")
            return
        received = to_decimal(self.received) or None
        if received is not None and received < subtotal - discount:
            warn(self, "Not enough cash", f"Cash received is less than the total of {money(subtotal - discount)}.")
            return
        res = run_safely(self, self.ctx.sales.complete_sale, list(self.lines), discount, None, received)
        if res is FAILED:
            # Stock may have changed: re-validate so the cart shows the current situation.
            self._apply(list(self.lines), silent=True)
            return
        self.last_sale_id = res.sale_id
        self._reset()
        Toast.show_message(self, f"Sale {res.receipt_number} completed — {money(res.total)}")
        if self.ctx.settings.get_bool("auto_print_prompt"):
            SaleCompletedDialog(self.ctx, res.sale_id, self).exec()
        self.scan.reload()
        self.scan.setFocus()

    # ---------------------------------------------------------------- hold
    def hold_sale(self) -> None:
        if not self.lines:
            return
        name, ok = QInputDialog.getText(self, "Hold sale", "Label for this sale (optional), e.g. customer's first name:")
        if not ok:
            return
        if run_safely(self, self.ctx.sales.hold, list(self.lines), to_decimal(self.discount), name.strip()) is FAILED:
            return
        self._reset()
        self._update_held()
        Toast.show_message(self, "Sale held — resume it from “Held sales”")

    def open_held(self) -> None:
        dlg = HeldSalesDialog(self.ctx, self)
        if dlg.exec() and dlg.chosen_id:
            if self.lines and not confirm(self, "Replace current cart?",
                                          "The current cart will be cleared to resume the held sale.", "Resume"):
                return
            res = run_safely(self, self.ctx.sales.resume, dlg.chosen_id)
            if res is not FAILED:
                lines, discount = res
                if self._apply(lines):
                    self.discount.setValue(float(discount))
                else:
                    Toast.show_message(self, "Some held items are no longer available in that quantity.", "warn")
        self._update_held()

    def _update_held(self) -> None:
        n = len(self.ctx.sales.held_sales())
        self.held_btn.setText(f"Held sales ({n})" if n else "Held sales")

    # ---------------------------------------------------------------- history
    def open_history(self) -> None:
        SalesHistoryDialog(self.ctx, self, self._receipt_menu).exec()

    def _receipt_menu(self, sale_id: int) -> None:
        SaleCompletedDialog(self.ctx, sale_id, self, completed=False).exec()


class SalesHistoryDialog(QDialog):
    def __init__(self, ctx: AppContext, parent, on_receipt):
        super().__init__(parent)
        self.ctx = ctx
        self.on_receipt = on_receipt
        self.setWindowTitle("Sales history")
        self.resize(980, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(label("Sales history", "PageTitle"))
        self.start = date_edit(date.today(), allow_future=False)
        self.end = date_edit(date.today(), allow_future=False)
        self.search = SearchField("Receipt number or medicine")
        go = button("Show", "search", "primary")
        go.clicked.connect(self._load)
        self.search.returnPressed.connect(self._load)
        self.start.dateChanged.connect(self._load)
        self.end.dateChanged.connect(self._load)
        lay.addLayout(hbox(field("From", self.start), field("To", self.end), field("Search", self.search), None, go))
        self.table = DataTable([
            Column("Receipt", lambda s: s.receipt_number, width=170, bold=True),
            Column("Date & Time", lambda s: s.sale_date, "datetime", width=190),
            Column("Subtotal", lambda s: s.subtotal, "money", width=110),
            Column("Discount", lambda s: s.discount, "money", width=100),
            Column("Total", lambda s: s.total, "money", width=110),
            Column("Profit", lambda s: s.gross_profit, "money", width=110),
            Column("Printed", lambda s: "Yes" if s.print_count else "No", width=80, stretch=True),
        ], "No sales in this period", "Change the dates or search.", "receipt", sort=None)
        self.table.activated.connect(self._open)
        lay.addWidget(self.table, 1)
        self.summary = label("", "Muted")
        view = button("View details", "eye")
        view.clicked.connect(lambda: self._open(self.table.selected()))
        receipt = button("Receipt…", "printer", "primary")
        receipt.clicked.connect(lambda: self._receipt(self.table.selected()))
        close = button("Close")
        close.clicked.connect(self.accept)
        lay.addLayout(hbox(self.summary, None, view, receipt, close))
        self._load()

    def _load(self, *_):
        start, end = from_qdate(self.start.date()), from_qdate(self.end.date())
        if end < start:
            start, end = end, start
        sales = self.ctx.sales.list(start, end, self.search.text())
        self.table.set_rows(sales)
        total = sum((s.total for s in sales), Decimal("0"))
        self.summary.setText(f"{len(sales)} sale(s) · {money(total)}")

    def _open(self, sale):
        if sale is not None:
            SaleDetailDialog(self.ctx, sale.id, self, on_print=self.on_receipt).exec()
            self._load()

    def _receipt(self, sale):
        if sale is not None:
            self.on_receipt(sale.id)
            self._load()
