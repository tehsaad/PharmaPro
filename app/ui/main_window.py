"""Main window: navy sidebar navigation + page stack + global keyboard shortcuts."""
from __future__ import annotations

import logging

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.context import AppContext
from app.ui.add_stock import AddStockPage
from app.ui.analytics import AnalyticsPage
from app.ui.backup import BackupPage
from app.ui.base import Page
from app.ui.dashboard import DashboardPage
from app.ui.dialogs.common_dialogs import AboutDialog
from app.ui.expenses import ExpensesPage
from app.ui.icons import logo_icon, logo_pixmap, nav_icon
from app.ui.medicines import MedicinesPage
from app.ui.purchases import PurchasesPage
from app.ui.reports import ReportsPage
from app.ui.sales import SalesPage
from app.ui.settings import SettingsPage
from app.ui.stock import StockPage
from app.ui.widgets import label, show_exception

log = logging.getLogger(__name__)

NAV = [
    # key, label, icon, page class
    ("dashboard", "Dashboard", "dashboard", DashboardPage),
    ("medicines", "Medicines", "pill", MedicinesPage),
    ("add_stock", "Add Stock", "package-plus", AddStockPage),
    ("inventory", "Inventory", "package", StockPage),
    ("sales", "Sales / POS", "cart", SalesPage),
    ("purchases", "Purchases", "truck", PurchasesPage),
    ("expenses", "Expenses", "wallet", ExpensesPage),
    ("reports", "Reports", "file-text", ReportsPage),
    ("analytics", "Analytics", "chart", AnalyticsPage),
    ("settings", "Settings", "settings", SettingsPage),
]
BOTTOM = [("backup", "Backup", "database", BackupPage)]


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_NAME} — {ctx.settings.get('pharmacy_name')}")
        self.setWindowIcon(logo_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setCentralWidget(root)

        self.pages: dict[str, Page] = {}
        self.buttons: dict[str, QPushButton] = {}
        self.stack = QStackedWidget()
        self.stack.setObjectName("Pages")
        lay.addWidget(self._build_sidebar())
        lay.addWidget(self.stack, 1)

        for key, _text, _icon, cls in NAV + BOTTOM:
            page = cls(ctx)
            if hasattr(page, "navigate"):
                page.navigate = self.navigate
            self.pages[key] = page
            self.stack.addWidget(page)
        self.pages["settings"].on_data_changed = self._data_changed
        self.pages["backup"].on_restored = self._data_changed

        self._shortcuts()
        self.navigate("dashboard")

    # ---------------------------------------------------------------- sidebar
    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(236)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 18, 0, 14)
        v.setSpacing(2)

        brand = QHBoxLayout()
        brand.setContentsMargins(20, 0, 16, 14)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(34))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label(APP_NAME, "Brand"))
        self.brand_sub = label(self.ctx.settings.get("pharmacy_name"), "BrandSub")
        self.brand_sub.setMaximumWidth(160)
        names.addWidget(self.brand_sub)
        brand.addLayout(names, 1)
        v.addLayout(brand)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        sections = {"dashboard": "OVERVIEW", "medicines": "INVENTORY", "sales": "TRANSACTIONS", "reports": "INSIGHTS", "settings": "SYSTEM"}
        for i, (key, text, icon_name, _cls) in enumerate(NAV):
            if key in sections:
                v.addWidget(label(sections[key], "NavSection"))
            v.addWidget(self._nav_button(key, text, icon_name, f"F{i + 1}"))
        v.addStretch(1)

        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        f = QVBoxLayout(footer)
        f.setContentsMargins(0, 10, 0, 0)
        f.setSpacing(2)
        for key, text, icon_name, _cls in BOTTOM:
            f.addWidget(self._nav_button(key, text, icon_name))
        about = QPushButton("  About")
        about.setObjectName("NavButton")
        about.setIcon(nav_icon("info"))
        about.setIconSize(QSize(18, 18))
        about.setCursor(Qt.PointingHandCursor)
        about.clicked.connect(lambda: AboutDialog(self.ctx, self).exec())
        f.addWidget(about)
        offline = label("●  Offline · data stored locally", "BrandSub")
        offline.setStyleSheet("color: #5EEAD4; padding: 10px 22px 0 22px; font-size: 8.5pt;")
        f.addWidget(offline)
        version = label(f"Version {APP_VERSION}", "BrandSub")
        version.setStyleSheet("color: #5F7391; padding: 2px 22px; font-size: 8pt;")
        f.addWidget(version)
        v.addWidget(footer)
        return side

    def _nav_button(self, key: str, text: str, icon_name: str, shortcut: str = "") -> QPushButton:
        b = QPushButton(f"  {text}")
        b.setObjectName("NavButton")
        b.setCheckable(True)
        b.setIcon(nav_icon(icon_name))
        b.setIconSize(QSize(18, 18))
        b.setCursor(Qt.PointingHandCursor)
        if shortcut:
            b.setToolTip(f"{text}  ({shortcut})")
        b.clicked.connect(lambda: self.navigate(key))
        self.group.addButton(b)
        self.buttons[key] = b
        return b

    # ---------------------------------------------------------------- navigation
    def navigate(self, key: str, **kwargs) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        if key in self.buttons:
            self.buttons[key].setChecked(True)
        try:
            if key == "inventory" and "filter" in kwargs:
                page.filter = kwargs["filter"]
                page.filter_buttons[kwargs["filter"]].setChecked(True)
            page.refresh()
            if key == "add_stock" and kwargs.get("medicine_id"):
                page.preselect(kwargs["medicine_id"])
            if key == "sales" and kwargs.get("history"):
                page.open_history()
        except Exception as exc:  # never let one screen crash the app
            show_exception(self, exc)

    def current_page(self) -> Page:
        return self.stack.currentWidget()

    def _data_changed(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — {self.ctx.settings.get('pharmacy_name')}")
        self.brand_sub.setText(self.ctx.settings.get("pharmacy_name"))
        for key in ("add_stock", "sales"):
            page = self.pages[key]
            if key == "sales":
                page.lines, page.previews = [], []
                page._render()
            else:
                page.rows.clear()
                page._render()
        self.current_page().refresh()

    # ---------------------------------------------------------------- shortcuts
    def _shortcuts(self) -> None:
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(fn)

        sc("Ctrl+N", self._new_sale)
        sc("Ctrl+F", lambda: self.current_page().focus_search())
        sc("Ctrl+S", lambda: self.current_page().handle_save())
        sc("Ctrl+P", self._print)
        for i, (key, *_rest) in enumerate(NAV):
            sc(f"F{i + 1}", lambda k=key: self.navigate(k))

    def _new_sale(self):
        self.navigate("sales")
        self.pages["sales"].new_sale()

    def _print(self):
        if not self.current_page().handle_print():
            self.navigate("sales")
            self.pages["sales"].handle_print()

    def closeEvent(self, event):
        sales = self.pages["sales"]
        if sales.lines:
            from app.ui.widgets import confirm
            if not confirm(self, "Close PharmaPro?",
                           "There is an unfinished sale in the cart. It will be lost if you close now.\n\n"
                           "Use “Hold sale” to keep it.", "Close anyway", danger=True):
                event.ignore()
                return
        rows = self.pages["add_stock"].rows
        if rows:
            from app.ui.widgets import confirm
            if not confirm(self, "Close PharmaPro?",
                           "The Add Stock list has unsaved items. They will be lost if you close now.",
                           "Close anyway", danger=True):
                event.ignore()
                return
        event.accept()
