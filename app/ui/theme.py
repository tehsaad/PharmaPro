"""Visual design tokens and the application stylesheet.

Direction: dark navy sidebar, calm light workspace, a single medical-teal accent.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# ---- palette -------------------------------------------------------------
NAVY = "#0F1B2D"
NAVY_2 = "#16263D"
NAVY_3 = "#1F3350"
NAV_TEXT = "#9FB0C8"
NAV_TEXT_ACTIVE = "#FFFFFF"

ACCENT = "#0D9488"        # teal-600
ACCENT_HOVER = "#0F766E"  # teal-700
ACCENT_SOFT = "#E6F4F2"

BG = "#F3F5F8"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F8FAFC"
BORDER = "#E2E8F0"
BORDER_STRONG = "#CBD5E1"

TEXT = "#0F172A"
TEXT_2 = "#475569"
TEXT_MUTED = "#64748B"

# Status colours (reserved for state - always shown with a text label)
GOOD = "#047857"
GOOD_BG = "#E7F6EF"
WARN = "#B45309"
WARN_BG = "#FEF3E2"
SERIOUS = "#C2410C"
SERIOUS_BG = "#FDECE3"
CRITICAL = "#B91C1C"
CRITICAL_BG = "#FDE8E8"
NEUTRAL = "#475569"
NEUTRAL_BG = "#EEF2F6"

# Chart series (validated categorical order, light mode)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

STATUS_STYLE = {
    "Normal": (GOOD, GOOD_BG),
    "In Stock": (GOOD, GOOD_BG),
    "Low Stock": (WARN, WARN_BG),
    "Expiring Soon": (SERIOUS, SERIOUS_BG),
    "Expired": (CRITICAL, CRITICAL_BG),
    "Out of Stock": (NEUTRAL, NEUTRAL_BG),
    "Inactive": (TEXT_MUTED, NEUTRAL_BG),
    "Active": (GOOD, GOOD_BG),
    "Manual": (NEUTRAL, NEUTRAL_BG),
    "Automatic": (NEUTRAL, NEUTRAL_BG),
    "Before restore": (WARN, WARN_BG),
}

FONT_FAMILIES = ["Segoe UI", "Inter", "Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Arial"]


def app_font(size: float = 10) -> QFont:
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPointSizeF(size)
    return f


STYLESHEET = f"""
* {{ outline: none; }}
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QWidget#Workspace, QStackedWidget#Pages {{ background: {BG}; }}
QDialog {{ background: {SURFACE}; }}
QToolTip {{ background: {NAVY}; color: white; border: none; padding: 6px 8px; border-radius: 6px; }}

/* ---------- sidebar ---------- */
QFrame#Sidebar {{ background: {NAVY}; border: none; }}
QLabel#Brand {{ color: white; font-size: 15pt; font-weight: 700; }}
QLabel#BrandSub {{ color: {NAV_TEXT}; font-size: 8.5pt; }}
QLabel#NavSection {{ color: #5F7391; font-size: 8pt; font-weight: 700; letter-spacing: 1px; padding: 12px 18px 4px 18px; }}
QPushButton#NavButton {{
    color: {NAV_TEXT}; background: transparent; border: none; border-radius: 8px;
    text-align: left; padding: 9px 14px; margin: 1px 10px; font-size: 10pt; font-weight: 500;
}}
QPushButton#NavButton:hover {{ background: {NAVY_2}; color: white; }}
QPushButton#NavButton:checked {{ background: {NAVY_3}; color: white; font-weight: 600; }}
QFrame#SidebarFooter {{ border-top: 1px solid {NAVY_3}; }}

/* ---------- page header ---------- */
QLabel#PageTitle {{ font-size: 18pt; font-weight: 700; color: {TEXT}; }}
QLabel#PageSubtitle {{ color: {TEXT_MUTED}; font-size: 10pt; }}
QLabel#SectionTitle {{ font-size: 11.5pt; font-weight: 650; color: {TEXT}; }}
QLabel#Muted {{ color: {TEXT_MUTED}; }}
QLabel#FieldLabel {{ color: {TEXT_2}; font-weight: 600; font-size: 9pt; }}

