"""Reusable UI building blocks shared by every screen."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from PySide6.QtCore import (
    QAbstractTableModel,
    QDate,
    QEasingCurve,
    QModelIndex,
    QPropertyAnimation,
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.services.errors import PharmaError
from app.ui import theme
from app.ui.icons import icon, pixmap
from app.utils.formatting import fmt_date, fmt_datetime, money

log = logging.getLogger(__name__)

FAILED = object()  # sentinel returned by run_safely when an action failed
SORT_ROLE = Qt.UserRole + 1
OBJECT_ROLE = Qt.UserRole + 2


# --------------------------------------------------------------------------- buttons
def button(text: str = "", icon_name: str | None = None, variant: str | None = None,
           tooltip: str = "", icon_color: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if icon_name:
        color = icon_color or ("#FFFFFF" if variant in ("primary", "big", "onDark") else
                               theme.CRITICAL if variant == "danger" else theme.TEXT_2)
        b.setIcon(icon(icon_name, color, 16))
        b.setIconSize(QSize(16, 16))
    if tooltip:
        b.setToolTip(tooltip)
    b.setCursor(Qt.PointingHandCursor)
    return b


# --------------------------------------------------------------------------- layout
class Card(QFrame):
    def __init__(self, parent=None, padding: int = 18, spacing: int = 12, shadow: bool = False):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(padding, padding, padding, padding)
        self.layout_.setSpacing(spacing)
        if shadow:
            add_shadow(self)

    def add(self, w, stretch: int = 0):
        if isinstance(w, QWidget):
            self.layout_.addWidget(w, stretch)
        else:
            self.layout_.addLayout(w, stretch)
        return w


def add_shadow(w: QWidget, blur: int = 18, alpha: int = 18, dy: int = 3) -> None:
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setColor(QColor(15, 23, 42, alpha))
    eff.setOffset(0, dy)
    w.setGraphicsEffect(eff)


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def divider() -> QFrame:
    f = QFrame()
    f.setObjectName("Divider")
    return f


def field(caption: str, widget: QWidget, hint: str = "") -> QWidget:
    """Vertical label + input pair."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(label(caption, "FieldLabel"))
    lay.addWidget(widget)
    if hint:
        h = label(hint, "Muted", wrap=True)
        h.setStyleSheet("font-size: 8.5pt;")
        lay.addWidget(h)
    return box


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(10)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(title, "PageTitle"))
        self.subtitle = label(subtitle, "PageSubtitle")
        if subtitle:
            text.addWidget(self.subtitle)
        lay.addLayout(text)
        lay.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        lay.addLayout(self.actions)

    def add_action(self, w: QWidget) -> QWidget:
        self.actions.addWidget(w)
        return w


class StatCard(QFrame):
    """KPI tile: label, big value, small hint, with a tinted icon chip."""

    clicked = Signal()

    def __init__(self, title: str, icon_name: str, tint: str = theme.ACCENT, tint_bg: str = theme.ACCENT_SOFT):
        super().__init__()
        self.setObjectName("StatCard")
        self.setMinimumHeight(112)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.title = label(title, "StatLabel")
        self.value = label("—", "StatValue")
        self.hint = label("", "StatHint")
        col.addWidget(self.title)
        col.addWidget(self.value)
        col.addWidget(self.hint)
        col.addStretch(1)
        lay.addLayout(col, 1)
        chip = QLabel()
        chip.setFixedSize(40, 40)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(pixmap(icon_name, tint, 20))
        chip.setStyleSheet(f"background: {tint_bg}; border-radius: 10px;")
        lay.addWidget(chip, 0, Qt.AlignTop)
        add_shadow(self, blur=16, alpha=14, dy=2)

    def set(self, value: str, hint: str = "", hint_color: str | None = None) -> None:
        self.value.setText(value)
        self.hint.setText(hint)
        self.hint.setStyleSheet(f"color: {hint_color};" if hint_color else "")

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


