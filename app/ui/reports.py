from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem

from app.context import AppContext
from app.services.reporting_service import REPORT_TYPES, SNAPSHOT_REPORTS, Report, display
from app.ui.base import Page
from app.ui.dialogs.receipt_dialog import open_file
from app.ui.icons import icon
from app.ui.range_picker import RangePicker
from app.ui.widgets import FAILED, Card, Column, DataTable, PageHeader, SearchField, Toast, button, hbox, label, run_safely

REPORT_ICONS = {
    "Sales Report": "cart", "Purchase Report": "truck", "Stock Report": "package", "Profit Report": "trending",
    "Expense Report": "wallet", "Expiry Report": "hourglass", "Low Stock Report": "alert",
    "Top Selling Medicines": "chart",
}


class ReportsPage(Page):
    title = "Reports"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.report: Report | None = None
        header = PageHeader("Reports", "Business reports you can filter, sort, and export to PDF or CSV.")
        self.btn_csv = header.add_action(button("Export CSV", "download"))
        self.btn_csv.clicked.connect(lambda: self.export("csv"))
        self.btn_pdf = header.add_action(button("Export PDF", "file-text", "primary"))
        self.btn_pdf.clicked.connect(lambda: self.export("pdf"))
        self.body.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(16)
        side = Card(padding=10)
        side.setFixedWidth(250)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { border: none; } QListWidget::item { padding: 10px 8px; border-radius: 8px; border: none; }")
        for name in REPORT_TYPES:
            self.list.addItem(QListWidgetItem(icon(REPORT_ICONS[name], "#475569", 18), name))
        self.list.setCurrentRow(0)
        self.list.currentRowChanged.connect(lambda _r: self.refresh())
        side.add(self.list, 1)
        row.addWidget(side)

        main = Card()
        self.title_lbl = label("", "SectionTitle")
        self.subtitle_lbl = label("", "Muted")
        main.add(self.title_lbl)
        main.add(self.subtitle_lbl)
        self.range = RangePicker("This Month")
        self.range.changed.connect(lambda *_: self.refresh())
        self.search = SearchField("Search within this report   (Ctrl+F)")
        self.search.search.connect(self._search)
        main.add(hbox(self.range, None, self.search))
        self.table_holder = QHBoxLayout()
        self.table: DataTable | None = None
        main.add(self.table_holder, 1)
        self.totals = label("", "SectionTitle")
        self.totals.setWordWrap(True)
        main.add(self.totals)
        row.addWidget(main, 1)
        self.body.addLayout(row, 1)

    def refresh(self) -> None:
        name = REPORT_TYPES[max(self.list.currentRow(), 0)]
        self.range.setEnabled(name not in SNAPSHOT_REPORTS)
        start, end = self.range.range()
        report = run_safely(self, self.ctx.reports.build, name, start, end)
        if report is FAILED:
            return
        self.report = report
        self.title_lbl.setText(report.title)
        self.subtitle_lbl.setText(report.subtitle)
        cols = [
            Column(c, (lambda r, i=i: r[i]), "status" if c == "Status" else "auto",
                   align_right=i in report.numeric, bold=(i == 1 and c in ("Medicine", "Supplier", "Title")))
            for i, c in enumerate(report.columns)
        ]
        if self.table is not None:
            self.table.setParent(None)
            self.table.deleteLater()
        self.table = DataTable(cols, "No records", "Nothing matches this report for the selected period.", REPORT_ICONS[name], row_height=36, sort=None)
        hh = self.table.view.horizontalHeader()
        hh.setStretchLastSection(True)
        self.table_holder.addWidget(self.table)
        self.table.set_rows(report.rows)
        self.table.view.resizeColumnsToContents()
        for i in range(len(cols)):
            self.table.view.setColumnWidth(i, min(max(self.table.view.columnWidth(i) + 24, 80), 320))
        self._search(self.search.text())

    def _search(self, text: str) -> None:
        if self.table is None or self.report is None:
            return
        self.table.search(text)
        shown = self.table.proxy.rowCount()
        parts = [f"{shown:,} of {len(self.report.rows):,} rows"]
        if self.report.totals and not text:
            pairs = [(self.report.columns[i], v) for i, v in enumerate(self.report.totals) if v not in ("", None) and i > 0]
            parts += [f"{c}: {display(v)}" for c, v in pairs]
        self.totals.setText("   ·   ".join(parts))

    def focus_search(self) -> bool:
        self.search.setFocus()
        return True

    def handle_save(self) -> bool:
        self.export("pdf")
        return True

    def export(self, kind: str) -> None:
        if self.report is None or self.table is None:
            return
        rows = self.table.visible_objects()
        filtered = len(rows) != len(self.report.rows)
        stamp = date.today().strftime("%Y-%m-%d")
        default = self.ctx.paths.exports / f"{self.report.title.replace(' ', '_')}_{stamp}.{kind}"
        flt = "PDF files (*.pdf)" if kind == "pdf" else "CSV files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, f"Export {kind.upper()}", str(default), flt)
        if not path:
            return
        path = Path(path if path.lower().endswith(f".{kind}") else f"{path}.{kind}")
        fn = self.ctx.reports.export_pdf if kind == "pdf" else self.ctx.reports.export_csv
        res = run_safely(self, fn, self.report, path, rows if filtered else None)
        if res is not FAILED:
            Toast.show_message(self, f"Exported {path.name}")
            if kind == "pdf":
                open_file(path)
