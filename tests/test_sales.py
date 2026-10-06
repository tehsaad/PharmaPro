import re
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import Batch, Sale, SaleItem
from app.services.errors import ExpiredStockError, InsufficientStockError, ValidationError
from app.services.sales_service import CartLine


def rows(ctx, model):
    with ctx.db.read() as s:
        return s.query(model).count()


def test_spec_profit_example(ctx, make_medicine, add_stock):
    """Purchase 10 @ Rs.80, sell 5 @ Rs.100 -> revenue 500, cost 400, profit 100."""
    med = make_medicine()
    add_stock(med.id, qty=10, cost="80", price="100")
    res = ctx.sales.complete_sale([CartLine(med.id, 5)])
    sale = ctx.sales.get(res.sale_id)
    assert sale.total == Decimal("500.00")
    assert sale.cost_of_goods == Decimal("400.00")
    assert sale.gross_profit == Decimal("100.00")
    (item,) = sale.items
    assert (item.quantity, item.selling_price, item.cost_price, item.profit) == (5, Decimal("100.00"), Decimal("80.00"), Decimal("100.00"))


def test_sale_deducts_stock(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10)
    ctx.sales.complete_sale([CartLine(med.id, 4)])
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 6
    assert ctx.sales.available_quantity(med.id) == 6


def test_multi_item_sale_with_discount(ctx, make_medicine, add_stock):
    a = make_medicine(code="XX101", name="Paracetamol")
    b = make_medicine(code="AMX101", name="Amoxicillin")
    c = make_medicine(code="VIT201", name="Vitamin C")
    add_stock(a.id, qty=50, cost="80", price="100")
    add_stock(b.id, qty=50, cost="120", price="160")
    add_stock(c.id, qty=50, cost="40", price="70")
    res = ctx.sales.complete_sale([CartLine(a.id, 2), CartLine(b.id, 1), CartLine(c.id, 3)], discount="20")
    sale = ctx.sales.get(res.sale_id)
    assert sale.subtotal == Decimal("570.00")
    assert sale.discount == Decimal("20.00")
    assert sale.total == Decimal("550.00")
    assert sale.cost_of_goods == Decimal("400.00")  # 160 + 120 + 120
    assert sale.gross_profit == Decimal("150.00")  # 550 - 400


def test_insufficient_stock_blocks_sale_and_changes_nothing(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=3)
    with pytest.raises(InsufficientStockError, match="Insufficient stock"):
        ctx.sales.complete_sale([CartLine(med.id, 4)])
    assert rows(ctx, Sale) == 0
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 3


def test_same_medicine_on_two_lines_cannot_oversell(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=5)
    with pytest.raises(InsufficientStockError):
        ctx.sales.complete_sale([CartLine(med.id, 3), CartLine(med.id, 3)])
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 5


def test_stock_never_negative_even_at_db_level(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=2)
    with pytest.raises(Exception):
        with ctx.db.session() as s:
            s.query(Batch).update({Batch.quantity_remaining: -1})
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 2


def test_expired_stock_cannot_be_sold(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, expiry_days=-1, purchase_days_ago=100)
    with pytest.raises(ExpiredStockError, match="expired"):
        ctx.sales.complete_sale([CartLine(med.id, 1)])
    assert rows(ctx, Sale) == 0
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 10


def test_batch_expiring_today_is_treated_as_expired(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, expiry_days=0, purchase_days_ago=100)
    with pytest.raises(ExpiredStockError):
        ctx.sales.complete_sale([CartLine(med.id, 1)])


def test_choosing_an_expired_batch_explicitly_is_blocked(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, batch="OLD", expiry_days=-3, purchase_days_ago=100)
    add_stock(med.id, qty=10, batch="NEW", expiry_days=300)
    old = next(b for b in ctx.medicines.batches(med.id) if b.batch_number == "OLD")
    with pytest.raises(ExpiredStockError, match="Batch OLD"):
        ctx.sales.complete_sale([CartLine(med.id, 1, batch_id=old.id)])


