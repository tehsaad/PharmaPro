"""Tabular business reports with CSV and PDF export."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.analytics.analytics_service import AnalyticsService
from app.services.expense_service import ExpenseService
from app.services.inventory_service import FILTER_ALL, InventoryService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.settings_service import SettingsService
from app.utils.formatting import fmt_date, fmt_datetime

REPORT_TYPES = [
    "Sales Report",
    "Purchase Report",
    "Stock Report",
    "Profit Report",
    "Expense Report",
    "Expiry Report",
    "Low Stock Report",
    "Top Selling Medicines",
]
# Reports that describe the current moment rather than a date range.
SNAPSHOT_REPORTS = {"Stock Report", "Expiry Report", "Low Stock Report"}


@dataclass
class Report:
    title: str
    subtitle: str
    columns: list[str]
    rows: list[list]
    numeric: set[int] = field(default_factory=set)
    totals: list | None = None


def display(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if isinstance(value, datetime):
        return fmt_datetime(value)
    if isinstance(value, date):
        return fmt_date(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


class ReportingService:
    def __init__(self, sales: SalesService, purchases: PurchaseService, inventory: InventoryService,
                 expenses: ExpenseService, analytics: AnalyticsService, settings: SettingsService):
        self.sales = sales
        self.purchases = purchases
        self.inventory = inventory
        self.expenses = expenses
        self.analytics = analytics
        self.settings = settings

    def build(self, report_type: str, start: date, end: date) -> Report:
        builders = {
            "Sales Report": self._sales,
            "Purchase Report": self._purchases,
            "Stock Report": self._stock,
            "Profit Report": self._profit,
            "Expense Report": self._expenses,
            "Expiry Report": self._expiry,
            "Low Stock Report": self._low_stock,
            "Top Selling Medicines": self._top,
        }
        if report_type not in builders:
            raise ValueError(report_type)
        report = builders[report_type](start, end)
        if report_type in SNAPSHOT_REPORTS:
            report.subtitle = f"As of {fmt_date(date.today())}"
        else:
            report.subtitle = f"{fmt_date(start)} – {fmt_date(end)}"
        return report

    def _sales(self, start, end) -> Report:
        sales = self.sales.list(start, end)
        rows = [
            [s.receipt_number, s.sale_date, s.subtotal, s.discount, s.total, s.cost_of_goods, s.gross_profit]
            for s in sales
        ]
        tot = [sum((r[i] for r in rows), Decimal("0.00")) for i in range(2, 7)]
        return Report("Sales Report", "", ["Receipt", "Date & Time", "Subtotal", "Discount", "Total", "Cost", "Profit"],
                      rows, {2, 3, 4, 5, 6}, [f"{len(rows)} sales", ""] + tot)

    def _purchases(self, start, end) -> Report:
        rows = []
        for p in self.purchases.list(start, end):
            rows.append([p.purchase_date, p.supplier, p.invoice_number or "—", p.total_amount])
        total = sum((r[3] for r in rows), Decimal("0.00"))
        return Report("Purchase Report", "", ["Date", "Supplier", "Invoice", "Amount"], rows, {3},
                      [f"{len(rows)} purchases", "", "", total])

    def _stock(self, start, end) -> Report:
        rows = [
            [r.code, r.medicine, r.category, r.batch_number, r.expiry_date, r.quantity_remaining,
             r.purchase_price, r.selling_price, r.stock_value, r.status]
            for r in self.inventory.stock_rows(FILTER_ALL)
        ]
        units = sum(r[5] for r in rows)
        value = sum((r[8] for r in rows), Decimal("0.00"))
        return Report("Stock Report", "", ["Code", "Medicine", "Category", "Batch", "Expiry", "Qty", "Cost", "Price", "Value", "Status"],
                      rows, {5, 6, 7, 8}, ["Total", "", "", "", "", units, "", "", value, ""])

    def _profit(self, start, end) -> Report:
        df = self.analytics.timeseries(start, end)
        gran = self.analytics.granularity(start, end)
        exp_by_period: dict[str, Decimal] = {}
        for e in self.expenses.list(start, end):
            key = e.date.strftime("%Y-%m-%d" if gran == "day" else "%Y-%m")
            exp_by_period[key] = exp_by_period.get(key, Decimal("0")) + e.amount
        rows = []
        for ts, r in df.iterrows():
            key = ts.strftime("%Y-%m-%d" if gran == "day" else "%Y-%m")
            revenue = Decimal(str(r["revenue"])).quantize(Decimal("0.01"))
            cost = Decimal(str(r["cost"])).quantize(Decimal("0.01"))
            gross = Decimal(str(r["profit"])).quantize(Decimal("0.01"))
            exp = exp_by_period.get(key, Decimal("0.00"))
            label = ts.date() if gran == "day" else ts.strftime("%b %Y")
            rows.append([label, int(r["count"]), revenue, cost, gross, exp, gross - exp])
        tot = [sum(r[1] for r in rows)] + [sum((r[i] for r in rows), Decimal("0.00")) for i in range(2, 7)]
        return Report("Profit Report", "", ["Period", "Sales", "Revenue", "Cost of Goods", "Gross Profit", "Expenses", "Net Profit"],
                      rows, {1, 2, 3, 4, 5, 6}, ["Total"] + tot)

    def _expenses(self, start, end) -> Report:
        rows = [[e.date, e.title, e.category, e.amount, e.description] for e in self.expenses.list(start, end)]
        return Report("Expense Report", "", ["Date", "Title", "Category", "Amount", "Description"], rows, {3},
                      [f"{len(rows)} expenses", "", "", sum((r[3] for r in rows), Decimal("0.00")), ""])

    def _expiry(self, start, end) -> Report:
        today = date.today()
        warn = self.settings.expiry_warning_days
        rows = []
        for r in self.inventory.stock_rows(FILTER_ALL, today):
            if r.batch_id and r.quantity_remaining > 0 and r.expiry_date and r.expiry_date <= today + timedelta(days=warn):
                days = (r.expiry_date - today).days
                rows.append([r.code, r.medicine, r.batch_number, r.expiry_date, "Expired" if days <= 0 else days,
                             r.quantity_remaining, r.stock_value, r.supplier])
        rows.sort(key=lambda x: x[3])
        return Report("Expiry Report", "", ["Code", "Medicine", "Batch", "Expiry", "Days Left", "Qty", "Value at Cost", "Supplier"],
                      rows, {4, 5, 6}, ["Total", "", "", "", "", sum(r[5] for r in rows), sum((r[6] for r in rows), Decimal("0.00")), ""])

    def _low_stock(self, start, end) -> Report:
        rows = []
        for m in self.inventory.low_stock():
            status = "Out of Stock" if m.sellable_stock == 0 else "Low Stock"
            rows.append([m.code, m.name, m.category, m.sellable_stock, self.inventory.reorder_point(m.reorder_level), status])
        return Report("Low Stock Report", "", ["Code", "Medicine", "Category", "In Stock", "Reorder Level", "Status"],
                      rows, {3, 4}, None)

    def _top(self, start, end) -> Report:
        rows = [[i, t.code, t.name, t.category, t.quantity, t.revenue, t.profit]
                for i, t in enumerate(self.analytics.top_selling(start, end, limit=0), start=1)]
        return Report("Top Selling Medicines", "", ["#", "Code", "Medicine", "Category", "Qty Sold", "Revenue", "Profit"],
                      rows, {0, 4, 5, 6}, None)

    # --------------------------------------------------------------- export
    @staticmethod
    def export_csv(report: Report, path: Path, rows: list[list] | None = None) -> Path:
        rows = report.rows if rows is None else rows
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel reads UTF-8
            w = csv.writer(fh)
            w.writerow(report.columns)
            for r in rows:
                w.writerow([_csv_value(v) for v in r])
            if report.totals and rows is report.rows:
                w.writerow([_csv_value(v) for v in report.totals])
        return path

    def export_pdf(self, report: Report, path: Path, rows: list[list] | None = None) -> Path:
        rows = report.rows if rows is None else rows
        path = Path(path)
        doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                                topMargin=12 * mm, bottomMargin=12 * mm, title=report.title)
        styles = getSampleStyleSheet()
        cell = styles["BodyText"].clone("cell", fontSize=8, leading=10)
        head = styles["BodyText"].clone("head", fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold")
        story = [
            Paragraph(f"<b>{self.settings.get('pharmacy_name')}</b>", styles["Title"]),
            Paragraph(f"{report.title} — {report.subtitle}", styles["Heading3"]),
            Paragraph(f"Generated {datetime.now():%d %b %Y %I:%M %p}", styles["Normal"]),
            Spacer(1, 6 * mm),
        ]
        data = [[Paragraph(c, head) for c in report.columns]]
        for r in rows:
            data.append([Paragraph(_xml(display(v)), cell) for v in r])
        if report.totals and rows is report.rows:
            data.append([Paragraph(f"<b>{_xml(display(v)) if v != '' else ''}</b>", cell) for v in report.totals])
        if len(data) == 1:
            data.append([Paragraph("No records for this period.", cell)] + [""] * (len(report.columns) - 1))
        table = Table(data, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i in report.numeric:
            style.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
        table.setStyle(TableStyle(style))
        story.append(table)
        doc.build(story)
        return path


def _csv_value(v):
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    return v


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