class Banner(QFrame):
    """Inline notice strip (warning/info) with icon."""

    def __init__(self, text: str = "", kind: str = "warn"):
        super().__init__()
        self.setObjectName("Banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)
        self.icon = QLabel()
        self.text = label(text, wrap=True)
        lay.addWidget(self.icon, 0, Qt.AlignTop)
        lay.addWidget(self.text, 1)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        fg, bg, name = {
            "warn": (theme.WARN, theme.WARN_BG, "alert"),
            "error": (theme.CRITICAL, theme.CRITICAL_BG, "alert"),
            "info": (theme.TEXT_2, theme.NEUTRAL_BG, "info"),
            "ok": (theme.GOOD, theme.GOOD_BG, "check"),
        }[kind]
        self.setStyleSheet(f"QFrame#Banner {{ background: {bg}; border: 1px solid {bg}; }} QLabel {{ color: {fg}; font-weight: 600; }}")
        self.icon.setPixmap(pixmap(name, fg, 18))

    def set_text(self, text: str) -> None:
        self.text.setText(text)


class EmptyState(QWidget):
    def __init__(self, title: str, message: str = "", icon_name: str = "package"):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(pixmap(icon_name, "#94A3B8", 40))
        ic.setAlignment(Qt.AlignCenter)
        t = label(title, "SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        self.msg = label(message, "Muted", wrap=True)
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setMaximumWidth(420)
        lay.addWidget(ic)
        lay.addWidget(t)
        lay.addWidget(self.msg, 0, Qt.AlignHCenter)
        self.setStyleSheet(f"background: {theme.SURFACE}; border-radius: 10px;")


# --------------------------------------------------------------------------- inputs
class SearchField(QLineEdit):
    """Search box with an icon and debounced ``search`` signal (feels instant, stays cheap)."""

    search = Signal(str)

    def __init__(self, placeholder: str = "Search…", delay_ms: int = 120):
        super().__init__()
        self.setObjectName("SearchField")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(icon("search", "#94A3B8", 16), QLineEdit.LeadingPosition)
        self._timer = QTimer(self, singleShot=True, interval=delay_ms)
        self._timer.timeout.connect(lambda: self.search.emit(self.text().strip()))
        self.textChanged.connect(lambda _t: self._timer.start())
        self.setMinimumWidth(260)


def money_edit(maximum: float = 100_000_000) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setDecimals(2)
    w.setRange(0, maximum)
    w.setButtonSymbols(QAbstractSpinBox.NoButtons)
    w.setGroupSeparatorShown(True)
    w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    from app.utils.formatting import currency_symbol
    w.setPrefix(currency_symbol() + " ")
    return w


def date_edit(value: date | None = None, allow_future: bool = True) -> QDateEdit:
    w = QDateEdit()
    w.setCalendarPopup(True)
    w.setDisplayFormat("dd-MM-yyyy")
    w.setDate(to_qdate(value or date.today()))
    if not allow_future:
        w.setMaximumDate(to_qdate(date.today()))
    return w


def to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def from_qdate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def to_decimal(spin: QDoubleSpinBox) -> Decimal:
    return Decimal(str(round(spin.value(), 2)))


# --------------------------------------------------------------------------- tables
@dataclass
class Column:
    title: str
    getter: Callable[[Any], Any]
    kind: str = "text"  # text | money | int | date | datetime | status | expiry
    width: int | None = None
    stretch: bool = False
    color: Callable[[Any], str | None] | None = None
    bold: bool = False
    align_right: bool = False

    @property
    def right(self) -> bool:
        return self.align_right or self.kind in ("money", "int")


def format_value(value, kind: str) -> str:
    if kind == "auto":
        from app.services.reporting_service import display
        return display(value)
    if value is None or value == "":
        return "—" if kind != "text" else ""
    if kind == "money":
        return money(value)
    if kind == "int":
        return f"{int(value):,}"
    if kind == "date":
        return fmt_date(value)
    if kind == "datetime":
        return fmt_datetime(value)
    if kind == "expiry":
        return value.strftime("%d %b %Y") if isinstance(value, date) else str(value)
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return str(value)


def _sort_key(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.lower()
    return value


class ObjectTableModel(QAbstractTableModel):
    def __init__(self, columns: list[Column], parent=None):
        super().__init__(parent)
        self.columns = columns
        self.rows: list[Any] = []

    def set_rows(self, rows: list[Any]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_object(self, row: int):
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.columns[section].title
            if role == Qt.TextAlignmentRole:
                return int((Qt.AlignRight if self.columns[section].right else Qt.AlignLeft) | Qt.AlignVCenter)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        obj = self.rows[index.row()]
        col = self.columns[index.column()]
        if role == OBJECT_ROLE:
            return obj
        try:
            value = col.getter(obj)
        except Exception:  # defensive: never let one bad row break the table
            value = None
        if role == Qt.DisplayRole:
            return format_value(value, col.kind)
        if role == SORT_ROLE:
            return _sort_key(value)
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignRight if col.right else Qt.AlignLeft) | Qt.AlignVCenter)
        if role == Qt.ForegroundRole and col.color:
            c = col.color(obj)
            return QColor(c) if c else None
        if role == Qt.FontRole and col.bold:
            f = QFont()
            f.setWeight(QFont.DemiBold)
            return f
        return None


class FilterProxy(QSortFilterProxyModel):
    """Case-insensitive search across all columns plus an optional extra predicate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(-1)
        self.predicate: Callable[[Any], bool] | None = None
        self._terms: list[str] = []

    def _refilter(self, apply: Callable[[], None]) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt >= 6.10
            self.beginFilterChange()
            apply()
            self.endFilterChange()
        else:
            apply()
            self.invalidateFilter()

    def set_search(self, text: str) -> None:
        self._refilter(lambda: setattr(self, "_terms", [t for t in text.lower().split() if t]))

    def set_predicate(self, fn: Callable[[Any], bool] | None) -> None:
        self._refilter(lambda: setattr(self, "predicate", fn))

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        if self.predicate is not None:
            obj = model.row_object(row)
            if obj is not None and not self.predicate(obj):
                return False
        if not self._terms:
            return True
        hay = " ".join(
            str(model.data(model.index(row, c, parent), Qt.DisplayRole) or "") for c in range(model.columnCount())
        ).lower()
        return all(t in hay for t in self._terms)


class StatusDelegate(QStyledItemDelegate):
    """Draws status text as a rounded pill (colour + label, never colour alone)."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        text = index.data(Qt.DisplayRole) or ""
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        if not text or text == "—":
            return
        fg, bg = theme.STATUS_STYLE.get(text, (theme.NEUTRAL, theme.NEUTRAL_BG))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        f = QFont(option.font)
        f.setPointSizeF(max(8.0, f.pointSizeF() - 1))
        f.setWeight(QFont.DemiBold)
        painter.setFont(f)
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 18
        h = fm.height() + 6
        r = option.rect
        rect = QRectF(r.x() + 8, r.y() + (r.height() - h) / 2, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, h / 2, h / 2)
        painter.fillPath(path, QColor(bg))
        painter.setPen(QColor(fg))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + 30, s.height())


class DataTable(QWidget):
    """Sortable, searchable table that swaps to an empty-state message when empty."""

    activated = Signal(object)
    selection_changed = Signal(object)

    def __init__(self, columns: list[Column], empty_title: str = "Nothing here yet",
                 empty_message: str = "", empty_icon: str = "package", row_height: int = 40,
                 sort: tuple[int, Qt.SortOrder] | None = (0, Qt.AscendingOrder)):
        super().__init__()
        self.model = ObjectTableModel(columns, self)
        self.proxy = FilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(row_height)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        hh = self.view.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        self._status_delegate = StatusDelegate(self.view)
        for i, col in enumerate(columns):
            if col.kind == "status":
                self.view.setItemDelegateForColumn(i, self._status_delegate)
            if col.width:
                self.view.setColumnWidth(i, col.width)
            if col.stretch:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
        if sort is None:  # keep the order the rows were given in (e.g. newest first)
            hh.setSortIndicator(-1, Qt.AscendingOrder)
        else:
            hh.setSortIndicator(sort[0], sort[1])
        self.view.doubleClicked.connect(self._on_double)
        self.view.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed.emit(self.selected()))

        self.empty = EmptyState(empty_title, empty_message, empty_icon)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.empty)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)

    def set_rows(self, rows: list[Any]) -> None:
        sort_col = self.view.horizontalHeader().sortIndicatorSection()
        order = self.view.horizontalHeader().sortIndicatorOrder()
        self.model.set_rows(rows)
        if 0 <= sort_col < len(self.model.columns):
            self.proxy.sort(sort_col, order)
        else:
            self.proxy.sort(-1)
        self._update_empty()

    def search(self, text: str) -> None:
        self.proxy.set_search(text)
        self._update_empty()

    def set_predicate(self, fn) -> None:
        self.proxy.set_predicate(fn)
        self._update_empty()

    def _update_empty(self) -> None:
        self.stack.setCurrentIndex(0 if self.proxy.rowCount() else 1)

    def selected(self):
        idx = self.view.selectionModel().selectedRows()
        if not idx:
            return None
        return self.proxy.data(idx[0], OBJECT_ROLE)

    def visible_objects(self) -> list[Any]:
        return [self.proxy.data(self.proxy.index(r, 0), OBJECT_ROLE) for r in range(self.proxy.rowCount())]

    def _on_double(self, index):
        obj = self.proxy.data(index, OBJECT_ROLE)
        if obj is not None:
            self.activated.emit(obj)

    def sort_by(self, column: int, order=Qt.AscendingOrder) -> None:
        self.view.sortByColumn(column, order)