def test_expired_batches_skipped_by_fefo(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, batch="OLD", expiry_days=-3, purchase_days_ago=100)
    add_stock(med.id, qty=10, batch="NEW", expiry_days=300)
    res = ctx.sales.complete_sale([CartLine(med.id, 2)])
    assert [i.batch.batch_number for i in ctx.sales.get(res.sale_id).items] == ["NEW"]


def test_insufficient_mentions_expired_units(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, batch="OLD", expiry_days=-3, purchase_days_ago=100)
    add_stock(med.id, qty=2, batch="NEW", expiry_days=300)
    with pytest.raises(InsufficientStockError, match="10 more are expired"):
        ctx.sales.complete_sale([CartLine(med.id, 5)])


def test_fefo_picks_nearest_expiry_first(ctx, make_medicine, add_stock):
    """Spec example: Batch A 20 units @80 (nearer expiry), Batch B 50 @90; sell 10 -> from A."""
    med = make_medicine()
    add_stock(med.id, qty=50, batch="B", cost="90", price="110", expiry_days=400)
    add_stock(med.id, qty=20, batch="A", cost="80", price="100", expiry_days=200)
    res = ctx.sales.complete_sale([CartLine(med.id, 10)])
    (item,) = ctx.sales.get(res.sale_id).items
    assert item.batch.batch_number == "A"
    assert item.cost_price == Decimal("80.00")
    batches = {b.batch_number: b.quantity_remaining for b in ctx.medicines.batches(med.id)}
    assert batches == {"A": 10, "B": 50}


def test_fefo_spans_batches_with_each_batch_cost(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=20, batch="A", cost="80", price="100", expiry_days=200)
    add_stock(med.id, qty=50, batch="B", cost="90", price="110", expiry_days=400)
    res = ctx.sales.complete_sale([CartLine(med.id, 25)])
    sale = ctx.sales.get(res.sale_id)
    parts = [(i.batch.batch_number, i.quantity, i.cost_price, i.selling_price) for i in sale.items]
    assert parts == [("A", 20, Decimal("80.00"), Decimal("100.00")), ("B", 5, Decimal("90.00"), Decimal("110.00"))]
    assert sale.total == Decimal("2550.00")       # 20*100 + 5*110
    assert sale.cost_of_goods == Decimal("2050.00")  # 20*80 + 5*90
    assert sale.gross_profit == Decimal("500.00")


def test_preview_matches_commit(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=20, batch="A", price="100", expiry_days=200)
    add_stock(med.id, qty=50, batch="B", price="110", expiry_days=400)
    (line,) = ctx.sales.preview([CartLine(med.id, 25)])
    assert line.total == Decimal("2550.00")
    assert line.mixed_prices
    assert line.batch_label == "A, B"
    # preview must not change stock
    assert ctx.sales.available_quantity(med.id) == 70


def test_history_unchanged_after_price_change(ctx, make_medicine, add_stock):
    """RULES 9-11: later price changes never alter past sales or profit."""
    med = make_medicine()
    add_stock(med.id, qty=10, cost="80", price="100")
    res = ctx.sales.complete_sale([CartLine(med.id, 2)])
    batch = ctx.medicines.batches(med.id)[0]
    ctx.medicines.update_batch_selling_price(batch.id, "150")
    sale = ctx.sales.get(res.sale_id)
    assert sale.total == Decimal("200.00")
    assert sale.gross_profit == Decimal("40.00")
    res2 = ctx.sales.complete_sale([CartLine(med.id, 1)])
    assert ctx.sales.get(res2.sale_id).total == Decimal("150.00")


def test_discount_cannot_exceed_subtotal(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, price="100")
    with pytest.raises(ValidationError, match="Discount"):
        ctx.sales.complete_sale([CartLine(med.id, 1)], discount="150")
    with pytest.raises(ValidationError):
        ctx.sales.complete_sale([CartLine(med.id, 1)], discount="-5")
    assert rows(ctx, Sale) == 0


