"""Customer receipts: PDF (ReportLab) and HTML (for Qt print preview / printing).

Receipts never show cost or profit - those are for the owner only.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models import Sale
from app.services.settings_service import SettingsService
from app.utils.formatting import money

PAPER_WIDTH_MM = {"thermal_80": 80, "thermal_58": 58}


@dataclass
class ReceiptLine:
    name: str
    quantity: int
    unit_price: Decimal
    total: Decimal


@dataclass
class ReceiptData:
    pharmacy_name: str
    address: str
    phone: str
    email: str
    license_number: str
    receipt_number: str
    sale_date: datetime
    lines: list[ReceiptLine] = field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    amount_received: Decimal | None = None
    footer: str = ""
    currency: str = "Rs."

    @property
    def change(self) -> Decimal | None:
        if self.amount_received is None:
            return None
        return self.amount_received - self.total

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)


class ReceiptService:
    def __init__(self, settings: SettingsService, receipts_dir: Path):
        self.settings = settings
        self.receipts_dir = Path(receipts_dir)

    def build(self, sale: Sale) -> ReceiptData:
        cfg = self.settings.all()
        # Merge batch-level sale items back into one line per medicine and price.
        merged: dict[tuple[int, Decimal], ReceiptLine] = {}
        for item in sale.items:
            label = item.medicine.name
            if item.medicine.strength:
                label = f"{label} {item.medicine.strength}"
            key = (item.medicine_id, item.selling_price)
            if key in merged:
                merged[key].quantity += item.quantity
                merged[key].total += item.total
            else:
                merged[key] = ReceiptLine(label, item.quantity, item.selling_price, item.total)
        return ReceiptData(
            pharmacy_name=cfg["pharmacy_name"], address=cfg["address"], phone=cfg["phone"], email=cfg["email"],
            license_number=cfg.get("license_number", ""), receipt_number=sale.receipt_number,
            sale_date=sale.sale_date, lines=list(merged.values()), subtotal=sale.subtotal,
            discount=sale.discount, total=sale.total, amount_received=sale.amount_received,
            footer=cfg["receipt_footer"], currency=cfg["currency_symbol"],
        )

    # ------------------------------------------------------------------ PDF
    def default_pdf_path(self, data: ReceiptData) -> Path:
        return self.receipts_dir / f"{data.receipt_number}.pdf"

    def render_pdf(self, data: ReceiptData, path: Path | None = None, paper: str | None = None) -> Path:
        paper = paper or self.settings.get("receipt_paper")
        path = Path(path) if path else self.default_pdf_path(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        if paper in PAPER_WIDTH_MM:
            self._render_thermal(data, path, PAPER_WIDTH_MM[paper])
        else:
            self._render_a4(data, path)
        return path

    def _render_thermal(self, data: ReceiptData, path: Path, width_mm: int) -> None:
        small = width_mm < 70
        fs = 7 if small else 8
        margin = 3 * mm
        width = width_mm * mm
        name_chars = 16 if small else 26
        # Pre-compute wrapped item names so the page height fits the content.
        wrapped = [_wrap(line.name, name_chars) for line in data.lines]
        header_lines = 3 + bool(data.address) + bool(data.phone) + bool(data.email) + bool(data.license_number)
        body_lines = sum(len(w) + 1 for w in wrapped)
        footer_lines = 8 + len(_wrap(data.footer, name_chars + 10))
        height = (header_lines + body_lines + footer_lines) * (fs + 4) + 14 * mm
        c = canvas.Canvas(str(path), pagesize=(width, height))
        c.setTitle(f"Receipt {data.receipt_number}")
        y = height - 6 * mm
        cx = width / 2
        right = width - margin

        def line(text, size=fs, bold=False, align="center", x=None):
            nonlocal y
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            if align == "center":
                c.drawCentredString(cx, y, text)
            elif align == "right":
                c.drawRightString(x or right, y, text)
            else:
                c.drawString(x or margin, y, text)

        def advance(n=1.0):
            nonlocal y
            y -= (fs + 4) * n

        def rule():
            nonlocal y
            c.setDash(1, 2)
            c.line(margin, y + 3, right, y + 3)
            c.setDash()
            advance(0.6)

        line(data.pharmacy_name, fs + 3, bold=True); advance(1.3)
        for extra in (data.address, data.phone and f"Tel: {data.phone}", data.email,
                      data.license_number and f"Lic: {data.license_number}"):
            if extra:
                line(extra); advance()
        advance(0.3); rule()
        line(f"Receipt: {data.receipt_number}", align="left"); advance()
        line(f"Date: {data.sale_date:%d-%m-%Y}", align="left")
        line(f"Time: {data.sale_date:%I:%M %p}", align="right"); advance()
        rule()
        qty_x = width * (0.52 if small else 0.58)
        price_x = width * (0.74 if small else 0.78)
        line("Item", bold=True, align="left"); line("Qty", bold=True, align="right", x=qty_x)
        line("Price", bold=True, align="right", x=price_x); line("Total", bold=True, align="right"); advance()
        rule()
        cur = data.currency
        for item, parts in zip(data.lines, wrapped):
            for i, part in enumerate(parts):
                line(part, align="left")
                if i == 0:
                    line(str(item.quantity), align="right", x=qty_x)
                    line(f"{item.unit_price:,.2f}", align="right", x=price_x)
                    line(f"{item.total:,.2f}", align="right")
                advance()
        rule()

        def total_row(label, value, bold=False, size=fs):
            line(label, size, bold, align="left"); line(value, size, bold, align="right"); advance(1.15)

        total_row("Subtotal", money(data.subtotal, cur))
        if data.discount:
            total_row("Discount", "-" + money(data.discount, cur))
        total_row("TOTAL", money(data.total, cur), bold=True, size=fs + 2)
        if data.amount_received is not None:
            total_row("Cash", money(data.amount_received, cur))
            total_row("Change", money(data.change, cur))
        line(f"Items: {data.item_count}", align="left"); advance()
        rule(); advance(0.3)
        for part in _wrap(data.footer, name_chars + 10):
            line(part, bold=True); advance()
        c.showPage()
        c.save()

    def _render_a4(self, data: ReceiptData, path: Path) -> None:
        width, height = A4
        c = canvas.Canvas(str(path), pagesize=A4)
        c.setTitle(f"Receipt {data.receipt_number}")
        m = 20 * mm
        y = height - m
        c.setFont("Helvetica-Bold", 18)
        c.drawString(m, y, data.pharmacy_name)
        c.setFont("Helvetica", 10)
        for extra in (data.address, data.phone and f"Tel: {data.phone}", data.email,
                      data.license_number and f"License: {data.license_number}"):
            if extra:
                y -= 14
                c.drawString(m, y, extra)
        c.setFont("Helvetica-Bold", 14)
        c.drawRightString(width - m, height - m, "RECEIPT")
        c.setFont("Helvetica", 10)
        c.drawRightString(width - m, height - m - 16, data.receipt_number)
        c.drawRightString(width - m, height - m - 30, f"{data.sale_date:%d-%m-%Y  %I:%M %p}")
        y -= 28
        cols = [m, width * 0.58, width * 0.72, width - m]
        c.setFillColorRGB(0.93, 0.95, 0.96)
        c.rect(m - 4, y - 6, width - 2 * m + 8, 20, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(cols[0], y, "Medicine")
        c.drawRightString(cols[1], y, "Qty")
        c.drawRightString(cols[2], y, "Price")
        c.drawRightString(cols[3], y, "Total")
        c.setFont("Helvetica", 10)
        y -= 22
        for item in data.lines:
            if y < 60 * mm:
                c.showPage()
                y = height - m
                c.setFont("Helvetica", 10)
            c.drawString(cols[0], y, item.name[:60])
            c.drawRightString(cols[1], y, str(item.quantity))
            c.drawRightString(cols[2], y, f"{item.unit_price:,.2f}")
            c.drawRightString(cols[3], y, f"{item.total:,.2f}")
            y -= 16
        c.line(m, y + 6, width - m, y + 6)
        y -= 10
        rows = [("Subtotal", money(data.subtotal, data.currency))]
        if data.discount:
            rows.append(("Discount", "-" + money(data.discount, data.currency)))
        rows.append(("TOTAL", money(data.total, data.currency)))
        if data.amount_received is not None:
            rows += [("Cash", money(data.amount_received, data.currency)), ("Change", money(data.change, data.currency))]
        for label, value in rows:
            bold = label == "TOTAL"
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 10)
            c.drawRightString(cols[2], y, label)
            c.drawRightString(cols[3], y, value)
            y -= 18
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(width / 2, 25 * mm, data.footer)
        c.showPage()
        c.save()

    # ----------------------------------------------------------------- HTML
    def render_html(self, data: ReceiptData, paper: str | None = None) -> str:
        """Receipt as simple HTML for QTextDocument printing / preview."""
        paper = paper or self.settings.get("receipt_paper")
        thermal = paper in PAPER_WIDTH_MM
        e = html.escape
        cur = data.currency
        size = "8pt" if paper == "thermal_58" else ("9pt" if thermal else "11pt")
        head = "".join(
            f"<div>{e(x)}</div>"
            for x in (data.address, data.phone and f"Tel: {data.phone}", data.email,
                      data.license_number and f"Lic: {data.license_number}") if x
        )
        rows = "".join(
            f"<tr><td>{e(line.name)}</td><td align='right'>{line.quantity}</td>"
            f"<td align='right'>{line.unit_price:,.2f}</td><td align='right'>{line.total:,.2f}</td></tr>"
            for line in data.lines
        )
        totals = [("Subtotal", money(data.subtotal, cur))]
        if data.discount:
            totals.append(("Discount", "-" + money(data.discount, cur)))
        totals.append(("<b>TOTAL</b>", f"<b>{e(money(data.total, cur))}</b>"))
        if data.amount_received is not None:
            totals += [("Cash", money(data.amount_received, cur)), ("Change", money(data.change, cur))]
        total_rows = "".join(f"<tr><td>{label}</td><td align='right'>{value}</td></tr>" for label, value in totals)
        return f"""
<html><body style="font-family: 'DejaVu Sans', Arial, sans-serif; font-size:{size}; color:#000;">
<div align="center"><div style="font-size:150%; font-weight:bold;">{e(data.pharmacy_name)}</div>{head}</div>
<hr/>
<table width="100%"><tr><td>Receipt: <b>{e(data.receipt_number)}</b></td></tr>
<tr><td>Date: {data.sale_date:%d-%m-%Y} &nbsp; Time: {data.sale_date:%I:%M %p}</td></tr></table>
<hr/>
<table width="100%" cellspacing="0" cellpadding="1">
<tr><th align="left">Medicine</th><th align="right">Qty</th><th align="right">Price</th><th align="right">Total</th></tr>
{rows}
</table>
<hr/>
<table width="100%" cellspacing="0" cellpadding="1">{total_rows}</table>
<hr/>
<div align="center"><b>{e(data.footer)}</b></div>
</body></html>"""


def _wrap(text: str, width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], ""
    for word in words:
        if len(cur) + len(word) + (1 if cur else 0) <= width:
            cur = f"{cur} {word}".strip()
        else:
            if cur:
                lines.append(cur)
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            cur = word
    if cur:
        lines.append(cur)
    return lines