# --------------------------------------------------------------------------- feedback
class Toast(QLabel):
    """Non-blocking notification in the bottom-right corner of the window."""

    _active: list["Toast"] = []

    def __init__(self, parent: QWidget, text: str, kind: str = "ok"):
        super().__init__(parent)
        self.setObjectName("Toast")
        colors = {"ok": theme.ACCENT_HOVER, "warn": theme.WARN, "error": theme.CRITICAL, "info": theme.NAVY}
        self.setStyleSheet(f"QLabel#Toast {{ background: {colors.get(kind, theme.NAVY)}; }}")
        self.setText(text)
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self.adjustSize()
        add_shadow(self, blur=24, alpha=60, dy=6)

    @classmethod
    def show_message(cls, parent: QWidget | None, text: str, kind: str = "ok", ms: int = 3200) -> None:
        if parent is None:
            return
        window = parent.window()
        toast = cls(window, text, kind)
        cls._active = [t for t in cls._active if t.isVisible()]
        offset = sum(t.height() + 10 for t in cls._active)
        toast.move(window.width() - toast.width() - 28, window.height() - toast.height() - 28 - offset)
        toast.show()
        toast.raise_()
        cls._active.append(toast)
        QTimer.singleShot(ms, toast._fade)

    def _fade(self) -> None:
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(350)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self.deleteLater)
        anim.start()


