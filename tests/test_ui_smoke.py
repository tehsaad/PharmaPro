"""Offscreen UI tests: every screen opens, and the main workflows work through the widgets."""
from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.services import sample_data  # noqa: E402

MODULES_WITH_DIALOGS = [
    "app.ui.widgets", "app.ui.sales", "app.ui.add_stock", "app.ui.medicines", "app.ui.backup",
    "app.ui.settings", "app.ui.expenses", "app.ui.dialogs.receipt_dialog",
]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    from app.ui.theme import apply_theme
    apply_theme(app)
    yield app


@pytest.fixture
def messages(monkeypatch):
    """Replace modal message boxes with recorders so tests never block."""
    import importlib
    seen = []
    for name in MODULES_WITH_DIALOGS:
        mod = importlib.import_module(name)
        for fn in ("warn", "info", "error"):
            if hasattr(mod, fn):
                monkeypatch.setattr(mod, fn, lambda parent, title, text, _k=fn: seen.append((_k, title, text)))
        if hasattr(mod, "confirm"):
            monkeypatch.setattr(mod, "confirm", lambda *a, **k: True)
    return seen


@pytest.fixture
def window(qapp, ctx, messages):
    ctx.settings.update({"auto_print_prompt": "0"})
    sample_data.seed(ctx, days_of_sales=20)
    from app.ui.main_window import MainWindow
    w = MainWindow(ctx)
    w.show()
    yield w
    w.pages["sales"].lines = []
    w.pages["add_stock"].rows = []
    w.close()


def test_every_page_opens(window):
    from app.ui.main_window import BOTTOM, NAV
    for key, *_ in NAV + BOTTOM:
        window.navigate(key)
        assert window.current_page() is window.pages[key]
    window.navigate("inventory", filter="Expired")
    assert window.pages["inventory"].table.proxy.rowCount() >= 1


def test_dashboard_shows_numbers(window):
    window.navigate("dashboard")
    page = window.pages["dashboard"]
    assert page.c_stock.value.text().startswith("Rs.")
    assert page.alerts.count() > 0


def test_pos_sale_through_ui(window, ctx, messages):
    window.navigate("sales")
    pos = window.pages["sales"]
    med = ctx.medicines.find_by_code("XX101")
    before = ctx.sales.available_quantity(med.id)
    # Simulate a barcode scanner: type the code and press Enter.
    pos.scan.setText("XX101")
    pos.scan.returnPressed.emit()
    pos.scan.setText("xx101")  # same item scanned again -> quantity 2
    pos.scan.returnPressed.emit()
    assert len(pos.lines) == 1 and pos.lines[0].quantity == 2
    pos.discount.setValue(5)
    pos.complete_sale()
    assert pos.lines == []
    assert ctx.sales.available_quantity(med.id) == before - 2
    last = ctx.sales.last_sale()
    assert last.discount == Decimal("5.00") and last.items[0].quantity == 2


def test_pos_blocks_oversell(window, ctx, messages):
    pos = window.pages["sales"]
    window.navigate("sales")
    med = ctx.medicines.find_by_code("AMX101")
    available = ctx.sales.available_quantity(med.id)
    pos.add_medicine(med.id, 1)
    pos.set_quantity(0, available + 5)
    assert pos.lines[0].quantity == 1  # rejected, previous quantity kept
    assert any("Insufficient stock" in m[1] or "Insufficient" in m[2] for m in messages)


def test_pos_blocks_expired_only_stock(window, ctx, messages):
    pos = window.pages["sales"]
    window.navigate("sales")
    pos.lines, pos.previews = [], []
    med = ctx.medicines.find_by_code("BND001")
    # sell all good stock of the bandage so only the expired lot remains
    good = ctx.sales.available_quantity(med.id)
    from app.services.sales_service import CartLine
    if good:
        ctx.sales.complete_sale([CartLine(med.id, good)])
    pos.add_medicine(med.id, 1)
    assert pos.lines == []
    assert any(m[1] == "Expired medicine" for m in messages)


def test_add_stock_through_ui(window, ctx, messages):
    window.navigate("add_stock")
    page = window.pages["add_stock"]
    med = ctx.medicines.find_by_code("VIT201")
    before = ctx.sales.available_quantity(med.id)
    page.supplier.setCurrentText("Test Supplier")
    page.invoice.setText("INV-UI-1")
    page._medicine_chosen(med.id)
    page.batch.setText("ui-batch-1")
    from app.ui.widgets import to_qdate
    page.expiry.setDate(to_qdate(date.today() + timedelta(days=500)))
    page.qty.setValue(40)
    page.cost.setValue(41)
    page.price.setValue(70)
    page._add_line()
    assert len(page.rows) == 1
    page.handle_save()
    assert page.rows == []
    assert ctx.sales.available_quantity(med.id) == before + 40
    assert any(b.batch_number == "UI-BATCH-1" for b in ctx.medicines.batches(med.id))


def test_medicine_search_filters_table(window):
    window.navigate("medicines")
    page = window.pages["medicines"]
    page.status.setCurrentIndex(0)
    page.search.setText("para")
    page._apply_filters()
    assert page.table.proxy.rowCount() == 1


def test_reports_and_analytics_render(window):
    window.navigate("reports")
    rp = window.pages["reports"]
    for row in range(rp.list.count()):
        rp.list.setCurrentRow(row)
        assert rp.report is not None
    window.navigate("analytics")
    ap = window.pages["analytics"]
    ap.range.combo.setCurrentText("This Year")
    assert ap.k_count.value.text() != "—"


def test_backup_page_backup_now(window, ctx):
    window.navigate("backup")
    page = window.pages["backup"]
    page.backup_now()
    assert page.table.model.rowCount() >= 1
