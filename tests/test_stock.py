from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Batch, Purchase, PurchaseItem
from app.services.errors import ValidationError
from app.services.inventory_service import FILTER_EXPIRED, FILTER_EXPIRING, FILTER_LOW, FILTER_OUT
from app.services.purchase_service import StockLine
from app.utils.constants import STATUS_EXPIRED, STATUS_EXPIRING, STATUS_LOW, STATUS_NORMAL, STATUS_OUT


def count(ctx, model):
    with ctx.db.read() as s:
        return s.query(model).count()


def test_stock_addition_creates_batch(ctx, make_medicine, add_stock):
    med = make_medicine()
    result = add_stock(med.id, qty=100, cost="80", price="100", batch="p123")
    assert result.total_amount == Decimal("8000.00")
    batches = ctx.medicines.batches(med.id)
    assert len(batches) == 1
    b = batches[0]
    assert b.batch_number == "P123"
    assert b.quantity_received == b.quantity_remaining == 100
    assert b.purchase_price == Decimal("80.00")
    assert b.selling_price == Decimal("100.00")
    assert b.supplier == "ABC Pharmaceuticals"


def test_multiple_medicines_in_one_transaction(ctx, make_medicine):
    a = make_medicine(code="XX101", name="Paracetamol")
    b = make_medicine(code="AMX101", name="Amoxicillin")
    c = make_medicine(code="VIT201", name="Vitamin C")
    exp = date.today() + timedelta(days=400)
    res = ctx.purchases.add_stock("ABC Pharmaceuticals", "INV-1023", date.today(), [
        StockLine(a.id, "P123", exp, 100, "80", "100"),
        StockLine(b.id, "A441", exp, 50, "120", "160"),
        StockLine(c.id, "V221", exp, 200, "40", "70"),
    ])
    assert res.line_count == 3 and res.units == 350
    assert res.total_amount == Decimal("22000.00")
    purchase = ctx.purchases.get(res.purchase_id)
    assert purchase.invoice_number == "INV-1023"
    assert len(purchase.items) == 3
    assert count(ctx, Batch) == 3


def test_batches_preserve_different_purchase_prices(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, batch="A", cost="80", price="100")
    add_stock(med.id, batch="B", cost="85", price="105")
    prices = sorted((b.purchase_price, b.selling_price) for b in ctx.medicines.batches(med.id))
    assert prices == [(Decimal("80.00"), Decimal("100.00")), (Decimal("85.00"), Decimal("105.00"))]


def test_restocking_same_batch_increases_quantity(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, batch="A")
    add_stock(med.id, qty=5, batch="A", price="110")
    (b,) = ctx.medicines.batches(med.id)
    assert b.quantity_received == 15 and b.quantity_remaining == 15
    assert b.selling_price == Decimal("110.00")


def test_same_batch_with_different_cost_is_rejected(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, batch="A", cost="80")
    with pytest.raises(ValidationError, match="different purchase price"):
        add_stock(med.id, batch="A", cost="90")


def test_stock_transaction_rolls_back_entirely_on_error(ctx, make_medicine):
    a = make_medicine(code="A1", name="A")
    exp = date.today() + timedelta(days=300)
    with pytest.raises(Exception):
        ctx.purchases.add_stock("Supplier", "INV-9", date.today(), [
            StockLine(a.id, "OK1", exp, 10, "10", "12"),
            StockLine(999999, "BAD", exp, 10, "10", "12"),  # medicine does not exist
        ])
    assert count(ctx, Purchase) == 0
    assert count(ctx, PurchaseItem) == 0
    assert count(ctx, Batch) == 0


@pytest.mark.parametrize("qty,cost,price,expiry,msg", [
    (0, "10", "12", 300, "greater than zero"),
    (-5, "10", "12", 300, "greater than zero"),
    ("1.5", "10", "12", 300, "whole number"),
    (5, "-1", "12", 300, "cannot be negative"),
    (5, "10", "-2", 300, "cannot be negative"),
    (5, "abc", "12", 300, "must be a number"),
    (5, "10", "12", -3, "Expiry date must be after"),
])
def test_stock_validation(ctx, make_medicine, qty, cost, price, expiry, msg):
    med = make_medicine()
    with pytest.raises(ValidationError, match=msg):
        ctx.purchases.add_stock("Supplier", "", date.today(),
                                [StockLine(med.id, "B", date.today() + timedelta(days=expiry), qty, cost, price)])
    assert count(ctx, Batch) == 0


