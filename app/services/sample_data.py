"""Fictional demonstration data. Contains no real patient or customer information."""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Medicine
from app.services.errors import InsufficientStockError, ValidationError
from app.services.medicine_service import MedicineInput
from app.services.purchase_service import StockLine
from app.services.sales_service import CartLine

# code, name, generic, category, manufacturer, dosage, strength, unit, reorder, cost, price
MEDICINES = [
    ("XX101", "Paracetamol", "Acetaminophen", "Pain Relief", "Healix Labs", "Tablet", "500 mg", "Strip", 20, "80", "100"),
    ("AMX101", "Amoxicillin", "Amoxicillin Trihydrate", "Antibiotic", "Medora Pharma", "Capsule", "500 mg", "Strip", 15, "120", "160"),
    ("VIT201", "Vitamin C", "Ascorbic Acid", "Vitamin & Supplement", "NutriCore", "Tablet", "1000 mg", "Bottle", 10, "40", "70"),
    ("IBU400", "Ibuprofen", "Ibuprofen", "Pain Relief", "Healix Labs", "Tablet", "400 mg", "Strip", 15, "55", "75"),
    ("AZM250", "Azithromycin", "Azithromycin", "Antibiotic", "Medora Pharma", "Tablet", "250 mg", "Strip", 10, "210", "280"),
    ("CTZ010", "Cetirizine", "Cetirizine HCl", "Allergy", "Aerolife", "Tablet", "10 mg", "Strip", 12, "30", "45"),
    ("OMP020", "Omeprazole", "Omeprazole", "Gastrointestinal", "Gastro Pharma", "Capsule", "20 mg", "Strip", 15, "95", "130"),
    ("MET500", "Metformin", "Metformin HCl", "Diabetes", "Glucocare", "Tablet", "500 mg", "Strip", 20, "60", "85"),
    ("AML005", "Amlodipine", "Amlodipine Besylate", "Cardiovascular", "CardioWell", "Tablet", "5 mg", "Strip", 50, "70", "100"),
    ("SAL100", "Salbutamol Inhaler", "Salbutamol", "Respiratory", "Aerolife", "Inhaler", "100 mcg", "Unit", 5, "320", "420"),
    ("ORS001", "ORS Sachet", "Oral Rehydration Salts", "Gastrointestinal", "Hydra Health", "Sachet", "20.5 g", "Sachet", 30, "12", "20"),
    ("CFS100", "Cough Syrup", "Dextromethorphan", "Respiratory", "Aerolife", "Syrup", "100 ml", "Bottle", 8, "110", "150"),
    ("DCL050", "Diclofenac Gel", "Diclofenac Sodium", "Pain Relief", "DermaPlus", "Gel", "1%", "Tube", 6, "140", "190"),
    ("LOR010", "Loratadine", "Loratadine", "Allergy", "Aerolife", "Tablet", "10 mg", "Strip", 30, "35", "55"),
    ("CAL500", "Calcium + D3", "Calcium Carbonate + Vitamin D3", "Vitamin & Supplement", "NutriCore", "Tablet", "500 mg", "Bottle", 8, "180", "250"),
    ("FLU150", "Fluconazole", "Fluconazole", "Antifungal", "Medora Pharma", "Capsule", "150 mg", "Unit", 5, "45", "70"),
    ("ZNC020", "Zinc Syrup", "Zinc Sulphate", "Vitamin & Supplement", "NutriCore", "Syrup", "60 ml", "Bottle", 6, "65", "95"),
    ("BND001", "Elastic Bandage", "Crepe Bandage", "First Aid", "MediWrap", "Other", "10 cm", "Unit", 5, "90", "130"),
]

# Opening quantities kept small so these items demonstrate low-stock warnings.
LOW_DEMO = {"AML005": 270, "LOR010": 165}

SUPPLIERS = ["ABC Pharmaceuticals", "Crescent Distributors", "Unity Medical Supplies"]


def has_data(ctx) -> bool:
    with ctx.db.read() as s:
        return (s.scalar(select(func.count(Medicine.id))) or 0) > 0


