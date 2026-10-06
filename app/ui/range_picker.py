"""Date-range selector with presets (Today, This Month, … Custom Range)."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from app.analytics.analytics_service import PRESETS, resolve_range
from app.ui.widgets import date_edit, from_qdate, label, to_qdate


class RangePicker(QWidget):
    changed = Signal(object, object)

    def __init__(self, default: str = "This Month", presets: list[str] | None = None):
        super().__init__()
        self.presets = presets or PRESETS
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.combo = QComboBox()
        self.combo.addItems(self.presets)
        self.combo.setMinimumWidth(150)
        self.start = date_edit(date.today(), allow_future=False)
        self.end = date_edit(date.today(), allow_future=False)
        self.dash = label("to", "Muted")
        lay.addWidget(self.combo)
        lay.addWidget(self.start)
        lay.addWidget(self.dash)
        lay.addWidget(self.end)
        self.combo.currentTextChanged.connect(self._preset)
        self.start.dateChanged.connect(self._custom)
        self.end.dateChanged.connect(self._custom)
        self._busy = False
        self.combo.setCurrentText(default)
        self._preset(default)

    def _preset(self, name: str) -> None:
        custom = name == "Custom Range"
        if not custom:
            s, e = resolve_range(name)
            self._busy = True
            self.start.setDate(to_qdate(s))
            self.end.setDate(to_qdate(e))
            self._busy = False
        self.start.setEnabled(custom)
        self.end.setEnabled(custom)
        self.changed.emit(*self.range())

    def _custom(self, *_):
        if not self._busy and self.combo.currentText() == "Custom Range":
            self.changed.emit(*self.range())

    def range(self) -> tuple[date, date]:
        s, e = from_qdate(self.start.date()), from_qdate(self.end.date())
        return (s, e) if s <= e else (e, s)

    def label_text(self) -> str:
        name = self.combo.currentText()
        s, e = self.range()
        return name if name != "Custom Range" else f"{s:%d %b %Y} – {e:%d %b %Y}"
