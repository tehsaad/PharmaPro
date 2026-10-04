from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem

from app.context import AppContext
from app.ui import theme
from app.ui.base import Page
from app.ui.charts import PROFIT, REVENUE, ChartCanvas
from app.ui.icons import icon
from app.ui.widgets import Card, Column, DataTable, PageHeader, StatCard, button, label
from app.utils.formatting import fmt_date, money_short, number


class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx, scroll=True)
        self.navigate = lambda *a, **k: None
        self.header = PageHeader("Dashboard", "")
        sale_btn = self.header.add_action(button("New sale", "cart", "primary", "Ctrl+N"))
        sale_btn.clicked.connect(lambda: self.navigate("sales"))
        stock_btn = self.header.add_action(button("Add stock", "package-plus"))
        stock_btn.clicked.connect(lambda: self.navigate("add_stock"))
        self.body.addWidget(self.header)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_stock = StatCard("Stock value (at cost)", "package")
        self.c_today = StatCard("Today's sales", "cart", theme.SERIES[0], "#E8F1FB")
        self.c_today_profit = StatCard("Today's profit", "trending", theme.GOOD, theme.GOOD_BG)
        self.c_month = StatCard("This month's sales", "coins", theme.SERIES[0], "#E8F1FB")
        self.c_month_profit = StatCard("This month's profit", "trending", theme.GOOD, theme.GOOD_BG)
        self.c_low = StatCard("Low stock items", "alert", theme.WARN, theme.WARN_BG)
        self.c_expiring = StatCard("Expiring soon", "hourglass", theme.SERIOUS, theme.SERIOUS_BG)
        self.c_expired = StatCard("Expired items", "ban", theme.CRITICAL, theme.CRITICAL_BG)
        cards = [self.c_stock, self.c_today, self.c_today_profit, self.c_month,
                 self.c_month_profit, self.c_low, self.c_expiring, self.c_expired]
        for i, c in enumerate(cards):
            grid.addWidget(c, i // 4, i % 4)
        self.c_low.clicked.connect(lambda: self.navigate("inventory", filter="Low Stock"))
        self.c_expiring.clicked.connect(lambda: self.navigate("inventory", filter="Expiring Soon"))
        self.c_expired.clicked.connect(lambda: self.navigate("inventory", filter="Expired"))
        for c in (self.c_low, self.c_expiring, self.c_expired):
            c.setCursor(Qt.PointingHandCursor)
            c.setToolTip("Click to view in Inventory")
        self.body.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(14)
        chart_card = Card()
        chart_card.add(label("Sales — last 14 days", "SectionTitle"))
        self.chart = ChartCanvas(height=2.9)
        chart_card.add(self.chart, 1)
        row.addWidget(chart_card, 3)

        alert_card = Card()
        alert_card.add(label("Needs attention", "SectionTitle"))
        self.alerts = QListWidget()
        self.alerts.setMinimumHeight(240)
        self.alerts.setStyleSheet("QListWidget { border: none; }")
        self.alerts.itemDoubleClicked.connect(self._open_alert)
        alert_card.add(self.alerts, 1)
        row.addWidget(alert_card, 2)
        self.body.addLayout(row)

        recent_card = Card()
        head = QHBoxLayout()
        head.addWidget(label("Recent sales", "SectionTitle"))
        head.addStretch(1)
        view_all = button("Sales history", "clock", "ghost")
        view_all.clicked.connect(lambda: self.navigate("sales", history=True))
        head.addWidget(view_all)
        recent_card.add(head)
        self.recent = DataTable([
            Column("Receipt", lambda s: s.receipt_number, width=170, bold=True),
            Column("Time", lambda s: s.sale_date, "datetime", width=200),
            Column("Total", lambda s: s.total, "money", width=130),
            Column("Discount", lambda s: s.discount, "money", width=110),
            Column("Profit", lambda s: s.gross_profit, "money", width=120, stretch=True),
        ], "No sales yet today", "Completed sales will appear here.", "receipt", row_height=36, sort=None)
        self.recent.setMinimumHeight(260)
        recent_card.add(self.recent)
        self.body.addWidget(recent_card)
        self.body.addStretch(1)

    def refresh(self) -> None:
        ctx = self.ctx
        today = date.today()
        hour = datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        self.header.subtitle.setText(f"{greet} — {ctx.settings.get('pharmacy_name')} · {today:%A, %d %B %Y}")

        day = ctx.profit.summary(today, today)
        month = ctx.profit.summary(today.replace(day=1), today)
        self.c_stock.set(money_short(ctx.inventory.stock_value()), f"Retail value {money_short(ctx.inventory.retail_value())}")
        self.c_today.set(money_short(day.revenue), f"{day.sales_count} sale(s)")
        self.c_today_profit.set(money_short(day.gross_profit),
                                f"{day.margin_pct:.1f}% margin" if day.revenue else "No sales yet today")
        self.c_month.set(money_short(month.revenue), f"{month.sales_count} sale(s) since {today.replace(day=1):%d %b}")
        net_color = theme.GOOD if month.net_profit >= 0 else theme.CRITICAL
        self.c_month_profit.set(money_short(month.gross_profit), f"Net after expenses {money_short(month.net_profit)}", net_color)

        low = ctx.inventory.low_stock()
        warn_days = ctx.settings.expiry_warning_days
        expiring = ctx.inventory.expiring_batches(warn_days)
        expired = ctx.inventory.expired_batches()
        buckets = ctx.inventory.expiry_buckets()
        self.c_low.set(number(len(low)), "At or below reorder level")
        self.c_expiring.set(number(len(expiring)),
                            f"{buckets['30']} in 30 · {buckets['60']} in 60 · {buckets['90']} in 90 days")
        self.c_expired.set(number(len(expired)), f"Value {money_short(ctx.inventory.expired_value())} — do not sell",
                           theme.CRITICAL if expired else None)

        self.alerts.clear()

        def add(text, sub, icon_name, color, target):
            item = QListWidgetItem(icon(icon_name, color, 18), f"{text}\n{sub}")
            item.setData(Qt.UserRole, target)
            self.alerts.addItem(item)

        for r in expired[:6]:
            add(f"{r.medicine} — batch {r.batch_number}", f"EXPIRED on {fmt_date(r.expiry_date)} · {r.quantity_remaining} units — remove from shelf",
                "ban", theme.CRITICAL, "Expired")
        for r in sorted(expiring, key=lambda r: r.expiry_date)[:6]:
            add(f"{r.medicine} — batch {r.batch_number}", f"Expires in {r.days_to_expiry} days ({fmt_date(r.expiry_date)}) · {r.quantity_remaining} units",
                "hourglass", theme.SERIOUS, "Expiring Soon")
        for m in low[:8]:
            sub = "Out of stock" if m.sellable_stock == 0 else f"Only {m.sellable_stock} left (reorder at {ctx.inventory.reorder_point(m.reorder_level)})"
            add(f"{m.name} ({m.code})", sub, "alert", theme.WARN, "Low Stock")
        if not self.alerts.count():
            item = QListWidgetItem(icon("check", theme.GOOD, 18), "All clear\nNo stock or expiry problems right now.")
            self.alerts.addItem(item)

        start = today - timedelta(days=13)
        df = ctx.analytics.timeseries(start, today)
        x = [d.strftime("%d %b") for d in df.index]
        labels = [d.strftime("%a %d %b") for d in df.index]
        self.chart.line(x, [("Revenue", list(df["revenue"]), REVENUE), ("Gross profit", list(df["profit"]), PROFIT)],
                        labels, fill_first=True)

        self.recent.set_rows(ctx.sales.list(today - timedelta(days=7), today, limit=10))

    def _open_alert(self, item: QListWidgetItem):
        target = item.data(Qt.UserRole)
        if target:
            self.navigate("inventory", filter=target)
