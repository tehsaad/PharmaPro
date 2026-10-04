"""Shared constants and default settings."""
from __future__ import annotations

MEDICINE_CATEGORIES = [
    "Pain Relief", "Antibiotic", "Antiviral", "Antifungal", "Vitamin & Supplement",
    "Cardiovascular", "Diabetes", "Gastrointestinal", "Respiratory", "Allergy",
    "Dermatology", "Eye & Ear", "Hormonal", "Neurology", "Psychiatric",
    "First Aid", "Surgical", "Baby Care", "Other",
]

DOSAGE_FORMS = [
    "Tablet", "Capsule", "Syrup", "Suspension", "Injection", "Drops", "Cream",
    "Ointment", "Gel", "Inhaler", "Sachet", "Powder", "Spray", "Suppository", "Other",
]

UNITS = ["Tablet", "Capsule", "Strip", "Box", "Bottle", "Vial", "Ampoule", "Tube", "Sachet", "Pack", "Unit"]

EXPENSE_CATEGORIES = ["Electricity", "Rent", "Salaries", "Transportation", "Maintenance", "Other"]

PAPER_SIZES = {
    "thermal_80": "Thermal 80 mm",
    "thermal_58": "Thermal 58 mm",
    "a4": "A4",
}

# Stock status labels shown to the pharmacist.
STATUS_NORMAL = "Normal"
STATUS_LOW = "Low Stock"
STATUS_OUT = "Out of Stock"
STATUS_EXPIRING = "Expiring Soon"
STATUS_EXPIRED = "Expired"
STATUS_INACTIVE = "Inactive"

DEFAULT_SETTINGS: dict[str, str] = {
    "pharmacy_name": "PharmaPro Pharmacy",
    "address": "Main Boulevard, Lahore",
    "phone": "+92 300 0000000",
    "email": "",
    "license_number": "",
    "receipt_footer": "Thank you for your purchase.",
    "receipt_paper": "thermal_80",
    "printer_name": "",
    "auto_print_prompt": "1",
    "currency_symbol": "Rs.",
    "currency_code": "PKR",
    "low_stock_threshold": "10",
    "expiry_warning_days": "90",
    "auto_backup": "1",
    "backup_keep": "30",
}
