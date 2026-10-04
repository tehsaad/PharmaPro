"""Matplotlib charts embedded in Qt, styled to match the app.

Conventions: one y-axis per chart, thin marks, recessive grid, a legend whenever
there are two or more series, and a hover tooltip on every chart.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from app.ui import theme  # noqa: E402
from app.utils.formatting import currency_symbol  # noqa: E402

GRID = "#E9EDF2"
AXIS = "#94A3B8"
INK = "#334155"
INK_MUTED = "#64748B"

REVENUE = theme.SERIES[0]
COST = theme.SERIES[1]
PROFIT = theme.SERIES[2]


def _compact(v: float, _pos=None) -> str:
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if a >= 1_000:
        return f"{v / 1_000:.0f}k" if a >= 10_000 else f"{v / 1_000:.1f}k"
    return f"{v:.0f}"


def _money(v: float) -> str:
    return f"{currency_symbol()} {v:,.0f}"


class ChartCanvas(FigureCanvasQTAgg):
    def __init__(self, height: float = 3.0):
        self.fig = Figure(figsize=(5, height), dpi=100, facecolor="white")
        super().__init__(self.fig)
        self.setMinimumHeight(int(height * 82))
        self.ax = self.fig.add_subplot(111)
        self._hover_points: list[tuple[float, float, str]] = []
        self._hover_rects: list[tuple[object, str]] = []
        self._tip = None
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("figure_leave_event", lambda _e: self._hide_tip())

    # ------------------------------------------------------------ helpers
    def _reset(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self._hover_points, self._hover_rects = [], []
        self._tip = None
        ax = self.ax
        ax.set_facecolor("white")
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK_MUTED, labelsize=8.5, length=0, pad=6)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    def _finish(self, legend: bool = False):
        if legend:
            leg = self.ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=4,
                                 bbox_to_anchor=(0, 1.13), handlelength=1.4, labelcolor=INK)
            leg.set_in_layout(True)
        self.fig.tight_layout(pad=1.0)
        self._tip = self.ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points", fontsize=8.5, color="white",
            bbox=dict(boxstyle="round,pad=0.5", fc=theme.NAVY, ec="none", alpha=0.95), zorder=10,
        )
        self._tip.set_visible(False)
        self.draw_idle()

    def empty(self, message: str = "No data for this period"):
        ax = self._reset()
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines["bottom"].set_visible(False)
        ax.grid(False)
        ax.text(0.5, 0.5, message, ha="center", va="center", color=INK_MUTED, fontsize=10, transform=ax.transAxes)
        self.fig.tight_layout()
        self.draw_idle()

    # ------------------------------------------------------------- charts
    def line(self, x, series: list[tuple[str, list[float], str]], labels: list[str], money: bool = True,
             fill_first: bool = False):
        """Line chart over time. ``labels`` are the tooltip names of each x point."""
        if not len(x) or all(not any(v) for _n, v, _c in series):
            self.empty()
            return
        ax = self._reset()
        idx = list(range(len(x)))
        for n, (name, values, color) in enumerate(series):
            ax.plot(idx, values, color=color, linewidth=2, label=name, solid_capstyle="round",
                    marker="o" if len(idx) <= 31 else None, markersize=3.5, markeredgewidth=0)
            if fill_first and n == 0:
                ax.fill_between(idx, values, color=color, alpha=0.08, linewidth=0)
        for i in idx:
            lines = [labels[i]] + [f"{name}: {_money(vals[i]) if money else int(vals[i])}" for name, vals, _ in series]
            top = max(vals[i] for _n, vals, _c in series)
            self._hover_points.append((i, top, "\n".join(lines)))
        self._x_ticks(ax, x)
        ax.yaxis.set_major_formatter(FuncFormatter(_compact))
        ax.yaxis.set_major_locator(MaxNLocator(5))
        ax.set_ylim(bottom=min(0, min(min(v) for _n, v, _c in series)))
        self._finish(legend=len(series) > 1)

    def bars(self, x, series: list[tuple[str, list[float], str]], labels: list[str]):
        """Grouped vertical bars (e.g. revenue vs cost per period)."""
        if not len(x) or all(not any(v) for _n, v, _c in series):
            self.empty()
            return
        ax = self._reset()
        n = len(series)
        width = 0.8 / n
        for k, (name, values, color) in enumerate(series):
            pos = [i - 0.4 + width * (k + 0.5) for i in range(len(x))]
            rects = ax.bar(pos, values, width=width * 0.88, color=color, label=name, linewidth=0)
            for r, i in zip(rects, range(len(x))):
                self._hover_rects.append((r, f"{labels[i]}\n{name}: {_money(values[i])}"))
        self._x_ticks(ax, x)
        ax.yaxis.set_major_formatter(FuncFormatter(_compact))
        ax.yaxis.set_major_locator(MaxNLocator(5))
        self._finish(legend=n > 1)

    def hbars(self, names: list[str], values: list[float], color: str = theme.ACCENT, money: bool = True,
              reference: list[float] | None = None, reference_label: str = ""):
        """Horizontal ranked bars, largest on top. Optional reference tick (e.g. reorder level)."""
        if not names:
            self.empty("Nothing to show")
            return
        ax = self._reset()
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.spines["bottom"].set_visible(False)
        ys = list(range(len(names)))[::-1]
        rects = ax.barh(ys, values, color=color, height=0.62, linewidth=0, label="In stock" if reference else None)
        ax.set_yticks(ys)
        ax.set_yticklabels([n if len(n) <= 22 else n[:21] + "…" for n in names], color=INK, fontsize=8.5)
        ax.xaxis.set_major_formatter(FuncFormatter(_compact))
        ax.xaxis.set_major_locator(MaxNLocator(5))
        for i, (r, n, v) in enumerate(zip(rects, names, values)):
            ax.text(r.get_width(), r.get_y() + r.get_height() / 2, f"  {_compact(v)}", va="center",
                    fontsize=8, color=INK_MUTED)
            if reference:
                tip = f"{n}\nIn stock: {int(v):,}\n{reference_label}: {int(reference[i]):,}"
            else:
                tip = f"{n}\n{_money(v) if money else f'{int(v):,} units'}"
            self._hover_rects.append((r, tip))
        if reference:
            ax.scatter(reference, ys, marker="|", s=260, color=theme.CRITICAL, linewidths=2,
                       label=reference_label, zorder=5)
        ax.set_xlim(right=max(list(values) + list(reference or [0])) * 1.18 or 1)
        self._finish(legend=bool(reference))

    @staticmethod
    def _x_ticks(ax, x):
        n = len(x)
        step = max(1, -(-n // 7))  # at most ~7 labels so dates never overlap
        ticks = list(range(0, n, step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([x[i] for i in ticks], fontsize=8.5, color=INK_MUTED)
        ax.set_xlim(-0.6, n - 0.4)

    # -------------------------------------------------------------- hover
    def _hide_tip(self):
        if self._tip is not None and self._tip.get_visible():
            self._tip.set_visible(False)
            self.draw_idle()

    def _on_move(self, event):
        if self._tip is None or event.inaxes != self.ax:
            self._hide_tip()
            return
        for rect, text in self._hover_rects:
            if rect.contains(event)[0]:
                self._show_tip(rect.get_x() + rect.get_width() / 2, rect.get_y() + rect.get_height(), text, event)
                return
        if self._hover_points and event.xdata is not None:
            i = int(round(event.xdata))
            if 0 <= i < len(self._hover_points):
                x, y, text = self._hover_points[i]
                self._show_tip(x, y, text, event)
                return
        self._hide_tip()

    def _show_tip(self, x, y, text, event):
        self._tip.xy = (x, y)
        # keep the tooltip inside the plot: flip to the left on the right half
        w = self.ax.bbox.width
        dx = -12 if event.x - self.ax.bbox.x0 > w * 0.6 else 12
        self._tip.set_position((dx, 10))
        self._tip.set_ha("right" if dx < 0 else "left")
        self._tip.set_text(text)
        self._tip.set_visible(True)
        self.draw_idle()
