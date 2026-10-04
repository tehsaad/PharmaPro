"""PharmaPro must work with no network at all.

Networking is disabled at the socket level for these tests; any attempt by
the app (or a library it uses) to reach the network makes the test fail.
"""
from __future__ import annotations

import os
import socket
from datetime import date, timedelta

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class NetworkUsed(AssertionError):
    pass


@pytest.fixture
def no_network(monkeypatch):
    def blocked(*_a, **_k):
        raise NetworkUsed("PharmaPro attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    yield


def test_full_workflow_without_network(no_network, ctx, tmp_path):
    from app.services import sample_data
    from app.services.sales_service import CartLine

    sample_data.seed(ctx, days_of_sales=10)
    med = ctx.medicines.find_by_code("XX101")
    res = ctx.sales.complete_sale([CartLine(med.id, 2)], discount=5)
    sale = ctx.sales.get(res.sale_id)
    data = ctx.receipts.build(sale)
    ctx.receipts.render_pdf(data, tmp_path / "r.pdf")
    ctx.receipts.render_html(data)
    today = date.today()
    from app.services.reporting_service import REPORT_TYPES
    for name in REPORT_TYPES:
        rep = ctx.reports.build(name, today - timedelta(days=30), today)
        ctx.reports.export_pdf(rep, tmp_path / f"{name}.pdf")
        ctx.reports.export_csv(rep, tmp_path / f"{name}.csv")
    ctx.analytics.timeseries(today - timedelta(days=30), today)
    backup = ctx.backups.create_backup()
    ctx.backups.restore(backup)
    assert ctx.profit.summary(today, today).sales_count >= 1


def test_ui_without_network(no_network, ctx):
    from PySide6.QtWidgets import QApplication

    from app.services import sample_data
    from app.ui.main_window import BOTTOM, NAV, MainWindow
    from app.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    sample_data.seed(ctx, days_of_sales=5)
    w = MainWindow(ctx)
    w.show()
    for key, *_ in NAV + BOTTOM:
        w.navigate(key)
        app.processEvents()
    w.close()