def _box(parent, kind, title, text, informative: str = "") -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(f"<b style='font-size:11pt'>{title}</b>")
    box.setInformativeText(text.replace("\n", "<br>") if text else "")
    icons = {"info": QMessageBox.Information, "warn": QMessageBox.Warning, "error": QMessageBox.Critical,
             "question": QMessageBox.Question}
    box.setIcon(icons[kind])
    return box


def info(parent, title: str, text: str) -> None:
    _box(parent, "info", title, text).exec()


def warn(parent, title: str, text: str) -> None:
    _box(parent, "warn", title, text).exec()


def error(parent, title: str, text: str) -> None:
    _box(parent, "error", title, text).exec()


def confirm(parent, title: str, text: str, ok_text: str = "Yes", cancel_text: str = "Cancel",
            danger: bool = False) -> bool:
    box = _box(parent, "warn" if danger else "question", title, text)
    ok = box.addButton(ok_text, QMessageBox.AcceptRole)
    cancel = box.addButton(cancel_text, QMessageBox.RejectRole)
    ok.setProperty("variant", "danger" if danger else "primary")
    box.setDefaultButton(cancel if danger else ok)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is ok


def show_exception(parent, exc: BaseException) -> None:
    if isinstance(exc, PharmaError):
        warn(parent, exc.title, str(exc))
    else:
        log.error("Unexpected error", exc_info=(type(exc), exc, exc.__traceback__))
        error(parent, "Something went wrong",
              "The action could not be completed. No changes were saved.\n\n"
              "If this keeps happening, please restart PharmaPro. Technical details were written to the log file.")


def run_safely(parent, fn: Callable, *args, **kwargs):
    """Run an action, showing friendly messages for any error. Returns FAILED on error."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - intentionally catch everything for the user
        show_exception(parent, exc)
        return FAILED


def hbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0), stretch_at: int | None = None) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for i, w in enumerate(widgets):
        if stretch_at == i:
            lay.addStretch(1)
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return lay
