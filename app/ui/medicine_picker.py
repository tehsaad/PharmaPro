"""Type-ahead medicine selector used by Add Stock and POS."""
from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit

from app.context import AppContext


class MedicinePicker(QLineEdit):
    """Line edit with instant suggestions over code, name, generic name and manufacturer.

    Emits ``picked(medicine_id)`` when a suggestion is chosen or an exact code/barcode is entered.
    Emits ``not_found(text)`` when Enter is pressed and nothing matches.
    """

    picked = Signal(int)
    not_found = Signal(str)

    def __init__(self, ctx: AppContext, placeholder: str = "Type code or name…", scanner_mode: bool = False):
        super().__init__()
        self.ctx = ctx
        self.scanner_mode = scanner_mode
        self.setPlaceholderText(placeholder)
        self._map: dict[str, int] = {}
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(12)
        self._completer.activated[str].connect(self._on_activated)
        self.setCompleter(self._completer)
        self.returnPressed.connect(self._on_return)
        self.reload()

    def reload(self) -> None:
        meds = self.ctx.medicines.search("", limit=100_000, active_only=True)
        self._map = {}
        for m in meds:
            parts = [m.code, m.name]
            if m.strength:
                parts[1] = f"{m.name} {m.strength}"
            label = f"{parts[0]}  —  {parts[1]}"
            if m.generic_name and m.generic_name.lower() != m.name.lower():
                label += f"  ({m.generic_name})"
            if m.manufacturer:
                label += f"  · {m.manufacturer}"
            self._map[label] = m.id
        self._model.setStringList(list(self._map))

    def _emit(self, mid: int) -> None:
        self.picked.emit(mid)
        if self.scanner_mode:
            self.clear()

    def _on_activated(self, text: str) -> None:
        mid = self._map.get(text)
        if mid is not None:
            # defer clearing until the completer has finished writing the text
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._emit(mid))

    def _on_return(self) -> None:
        text = self.text().strip()
        if not text:
            return
        if text in self._map:
            self._emit(self._map[text])
            return
        med = self.ctx.sales.lookup(text)  # exact code or barcode (scanner input)
        if med is not None:
            self._emit(med.id)
            return
        matches = self.ctx.medicines.search(text, limit=2)
        if len(matches) == 1:
            self._emit(matches[0].id)
        elif not matches:
            self.not_found.emit(text)
        else:
            self._completer.setCompletionPrefix(text)
            self._completer.complete()
