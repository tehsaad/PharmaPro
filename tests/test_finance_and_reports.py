from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.analytics.analytics_service import PRESETS, resolve_range
from app.services.errors import ValidationError
from app.services.reporting_service import REPORT_TYPES
from app.services.sales_service import CartLine


def test_expense_add_and_total(ctx):
    today = date.today()
    ctx.expenses.add("Shop rent", "Rent", "45000", today)
    ctx.expenses.add("Electricity bill", "Electricity", "12000.50", today)
    assert ctx.expenses.total(today, today) == Decimal("57000.50")
    assert dict(ctx.expenses.by_category(today, today))["Rent"] == Decimal("45000.00")


@pytest.mark.parametrize("title,cat,amount,msg", [
    ("", "Rent", "100", "Title"),
    ("X", "Rent", "0", "greater than zero"),
    ("X", "Rent", "-10", "negative"),
    ("X", "Bogus", "10", "category"),
])
def test_expense_validation(ctx, title, cat, amount, msg):
    with pytest.raises(ValidationError, match=msg):
        ctx.expenses.add(title, cat, amount, date.today())


def test_expense_edit_and_delete(ctx):
    exp = ctx.expenses.add("Fuel", "Transportation", "1000", date.today())
    ctx.expenses.update(exp.id, "Fuel", "Transportation", "1500", date.today())
    assert ctx.expenses.total(date.today(), date.today()) == Decimal("1500.00")
    ctx.expenses.delete(exp.id)
    assert ctx.expenses.total(date.today(), date.today()) == Decimal("0.00")


def test_net_profit(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=100, cost="80", price="100")
    ctx.sales.complete_sale([CartLine(med.id, 10)])                 # profit 200
    ctx.sales.complete_sale([CartLine(med.id, 5)], discount="50")   # revenue 450, cost 400, profit 50
    ctx.expenses.add("Electricity", "Electricity", "100", date.today())
    s = ctx.profit.summary(date.today(), date.today())
    assert s.sales_count == 2
    assert s.revenue == Decimal("1450.00")
    assert s.cogs == Decimal("1200.00")
    assert s.gross_profit == Decimal("250.00")
    assert s.expenses == Decimal("100.00")
    assert s.net_profit == Decimal("150.00")
    assert s.average_sale == Decimal("725.00")


def test_profit_summary_respects_date_range(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=100, cost="80", price="100", purchase_days_ago=30)
    ctx.sales.complete_sale([CartLine(med.id, 1)], sale_date=datetime.now() - timedelta(days=10))
    ctx.sales.complete_sale([CartLine(med.id, 2)])
    today = date.today()
    assert ctx.profit.summary(today, today).revenue == Decimal("200.00")
    assert ctx.profit.summary(today - timedelta(days=15), today).revenue == Decimal("300.00")


def test_empty_period_summary_is_zero(ctx):
    s = ctx.profit.summary(date.today(), date.today())
    assert s.sales_count == 0 and s.revenue == 0 and s.average_sale == 0 and s.net_profit == 0


def test_presets_resolve():
    today = date(2026, 10, 4)
    assert resolve_range("Today", today) == (today, today)
    assert resolve_range("Yesterday", today) == (date(2026, 10, 3),) * 2
    assert resolve_range("This Week", today) == (date(2026, 9, 28), today)
    assert resolve_range("This Month", today) == (date(2026, 10, 1), today)
    assert resolve_range("Last Month", today) == (date(2026, 9, 1), date(2026, 9, 30))
    assert resolve_range("This Year", today) == (date(2026, 1, 1), today)
    assert "Custom Range" in PRESETS


def test_analytics_timeseries_and_top(ctx, make_medicine, add_stock):
    a = make_medicine(code="A1", name="Alpha", category="Pain Relief")
    b = make_medicine(code="B1", name="Beta", category="Antibiotic")
    add_stock(a.id, qty=100, cost="10", price="20", purchase_days_ago=30)
    add_stock(b.id, qty=100, cost="50", price="80", purchase_days_ago=30)
    ctx.sales.complete_sale([CartLine(a.id, 5)], sale_date=datetime.now() - timedelta(days=2))
    ctx.sales.complete_sale([CartLine(a.id, 3), CartLine(b.id, 1)])
    today = date.today()
    df = ctx.analytics.timeseries(today - timedelta(days=6), today)
    assert len(df) == 7  # every day present, including days without sales
    assert df["revenue"].sum() == pytest.approx(240.0)
    assert df["profit"].sum() == pytest.approx(110.0)
    top = ctx.analytics.top_selling(today - timedelta(days=6), today)
    assert [t.code for t in top] == ["A1", "B1"] and top[0].quantity == 8
    cats = dict(ctx.analytics.sales_by_category(today - timedelta(days=6), today))
    assert cats == {"Pain Relief": Decimal("160.00"), "Antibiotic": Decimal("80.00")}
    long = ctx.analytics.timeseries(today - timedelta(days=200), today)
    assert ctx.analytics.granularity(today - timedelta(days=200), today) == "month"
    assert long["revenue"].sum() == pytest.approx(240.0)


def test_all_reports_build_and_export(ctx, make_medicine, add_stock, tmp_path):
    med = make_medicine()
    add_stock(med.id, qty=30, cost="80", price="100")
    ctx.sales.complete_sale([CartLine(med.id, 3)])
    ctx.expenses.add("Rent", "Rent", "100", date.today())
    today = date.today()
    for name in REPORT_TYPES:
        report = ctx.reports.build(name, today - timedelta(days=30), today)
        assert report.columns
        csv_path = ctx.reports.export_csv(report, tmp_path / f"{name}.csv")
        pdf_path = ctx.reports.export_pdf(report, tmp_path / f"{name}.pdf")
        assert csv_path.stat().st_size > 0
        assert pdf_path.read_bytes()[:4] == b"%PDF"
    sales = ctx.reports.build("Sales Report", today, today)
    assert len(sales.rows) == 1 and sales.totals[-1] == Decimal("60.00")
    profit = ctx.reports.build("Profit Report", today, today)
    assert profit.totals[-1] == Decimal("-40.00")  # 60 gross - 100 expense
