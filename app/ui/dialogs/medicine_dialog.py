from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.context import AppContext
from app.services.medicine_service import MedicineInput
from app.ui.widgets import FAILED, Banner, button, field, hbox, label, run_safely
from app.utils.constants import DOSAGE_FORMS, MEDICINE_CATEGORIES, UNITS


def _combo(items: list[str], value: str = "") -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.addItems([""] + items)
    c.setCurrentText(value)
    c.setInsertPolicy(QComboBox.NoInsert)
    return c


class MedicineDialog(QDialog):
    """Add or edit a medicine. Validation happens in the service layer."""

    def __init__(self, ctx: AppContext, parent=None, medicine_id: int | None = None, initial_code: str = ""):
        super().__init__(parent)
        self.ctx = ctx
        self.medicine_id = medicine_id
        self.saved_id: int | None = None
        self.setWindowTitle("Edit medicine" if medicine_id else "Add medicine")
        self.setMinimumWidth(640)

        med = ctx.medicines.get(medicine_id) if medicine_id else None
        cats = sorted(set(MEDICINE_CATEGORIES) | set(ctx.medicines.categories()))

        self.code = QLineEdit(med.code if med else initial_code.upper())
        self.code.setPlaceholderText("e.g. PCM001")
        self.barcode = QLineEdit((med.barcode or "") if med else "")
        self.barcode.setPlaceholderText("Scan or type (optional)")
        self.name = QLineEdit(med.name if med else "")
        self.name.setPlaceholderText("e.g. Paracetamol")
        self.generic = QLineEdit(med.generic_name if med else "")
        self.category = _combo(cats, med.category if med else "")
        self.manufacturer = QLineEdit(med.manufacturer if med else "")
        self.dosage = _combo(DOSAGE_FORMS, med.dosage if med else "")
        self.strength = QLineEdit(med.strength if med else "")
        self.strength.setPlaceholderText("e.g. 500 mg")
        self.unit = _combo(UNITS, med.unit if med else "Strip")
        self.reorder = QSpinBox()
        self.reorder.setRange(0, 1_000_000)
        self.reorder.setValue(med.reorder_level if med else 0)
        self.reorder.setSpecialValueText("Use default")
        self.description = QPlainTextEdit(med.description if med else "")
        self.description.setFixedHeight(70)
        self.active = QCheckBox("Active (available for sale and stock entry)")
        self.active.setChecked(med.active if med else True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(label(self.windowTitle(), "PageTitle"))
        self.error = Banner("", "error")
        self.error.hide()
        lay.addWidget(self.error)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.addWidget(field("Medicine code *", self.code), 0, 0)
        grid.addWidget(field("Barcode", self.barcode), 0, 1)
        grid.addWidget(field("Medicine name *", self.name), 1, 0)
        grid.addWidget(field("Generic name", self.generic), 1, 1)
        grid.addWidget(field("Category", self.category), 2, 0)
        grid.addWidget(field("Manufacturer", self.manufacturer), 2, 1)
        grid.addWidget(field("Dosage form", self.dosage), 3, 0)
        grid.addWidget(field("Strength", self.strength), 3, 1)
        grid.addWidget(field("Selling unit", self.unit), 4, 0)
        grid.addWidget(field("Reorder level", self.reorder, "Warn when stock falls to this level"), 4, 1)
        grid.addWidget(field("Notes", self.description), 5, 0, 1, 2)
        lay.addLayout(grid)
        if med:
            lay.addWidget(self.active)

        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        save = button("Save medicine", "check", "primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        lay.addLayout(hbox(None, cancel, save))
        (self.name if med else self.code).setFocus()

    def _save(self):
        data = MedicineInput(
            code=self.code.text(), barcode=self.barcode.text(), name=self.name.text(),
            generic_name=self.generic.text(), category=self.category.currentText(),
            manufacturer=self.manufacturer.text(), dosage=self.dosage.currentText(),
            strength=self.strength.text(), unit=self.unit.currentText(), reorder_level=self.reorder.value(),
            description=self.description.toPlainText(), active=self.active.isChecked(),
        )
        if self.medicine_id:
            res = run_safely(self, self.ctx.medicines.update, self.medicine_id, data)
        else:
            res = run_safely(self, self.ctx.medicines.create, data)
        if res is FAILED:
            return
        self.saved_id = res.id
        self.accept()

    def keyPressEvent(self, e):
        # Enter inside a single-line field should not submit half-finished forms by accident
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.focusWidget() is self.description:
            return super().keyPressEvent(e)
        super().keyPressEvent(e)
