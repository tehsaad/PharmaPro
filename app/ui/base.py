"""Base class for main-window pages."""
from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from app.context import AppContext


class Page(QWidget):
    """A screen in the main window.

    Pages are refreshed every time they are shown, so figures are always current.
    Optional hooks used by the global keyboard shortcuts:
    ``focus_search`` (Ctrl+F), ``handle_save`` (Ctrl+S), ``handle_print`` (Ctrl+P).
    """

    title = ""

    def __init__(self, ctx: AppContext, scroll: bool = False):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Workspace")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        inner.setObjectName("Workspace")
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(16)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setWidget(inner)
            outer.addWidget(area)
        else:
            outer.addWidget(inner)

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def focus_search(self) -> bool:
        return False

    def handle_save(self) -> bool:
        return False

    def handle_print(self) -> bool:
        return False
