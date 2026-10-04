import pytest

from app.services.errors import DuplicateCodeError, ValidationError
from app.services.medicine_service import MedicineInput
from app.services.sales_service import CartLine


def test_create_medicine(ctx, make_medicine):
    med = make_medicine(code="xx101")
    assert med.id
    assert med.code == "XX101"  # codes are normalised to upper case
    assert ctx.medicines.get(med.id).name == "Paracetamol"


def test_medicine_code_required(ctx):
    with pytest.raises(ValidationError, match="code cannot be empty"):
        ctx.medicines.create(MedicineInput(code="  ", name="Something"))


def test_medicine_name_required(ctx):
    with pytest.raises(ValidationError):
        ctx.medicines.create(MedicineInput(code="A1", name=""))


def test_duplicate_code_rejected_with_friendly_message(ctx, make_medicine):
    make_medicine(code="XX101")
    with pytest.raises(DuplicateCodeError) as exc:
        make_medicine(code="xx101", name="Other")
    assert str(exc.value) == "This medicine code already exists. Please choose another code."


def test_duplicate_code_on_edit(ctx, make_medicine):
    make_medicine(code="A1", name="A")
    b = make_medicine(code="B1", name="B")
    with pytest.raises(DuplicateCodeError):
        ctx.medicines.update(b.id, MedicineInput(code="A1", name="B"))


def test_edit_medicine(ctx, make_medicine):
    med = make_medicine()
    ctx.medicines.update(med.id, MedicineInput(code="XX101", name="Paracetamol Forte", category="Pain Relief"))
    assert ctx.medicines.get(med.id).name == "Paracetamol Forte"


def test_search_by_name_code_generic_manufacturer(ctx, make_medicine):
    make_medicine(code="XX101", name="Paracetamol", generic="Acetaminophen", manufacturer="Healix Labs")
    make_medicine(code="AMX101", name="Amoxicillin", generic="Amoxicillin Trihydrate", manufacturer="Medora")
    assert [m.code for m in ctx.medicines.search("para")] == ["XX101"]
    assert [m.code for m in ctx.medicines.search("XX101")] == ["XX101"]
    assert [m.code for m in ctx.medicines.search("xx1")] == ["XX101"]
    assert [m.code for m in ctx.medicines.search("acetamin")] == ["XX101"]
    assert [m.code for m in ctx.medicines.search("medora")] == ["AMX101"]
    assert len(ctx.medicines.search("")) == 2
    assert ctx.medicines.search("zzz-not-there") == []


def test_search_ranks_exact_code_first(ctx, make_medicine):
    make_medicine(code="AMX1010", name="Amoxil Forte")
    make_medicine(code="AMX101", name="Zeta Amoxicillin")
    assert ctx.medicines.search("AMX101")[0].code == "AMX101"


def test_search_handles_wildcards_safely(ctx, make_medicine):
    make_medicine(code="A1", name="Plain")
    assert ctx.medicines.search("%") == []
    assert ctx.medicines.search("_") == []


def test_find_by_code_and_barcode(ctx, make_medicine):
    med = make_medicine(code="XX101", barcode="8964000123456")
    assert ctx.medicines.find_by_code("xx101").id == med.id
    assert ctx.medicines.find_by_code("8964000123456").id == med.id
    assert ctx.medicines.find_by_code("") is None


def test_remove_without_history_deletes(ctx, make_medicine):
    med = make_medicine()
    assert ctx.medicines.remove(med.id) == "deleted"
    assert ctx.medicines.search("") == []


def test_remove_with_history_deactivates(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id)
    assert ctx.medicines.remove(med.id) == "deactivated"
    assert ctx.medicines.get(med.id).active is False
    # Deactivated medicines are hidden from POS search and cannot be sold.
    assert ctx.medicines.search("para") == []
    with pytest.raises(ValidationError, match="deactivated"):
        ctx.sales.complete_sale([CartLine(med.id, 1)])


def test_summary_aggregates_stock(ctx, make_medicine, add_stock):
    med = make_medicine()
    add_stock(med.id, qty=10, batch="A", expiry_days=100)
    add_stock(med.id, qty=5, batch="B", expiry_days=50, price="110")
    add_stock(med.id, qty=3, batch="C", expiry_days=-1, purchase_days_ago=60)
    s = ctx.medicines.summary(med.id)
    assert s.total_stock == 18
    assert s.sellable_stock == 15
    assert s.expired_stock == 3
    assert (s.nearest_expiry - __import__("datetime").date.today()).days == 50
    assert str(s.selling_price) == "110.00"  # price of the batch that will be sold next (FEFO)