def test_invalid_expiry_text_rejected(ctx, make_medicine):
    med = make_medicine()
    with pytest.raises(ValidationError, match="not a valid date"):
        ctx.purchases.add_stock("S", "", date.today(), [StockLine(med.id, "B", "31-31-2030", 1, "1", "2")])


def test_month_only_expiry_means_end_of_month(ctx, make_medicine):
    med = make_medicine()
    ctx.purchases.add_stock("S", "", date.today(), [StockLine(med.id, "B", "2031-02", 1, "1", "2")])
    assert ctx.medicines.batches(med.id)[0].expiry_date == date(2031, 2, 28)


def test_empty_stock_entry_rejected(ctx):
    with pytest.raises(ValidationError, match="at least one medicine"):
        ctx.purchases.add_stock("S", "", date.today(), [])


def test_supplier_required(ctx, make_medicine):
    med = make_medicine()
    with pytest.raises(ValidationError, match="Supplier"):
        ctx.purchases.add_stock(" ", "", date.today(), [StockLine(med.id, "B", "2031-02", 1, "1", "2")])


def test_below_cost_warning_rows():
    rows = [StockLine(1, "A", "2030-01", 1, "100", "90"), StockLine(2, "B", "2030-01", 1, "100", "120")]
    from app.services.purchase_service import PurchaseService
    assert PurchaseService.below_cost_rows(rows) == [1]


def test_stock_statuses_and_filters(ctx, make_medicine, add_stock):
    normal = make_medicine(code="N1", name="Normal", reorder=5)
    low = make_medicine(code="L1", name="Low", reorder=20)
    soon = make_medicine(code="S1", name="Soon", reorder=1)
    expired = make_medicine(code="E1", name="Expired", reorder=1)
    out = make_medicine(code="O1", name="Never stocked")
    add_stock(normal.id, qty=100, expiry_days=400)
    add_stock(low.id, qty=10, expiry_days=400)
    add_stock(soon.id, qty=50, expiry_days=20)
    add_stock(expired.id, qty=7, expiry_days=-2, purchase_days_ago=100)

    rows = {r.code: r for r in ctx.inventory.stock_rows()}
    assert rows["N1"].status == STATUS_NORMAL
    assert rows["L1"].status == STATUS_LOW
    assert rows["S1"].status == STATUS_EXPIRING
    assert rows["E1"].status == STATUS_EXPIRED
    assert rows["O1"].status == STATUS_OUT
    assert rows["N1"].stock_value == Decimal("8000.00")

    assert [r.code for r in ctx.inventory.stock_rows(FILTER_LOW)] == ["L1"]
    assert [r.code for r in ctx.inventory.stock_rows(FILTER_EXPIRING)] == ["S1"]
    assert [r.code for r in ctx.inventory.stock_rows(FILTER_EXPIRED)] == ["E1"]
    assert sorted(r.code for r in ctx.inventory.stock_rows(FILTER_OUT)) == ["E1", "O1"]

    low_codes = [m.code for m in ctx.inventory.low_stock()]
    assert "L1" in low_codes and "O1" in low_codes and "N1" not in low_codes

    buckets = ctx.inventory.expiry_buckets()
    assert buckets == {"expired": 1, "30": 1, "60": 1, "90": 1}
    # Stock value counts sellable stock only; expired stock is reported separately.
    assert ctx.inventory.stock_value() == Decimal("8000.00") + Decimal("800.00") + Decimal("4000.00")
    assert ctx.inventory.expired_value() == Decimal("560.00")


def test_low_stock_uses_global_threshold_when_no_reorder_level(ctx, make_medicine, add_stock):
    ctx.settings.update({"low_stock_threshold": "15"})
    med = make_medicine(reorder=0)
    add_stock(med.id, qty=12)
    assert [m.code for m in ctx.inventory.low_stock()] == [med.code]
