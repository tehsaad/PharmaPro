from datetime import date
from decimal import Decimal

import pytest

from app.models import Medicine
from app.services import sample_data
from app.services.errors import BackupError, ValidationError
from app.services.sales_service import CartLine


def _sale(ctx, make_medicine, add_stock):
    med = make_medicine(strength="500 mg")
    add_stock(med.id, qty=20, batch="A", cost="80", price="100", expiry_days=100)
    add_stock(med.id, qty=20, batch="B", cost="85", price="100", expiry_days=200)
    res = ctx.sales.complete_sale([CartLine(med.id, 25)], discount="10")
    return ctx.sales.get(res.sale_id)


@pytest.mark.parametrize("paper", ["thermal_80", "thermal_58", "a4"])
def test_receipt_pdf(ctx, make_medicine, add_stock, tmp_path, paper):
    sale = _sale(ctx, make_medicine, add_stock)
    data = ctx.receipts.build(sale)
    # batch split with the same price is merged into one receipt line
    assert len(data.lines) == 1 and data.lines[0].quantity == 25
    assert data.total == Decimal("2490.00")
    path = ctx.receipts.render_pdf(data, tmp_path / "r.pdf", paper=paper)
    assert path.read_bytes()[:4] == b"%PDF"


def test_receipt_html_hides_profit(ctx, make_medicine, add_stock):
    sale = _sale(ctx, make_medicine, add_stock)
    html = ctx.receipts.render_html(ctx.receipts.build(sale))
    assert sale.receipt_number in html
    assert "Thank you for your purchase." in html
    assert "profit" not in html.lower() and "cost" not in html.lower()


def test_print_count_tracked(ctx, make_medicine, add_stock):
    sale = _sale(ctx, make_medicine, add_stock)
    assert ctx.sales.mark_printed(sale.id) == 1
    assert ctx.sales.mark_printed(sale.id) == 2


def test_backup_and_restore(ctx, make_medicine):
    make_medicine(code="KEEP1", name="Keep me")
    backup = ctx.backups.create_backup()
    assert backup.name.startswith("PharmaPro_Backup_") and backup.suffix == ".db"
    make_medicine(code="LATER", name="Added after backup")
    assert len(ctx.medicines.search("")) == 2

    safety = ctx.backups.restore(backup)
    assert safety.exists()
    codes = [m.code for m in ctx.medicines.search("")]
    assert codes == ["KEEP1"]
    # the app keeps working normally after a restore
    make_medicine(code="NEW1", name="New after restore")
    assert len(ctx.medicines.search("")) == 2
    kinds = {b.kind for b in ctx.backups.list_backups()}
    assert {"Manual", "Before restore"} <= kinds


def test_restore_rejects_invalid_files(ctx, tmp_path):
    bad = tmp_path / "not_a_db.db"
    bad.write_text("hello")
    with pytest.raises(BackupError):
        ctx.backups.restore(bad)
    with pytest.raises(BackupError):
        ctx.backups.restore(tmp_path / "missing.db")
    import sqlite3
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("create table x(y)").connection.commit()
    with pytest.raises(BackupError, match="not a PharmaPro backup"):
        ctx.backups.restore(other)


def test_auto_backup_once_per_day(ctx):
    assert ctx.backups.auto_backup() is not None
    assert ctx.backups.auto_backup() is None


def test_settings_roundtrip(ctx):
    ctx.settings.update({"pharmacy_name": "City Pharmacy", "currency_symbol": "PKR", "low_stock_threshold": "7"})
    assert ctx.settings.get("pharmacy_name") == "City Pharmacy"
    assert ctx.settings.low_stock_threshold == 7
    with pytest.raises(ValidationError):
        ctx.settings.update({"pharmacy_name": ""})
    with pytest.raises(ValidationError):
        ctx.settings.update({"low_stock_threshold": "abc"})


def test_sample_data_seed(ctx):
    result = sample_data.seed(ctx)
    assert result["medicines"] >= 10 and result["sales"] > 50
    with ctx.db.read() as s:
        assert s.query(Medicine).count() == result["medicines"]
    buckets = ctx.inventory.expiry_buckets()
    assert buckets["expired"] >= 1 and buckets["90"] >= 1
    summary = ctx.profit.summary(date(2000, 1, 1), date.today())
    assert summary.revenue > 0 and summary.gross_profit > 0
    with pytest.raises(ValidationError):
        sample_data.seed(ctx)