def seed(ctx, days_of_sales: int = 75, rng_seed: int = 7) -> dict:
    """Populate an empty database with realistic fictional data."""
    if has_data(ctx):
        raise ValidationError("Sample data can only be loaded into an empty database.")
    rng = random.Random(rng_seed)
    today = date.today()

    ids: dict[str, int] = {}
    prices: dict[str, tuple[str, str]] = {}
    for code, name, generic, cat, mfr, dosage, strength, unit, reorder, cost, price in MEDICINES:
        med = ctx.medicines.create(MedicineInput(code=code, name=name, generic_name=generic, category=cat,
                                                 manufacturer=mfr, dosage=dosage, strength=strength, unit=unit,
                                                 reorder_level=reorder))
        ids[code] = med.id
        prices[code] = (cost, price)
    # One catalogue entry that has never been stocked.
    ctx.medicines.create(MedicineInput(code="INS100", name="Insulin Glargine", generic_name="Insulin Glargine",
                                       category="Diabetes", manufacturer="Glucocare", dosage="Injection",
                                       strength="100 IU/ml", unit="Vial", reorder_level=3))

    def bump(value: str, pct: float) -> str:
        return str((Decimal(value) * Decimal(str(1 + pct))).quantize(Decimal("1")))

    # Purchase 1: four months ago - the main opening stock.
    p1_date = today - timedelta(days=days_of_sales + 30)
    lines = []
    for code, *_ in MEDICINES:
        cost, price = prices[code]
        qty = LOW_DEMO.get(code) or rng.randint(250, 600)
        lines.append(StockLine(ids[code], f"{code[:3]}-A{rng.randint(100, 999)}",
                               today + timedelta(days=rng.randint(200, 900)), qty, cost, price))
    ctx.purchases.add_stock(SUPPLIERS[0], "INV-1001", p1_date, lines)

    # Purchase 2: an old lot that has now expired, still on the shelf (slow movers).
    p2_date = today - timedelta(days=400)
    ctx.purchases.add_stock(SUPPLIERS[1], "INV-0870", p2_date, [
        StockLine(ids["BND001"], "BND-OLD7", today - timedelta(days=20), 150, "85", "125"),
        StockLine(ids["DCL050"], "DCL-OLD2", today - timedelta(days=6), 160, "130", "180"),
    ])

    # Purchase 3: mid-period restock at slightly higher cost - both costs are preserved.
    p3_date = today - timedelta(days=35)
    restock = []
    for code, *_ in MEDICINES:
        if code in LOW_DEMO:
            continue  # left to run low so the low-stock warnings have something to show
        cost, price = prices[code]
        restock.append(StockLine(ids[code], f"{code[:3]}-B{rng.randint(100, 999)}",
                                 today + timedelta(days=rng.randint(300, 1000)), rng.randint(150, 350),
                                 bump(cost, 0.05), bump(price, 0.05)))
    ctx.purchases.add_stock(SUPPLIERS[2], "INV-2044", p3_date, restock)

    # Purchase 4: short-dated stock of slow movers (expiring within 30 / 60 / 90 days).
    ctx.purchases.add_stock(SUPPLIERS[0], "INV-2101", today - timedelta(days=20), [
        StockLine(ids["SAL100"], "SAL-C210", today + timedelta(days=24), 70, "320", "420"),
        StockLine(ids["FLU150"], "FLU-C330", today + timedelta(days=52), 120, "45", "70"),
        StockLine(ids["CAL500"], "CAL-C118", today + timedelta(days=80), 110, "180", "250"),
    ])

    # Sales spread over the last ``days_of_sales`` days.
    weights = {code: w for code, w in zip([m[0] for m in MEDICINES],
                                         [10, 6, 5, 7, 3, 6, 5, 6, 4, 1, 8, 3, 2, 3, 2, 2, 2, 1])}
    codes = list(weights)
    sale_count = 0
    for offset in range(days_of_sales, -1, -1):
        day = today - timedelta(days=offset)
        times = []
        for _ in range(rng.randint(8, 16) if offset else rng.randint(4, 8)):
            hour = rng.randint(9, 21) if offset else min(datetime.now().hour, rng.randint(9, 21))
            when = datetime.combine(day, time(hour, rng.randint(0, 59), rng.randint(0, 59)))
            jitter = rng.randint(1, 30)  # always drawn, so results don't depend on the time of day
            if when > datetime.now():
                when = datetime.now().replace(microsecond=0) - timedelta(minutes=jitter)
            if when.date() == day:
                times.append(when)
        for when in sorted(times):  # receipt numbers follow the time of day
            chosen = rng.sample(codes, k=rng.randint(1, 4))
            cart = [CartLine(ids[c], rng.choice([1, 2, 2, 3, 4, 5])) for c in chosen
                    if rng.random() < weights[c] / 10 + 0.2]
            if not cart:
                continue
            discount = rng.choice([0, 0, 0, 0, 5, 10])
            try:
                ctx.sales.complete_sale(cart, discount=discount, sale_date=when)
                sale_count += 1
            except (InsufficientStockError, ValidationError):
                continue

    # Monthly running costs.
    expenses = 0
    month_start = (today - timedelta(days=days_of_sales)).replace(day=1)
    while month_start <= today:
        for title, cat, amount in (("Shop rent", "Rent", 12000), ("Electricity bill", "Electricity", rng.randint(3000, 5000)),
                                   ("Assistant salary", "Salaries", 12000)):
            d = month_start + timedelta(days=4 if cat != "Salaries" else 0)
            if d <= today:
                ctx.expenses.add(title, cat, amount, d, "Monthly expense")
                expenses += 1
        d = month_start + timedelta(days=14)
        if d <= today:
            ctx.expenses.add("Stock delivery charges", "Transportation", rng.randint(800, 2000), d)
            expenses += 1
        month_start = (month_start + timedelta(days=32)).replace(day=1)
    return {"medicines": len(MEDICINES) + 1, "sales": sale_count, "expenses": expenses}
