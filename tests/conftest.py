from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.context import AppContext  # noqa: E402
from app.services.medicine_service import MedicineInput  # noqa: E402
from app.services.purchase_service import StockLine  # noqa: E402


@pytest.fixture
def ctx(tmp_path):
    context = AppContext(home=tmp_path)
    yield context
    context.close()


@pytest.fixture
def make_medicine(ctx):
    def _make(code="XX101", name="Paracetamol", generic="Acetaminophen", category="Pain Relief", reorder=0, **kw):
        return ctx.medicines.create(MedicineInput(code=code, name=name, generic_name=generic, category=category,
                                                  manufacturer=kw.pop("manufacturer", "Healix Labs"),
                                                  reorder_level=reorder, **kw))
    return _make


@pytest.fixture
def add_stock(ctx):
    def _add(medicine_id, qty=10, cost="80", price="100", batch="B1", expiry_days=365, purchase_days_ago=10,
             supplier="ABC Pharmaceuticals"):
        today = date.today()
        return ctx.purchases.add_stock(
            supplier, "INV-1", today - timedelta(days=purchase_days_ago),
            [StockLine(medicine_id, batch, today + timedelta(days=expiry_days), qty, cost, price)],
        )
    return _add
