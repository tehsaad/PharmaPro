from __future__ import annotations

from PySide6.QtWidgets import QGridLayout

from app.context import AppContext
from app.ui import theme
from app.ui.base import Page
from app.ui.charts import COST, PROFIT, REVENUE, ChartCanvas
from app.ui.range_picker import RangePicker
from app.ui.widgets import Card, PageHeader, StatCard, label
from app.utils.formatting import money_short


class AnalyticsPage(Page):
    title = "Analytics"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx, scroll=True)
        header = PageHeader("Analytics", "Revenue, cost and profit from your actual recorded transactions.")
        self.range = RangePicker("This Month")
        self.range.changed.connect(lambda *_: self.refresh())
        header.add_action(self.range)
        self.body.addWidget(header)

        kpis = QGridLayout()
        kpis.setSpacing(14)
        self.k_revenue = StatCard("Total revenue", "coins", theme.SERIES[0], "#E8F1FB")
        self.k_cogs = StatCard("Cost of goods sold", "package", COST, "#FDEEE6")
        self.k_gross = StatCard("Gross profit", "trending", theme.GOOD, theme.GOOD_BG)
        self.k_exp = StatCard("Expenses", "wallet", theme.CRITICAL, theme.CRITICAL_BG)
        self.k_net = StatCard("Net profit", "trending")
        self.k_count = StatCard("Number of sales", "receipt", theme.TEXT_2, theme.NEUTRAL_BG)
        self.k_avg = StatCard("Average sale value", "cart", theme.TEXT_2, theme.NEUTRAL_BG)
        self.k_disc = StatCard("Discounts given", "minus", theme.TEXT_2, theme.NEUTRAL_BG)
        for i, c in enumerate([self.k_revenue, self.k_cogs, self.k_gross, self.k_exp,
                               self.k_net, self.k_count, self.k_avg, self.k_disc]):
            kpis.addWidget(c, i // 4, i % 4)
        self.body.addLayout(kpis)

        grid = QGridLayout()
        grid.setSpacing(14)

        def chart_card(title: str, row: int, col: int, colspan: int = 1):
            card = Card(padding=16)
            card.add(label(title, "SectionTitle"))
            canvas = ChartCanvas(height=3.1)
            card.add(canvas, 1)
            grid.addWidget(card, row, col, 1, colspan)
            return canvas

        self.ch_sales = chart_card("Sales over time", 0, 0)
        self.ch_profit = chart_card("Gross profit over time", 0, 1)
        self.ch_rev_cost = chart_card("Revenue vs cost of goods", 1, 0, 2)
        self.ch_top = chart_card("Top-selling medicines (units)", 2, 0)
        self.ch_cat = chart_card("Sales by category", 2, 1)
        self.ch_low = chart_card("Low-stock medicines", 3, 0, 2)
        self.body.addLayout(grid)
        self.body.addStretch(1)

    def refresh(self) -> None:
        start, end = self.range.range()
        s = self.ctx.profit.summary(start, end)
        self.k_revenue.set(money_short(s.revenue), f"Subtotal before discounts {money_short(s.subtotal)}")
        self.k_cogs.set(money_short(s.cogs), "Actual batch cost of units sold")
        self.k_gross.set(money_short(s.gross_profit), f"{s.margin_pct:.1f}% margin")
        self.k_exp.set(money_short(s.expenses), "Rent, bills, salaries…")
        self.k_net.set(money_short(s.net_profit), "Gross profit − expenses",
                       theme.GOOD if s.net_profit >= 0 else theme.CRITICAL)
        self.k_count.set(f"{s.sales_count:,}", self.range.label_text())
        self.k_avg.set(money_short(s.average_sale), "Revenue ÷ number of sales")
        self.k_disc.set(money_short(s.discount), "Total discounts")

        df = self.ctx.analytics.timeseries(start, end)
        daily = self.ctx.analytics.granularity(start, end) == "day"
        x = [d.strftime("%d %b") if daily else d.strftime("%b %y") for d in df.index]
        tips = [d.strftime("%a %d %b %Y") if daily else d.strftime("%B %Y") for d in df.index]
        self.ch_sales.line(x, [("Revenue", list(df["revenue"]), REVENUE)], tips, fill_first=True)
        self.ch_profit.line(x, [("Gross profit", list(df["profit"]), PROFIT)], tips, fill_first=True)
        self.ch_rev_cost.bars(x, [("Revenue", list(df["revenue"]), REVENUE), ("Cost of goods", list(df["cost"]), COST)], tips)

        top = self.ctx.analytics.top_selling(start, end, limit=10)
        self.ch_top.hbars([t.name for t in top], [t.quantity for t in top], color=theme.ACCENT, money=False)
        cats = self.ctx.analytics.sales_by_category(start, end)[:10]
        self.ch_cat.hbars([c for c, _v in cats], [float(v) for _c, v in cats], color=REVENUE)
        low = self.ctx.inventory.low_stock()[:12]
        self.ch_low.hbars([m.name for m in low], [m.sellable_stock for m in low], color=theme.WARN, money=False,
                          reference=[self.ctx.inventory.reorder_point(m.reorder_level) for m in low],
                          reference_label="Reorder level")
