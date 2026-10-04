"""Receipt actions: preview, print, save as PDF. Guards against accidental double printing."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog, QVBoxLayout

from app.context import AppContext
from app.printing import receipt_printer
from app.ui.widgets import FAILED, Toast, button, confirm, hbox, label, run_safely, warn
from app.utils.formatting import money

log = logging.getLogger(__name__)


class ReceiptActions:
    """Shared receipt logic used by the POS screen and sale history."""

    def __init__(self, ctx: AppContext, parent):
        self.ctx = ctx
        self.parent = parent

    def _data(self, sale_id: int):
        sale = self.ctx.sales.get(sale_id)
        return sale, self.ctx.receipts.build(sale)

    def print(self, sale_id: int, confirm_reprint: bool = True) -> bool:
        sale, data = self._data(sale_id)
        if confirm_reprint and sale.print_count > 0:
            if not confirm(self.parent, "Print again?",
                           f"Receipt {sale.receipt_number} has already been printed "
                           f"{sale.print_count} time(s).\n\nPrint another copy?", "Print copy"):
                return False
        if not receipt_printer.printers_available():
            if confirm(self.parent, "No printer found",
                       "No printer is installed on this computer.\n\nSave the receipt as a PDF instead?", "Save PDF"):
                return self.save_pdf(sale_id)
            return False
        paper = self.ctx.settings.get("receipt_paper")
        html = self.ctx.receipts.render_html(data, paper)
        ok = run_safely(self.parent, receipt_printer.print_receipt, self.parent, html, paper,
                        self.ctx.settings.get("printer_name"), ask=False)
        if ok is FAILED:
            warn(self.parent, "Printer problem",
                 "The receipt could not be printed. Please check that the printer is switched on and has paper.\n\n"
                 "You can save the receipt as a PDF instead.")
            return False
        if ok:
            self.ctx.sales.mark_printed(sale_id)
            Toast.show_message(self.parent, f"Receipt {sale.receipt_number} sent to printer")
        return bool(ok)

    def preview(self, sale_id: int) -> bool:
        sale, data = self._data(sale_id)
        paper = self.ctx.settings.get("receipt_paper")
        html = self.ctx.receipts.render_html(data, paper)
        printed = run_safely(self.parent, receipt_printer.preview, self.parent, html, paper,
                             self.ctx.settings.get("printer_name"))
        if printed is True:
            self.ctx.sales.mark_printed(sale_id)
        return printed is True

    def save_pdf(self, sale_id: int, ask_path: bool = True) -> bool:
        sale, data = self._data(sale_id)
        default = self.ctx.receipts.default_pdf_path(data)
        path = default
        if ask_path:
            chosen, _ = QFileDialog.getSaveFileName(self.parent, "Save receipt as PDF", str(default), "PDF files (*.pdf)")
            if not chosen:
                return False
            path = Path(chosen if chosen.lower().endswith(".pdf") else chosen + ".pdf")
        res = run_safely(self.parent, self.ctx.receipts.render_pdf, data, path)
        if res is FAILED:
            return False
        Toast.show_message(self.parent, f"Receipt saved: {Path(res).name}")
        open_file(res)
        return True


def open_file(path) -> None:
    """Open a local file with the default application (never a network location)."""
    try:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
    except Exception:  # pragma: no cover - desktop integration varies
        log.warning("Could not open %s", path)


class SaleCompletedDialog(QDialog):
    """Shown once after a sale is completed. Printing happens only on request."""

    def __init__(self, ctx: AppContext, sale_id: int, parent=None, completed: bool = True):
        super().__init__(parent)
        self.ctx = ctx
        self.sale_id = sale_id
        self.actions = ReceiptActions(ctx, self)
        sale = ctx.sales.get(sale_id)
        title = "Sale completed" if completed else "Receipt"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(8)
        lay.addWidget(label(title, "PageTitle"))
        lay.addWidget(label(f"Receipt {sale.receipt_number}", "Muted"))
        total = label(money(sale.total), "StatValue")
        lay.addWidget(total)
        if sale.amount_received is not None:
            lay.addWidget(label(f"Cash received {money(sale.amount_received)}   ·   "
                                f"<b>Change {money(sale.amount_received - sale.total)}</b>"))
        lay.addSpacing(10)
        self.print_btn = button("Print receipt", "printer", "primary")
        self.print_btn.setDefault(True)
        self.print_btn.clicked.connect(self._print)
        preview = button("Preview", "eye")
        preview.clicked.connect(self._preview)
        pdf = button("Save PDF", "download")
        pdf.clicked.connect(lambda: self.actions.save_pdf(sale_id))
        done = button("Done (no receipt)" if completed else "Close")
        done.clicked.connect(self.accept)
        lay.addLayout(hbox(self.print_btn, preview, pdf, None, done))

    def _print(self):
        # A completed-sale print is the first print, so no "print again" question.
        if self.actions.print(self.sale_id, confirm_reprint=True):
            self.accept()

    def _preview(self):
        if self.actions.preview(self.sale_id):
            self.accept()