def test_empty_sale_rejected(ctx):
    with pytest.raises(ValidationError, match="empty"):
        ctx.sales.complete_sale([])


def test_invalid_quantity_rejected(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10)
    for bad in (0, -1, "x"):
        with pytest.raises(ValidationError):
            ctx.sales.complete_sale([CartLine(med.id, bad)])


def test_receipt_numbers_unique_and_sequential(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=50)
    numbers = [ctx.sales.complete_sale([CartLine(med.id, 1)]).receipt_number for _ in range(3)]
    today = date.today().strftime("%Y%m%d")
    assert numbers == [f"RX-{today}-0001", f"RX-{today}-0002", f"RX-{today}-0003"]
    assert all(re.fullmatch(r"RX-\d{8}-\d{4}", n) for n in numbers)


def test_receipt_numbers_restart_each_day(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=50, purchase_days_ago=10)
    yesterday = datetime.now() - timedelta(days=1)
    r1 = ctx.sales.complete_sale([CartLine(med.id, 1)], sale_date=yesterday).receipt_number
    r2 = ctx.sales.complete_sale([CartLine(med.id, 1)]).receipt_number
    assert r1.endswith("-0001") and r2.endswith("-0001") and r1 != r2


def test_every_sale_has_timestamp(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=5)
    sale = ctx.sales.get(ctx.sales.complete_sale([CartLine(med.id, 1)]).sale_id)
    assert isinstance(sale.sale_date, datetime)
    assert abs((datetime.now() - sale.sale_date).total_seconds()) < 60


def test_sale_rollback_when_a_later_line_fails(ctx, make_medicine, add_stock):
    a = make_medicine(code="A1", name="A")
    b = make_medicine(code="B1", name="B")
    add_stock(a.id, qty=10)
    add_stock(b.id, qty=1)
    with pytest.raises(InsufficientStockError):
        ctx.sales.complete_sale([CartLine(a.id, 5), CartLine(b.id, 2)])
    assert rows(ctx, Sale) == 0
    assert rows(ctx, SaleItem) == 0
    assert ctx.medicines.batches(a.id)[0].quantity_remaining == 10


def test_sale_rollback_on_unexpected_database_error(ctx, make_medicine, add_stock, monkeypatch):
    med = make_medicine()
    add_stock(med.id, qty=10)
    from app.services import sales_service

    def boom(*a, **k):
        raise RuntimeError("disk failure")

    monkeypatch.setattr(sales_service.SalesService, "_next_receipt_number", staticmethod(boom))
    with pytest.raises(RuntimeError):
        ctx.sales.complete_sale([CartLine(med.id, 2)])
    assert rows(ctx, Sale) == 0
    assert ctx.medicines.batches(med.id)[0].quantity_remaining == 10


def test_amount_received_and_change(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, price="100")
    with pytest.raises(ValidationError, match="less than the total"):
        ctx.sales.complete_sale([CartLine(med.id, 1)], amount_received="50")
    res = ctx.sales.complete_sale([CartLine(med.id, 1)], amount_received="500")
    data = ctx.receipts.build(ctx.sales.get(res.sale_id))
    assert data.change == Decimal("400.00")


def test_hold_and_resume_sale(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10)
    hid = ctx.sales.hold([CartLine(med.id, 2)], discount="5", label="Customer 1")
    assert len(ctx.sales.held_sales()) == 1
    lines, discount = ctx.sales.resume(hid)
    assert lines == [CartLine(med.id, 2, None)] and discount == Decimal("5.00")
    assert ctx.sales.held_sales() == []
    # holding a sale does not reserve or deduct stock
    assert ctx.sales.available_quantity(med.id) == 10


def test_lookup_exact_code_for_scanner(ctx, make_medicine):
    med = make_medicine(code="XX101")
    assert ctx.sales.lookup("xx101").id == med.id
    assert ctx.sales.lookup("XX10") is None
    assert ctx.sales.lookup("") is None