/* ---------- cards ---------- */
QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#StatCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#StatValue {{ font-size: 19pt; font-weight: 700; color: {TEXT}; }}
QLabel#StatLabel {{ color: {TEXT_MUTED}; font-size: 9.5pt; font-weight: 600; }}
QLabel#StatHint {{ color: {TEXT_MUTED}; font-size: 8.5pt; }}
QFrame#TotalsPanel {{ background: {NAVY}; border-radius: 12px; }}
QFrame#TotalsPanel QLabel {{ color: #D5DEEA; }}
QLabel#GrandTotal {{ color: white; font-size: 26pt; font-weight: 700; }}
QFrame#Banner {{ border-radius: 10px; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 6px 10px; min-height: 22px; selection-background-color: {ACCENT}; selection-color: white;
}}
QPlainTextEdit, QTextEdit {{ padding: 6px; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1.5px solid {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QSpinBox:disabled {{ background: {SURFACE_ALT}; color: {TEXT_MUTED}; }}
QLineEdit#ScanField {{ font-size: 13pt; padding: 10px 14px; border-radius: 10px; border: 1.5px solid {BORDER_STRONG}; }}
QLineEdit#ScanField:focus {{ border: 2px solid {ACCENT}; }}
QLineEdit#SearchField {{ padding-left: 8px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT}; padding: 4px; }}
QCheckBox {{ spacing: 8px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}
QPushButton#Stepper {{ padding: 0; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; border-radius: 8px; }}

/* ---------- buttons ---------- */
QPushButton {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_ALT}; border-color: #94A3B8; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #94A3B8; background: {SURFACE_ALT}; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; }}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[variant="primary"]:disabled {{ background: #9CCFC9; border-color: #9CCFC9; color: white; }}
QPushButton[variant="danger"] {{ background: {SURFACE}; color: {CRITICAL}; border: 1px solid #F3B4B4; }}
QPushButton[variant="danger"]:hover {{ background: {CRITICAL_BG}; }}
QPushButton[variant="ghost"] {{ background: transparent; border: none; color: {TEXT_2}; padding: 6px 10px; }}
QPushButton[variant="ghost"]:hover {{ background: {NEUTRAL_BG}; color: {TEXT}; }}
QPushButton[variant="big"] {{ background: {ACCENT}; color: white; border: none; font-size: 12pt; padding: 13px 18px; border-radius: 10px; }}
QPushButton[variant="big"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[variant="big"]:disabled {{ background: #5E8F8A; color: #D8E6E4; }}
QPushButton[variant="onDark"] {{ background: {NAVY_3}; color: white; border: 1px solid #2B4466; }}
QPushButton[variant="onDark"]:hover {{ background: #2A4466; }}

/* ---------- tables ---------- */
QTableView, QTableWidget, QListWidget, QTreeWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
    gridline-color: transparent; alternate-background-color: #FAFBFD;
    selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT};
}}
QTableView::item, QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid #EEF2F6; }}
QTableView::item:selected, QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
QHeaderView::section {{
    background: {SURFACE_ALT}; color: {TEXT_2}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px 8px; font-weight: 700; font-size: 9pt;
}}
QHeaderView {{ background: transparent; border: none; }}
QTableCornerButton::section {{ background: {SURFACE_ALT}; border: none; }}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid #EEF2F6; }}
QListWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

/* ---------- misc ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #CBD5E1; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {TEXT_MUTED}; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {ACCENT_HOVER}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding: 14px 12px 12px 12px; font-weight: 650; background: {SURFACE}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {TEXT_2}; }}
QMessageBox QLabel {{ font-size: 10pt; }}
QLabel#Toast {{ background: {NAVY}; color: white; border-radius: 10px; padding: 12px 18px; font-weight: 600; }}
QFrame#Divider {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(app_font(10))
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.Base, QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor("#FAFBFD"))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(SURFACE))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.PlaceholderText, QColor("#94A3B8"))
    pal.setColor(QPalette.ToolTipBase, QColor(NAVY))
    pal.setColor(QPalette.ToolTipText, QColor("white"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)
