"""Physical printing and print preview of receipts through Qt's print system.

Works with any printer installed in the operating system, including USB thermal
receipt printers (80 mm / 58 mm), with no network access.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo, QPrintPreviewDialog

log = logging.getLogger(__name__)

THERMAL_WIDTH_MM = {"thermal_80": 80, "thermal_58": 58}


def printers_available() -> list[str]:
    return [p.printerName() for p in QPrinterInfo.availablePrinters()]


def default_printer_name() -> str:
    info = QPrinterInfo.defaultPrinter()
    return "" if info.isNull() else info.printerName()


def _configure(printer: QPrinter, paper: str, printer_name: str = "") -> None:
    if printer_name and printer_name in printers_available():
        printer.setPrinterName(printer_name)
    if paper in THERMAL_WIDTH_MM:
        size = QPageSize(QSizeF(THERMAL_WIDTH_MM[paper], 297), QPageSize.Millimeter, "Receipt roll")
        layout = QPageLayout(size, QPageLayout.Portrait, QMarginsF(3, 3, 3, 3), QPageLayout.Millimeter)
    else:
        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)
    printer.setPageLayout(layout)


def _document(html: str, printer: QPrinter) -> QTextDocument:
    doc = QTextDocument()
    doc.setDocumentMargin(2)
    doc.setHtml(html)
    rect = printer.pageLayout().paintRectPoints()
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    return doc


def preview(parent, html: str, paper: str, printer_name: str = "") -> bool:
    """Show a print preview. Returns True if the user printed from the preview."""
    printer = QPrinter(QPrinter.HighResolution)
    _configure(printer, paper, printer_name)
    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle("Receipt preview")
    dlg.resize(560, 760)
    dlg.paintRequested.connect(lambda p: _document(html, p).print_(p))
    return dlg.exec() == QPrintPreviewDialog.Accepted


def print_receipt(parent, html: str, paper: str, printer_name: str = "", ask: bool = False) -> bool:
    """Send the receipt to a printer. Returns True when it was sent."""
    printer = QPrinter(QPrinter.HighResolution)
    _configure(printer, paper, printer_name)
    if ask or not (printer_name or default_printer_name()):
        dlg = QPrintDialog(printer, parent)
        dlg.setWindowTitle("Print receipt")
        if dlg.exec() != QPrintDialog.Accepted:
            return False
    try:
        _document(html, printer).print_(printer)
    except Exception:  # pragma: no cover - depends on printer drivers
        log.exception("Printing failed")
        raise
    return True
