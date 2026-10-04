from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QLineEdit, QSpinBox

from app.context import AppContext
from app.printing import receipt_printer
from app.services import sample_data
from app.ui.base import Page
from app.ui.widgets import FAILED, Card, PageHeader, Toast, button, confirm, field, hbox, label, run_safely, warn
from app.utils.constants import PAPER_SIZES

SYSTEM_DEFAULT = "System default printer"


class SettingsPage(Page):
    title = "Settings"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx, scroll=True)
        self.on_data_changed = lambda: None
        header = PageHeader("Settings", "Pharmacy details, receipts, inventory warnings and currency.")
        save = header.add_action(button("Save settings", "save", "primary", "Ctrl+S"))
        save.clicked.connect(self.handle_save)
        self.body.addWidget(header)

        # --- pharmacy
        c1 = Card()
        c1.add(label("Pharmacy information", "SectionTitle"))
        c1.add(label("Printed at the top of every receipt and report.", "Muted"))
        self.name = QLineEdit()
        self.address = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.license = QLineEdit()
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        g.addWidget(field("Pharmacy name *", self.name), 0, 0)
        g.addWidget(field("Phone", self.phone), 0, 1)
        g.addWidget(field("Address", self.address), 1, 0)
        g.addWidget(field("Email", self.email), 1, 1)
        g.addWidget(field("Drug license no. (optional)", self.license), 2, 0)
        c1.add(g)
        self.body.addWidget(c1)

        # --- receipt
        c2 = Card()
        c2.add(label("Receipts & printer", "SectionTitle"))
        self.footer = QLineEdit()
        self.paper = QComboBox()
        for key, text in PAPER_SIZES.items():
            self.paper.addItem(text, key)
        self.printer = QComboBox()
        self.prompt = QCheckBox("After each sale, ask whether to print the receipt")
        test = button("Test print", "printer")
        test.clicked.connect(self._test_print)
        g2 = QGridLayout()
        g2.setHorizontalSpacing(14)
        g2.setVerticalSpacing(10)
        g2.addWidget(field("Receipt footer", self.footer), 0, 0, 1, 2)
        g2.addWidget(field("Paper size", self.paper, "Thermal 80 mm suits most receipt printers"), 1, 0)
        g2.addWidget(field("Receipt printer", self.printer), 1, 1)
        c2.add(g2)
        c2.add(hbox(self.prompt, None, test))
        self.body.addWidget(c2)

        # --- inventory + currency
        c3 = Card()
        c3.add(label("Inventory & currency", "SectionTitle"))
        self.low = QSpinBox()
        self.low.setRange(0, 1_000_000)
        self.expiry = QSpinBox()
        self.expiry.setRange(1, 3650)
        self.expiry.setSuffix(" days")
        self.symbol = QLineEdit()
        self.symbol.setMaxLength(6)
        self.code = QLineEdit()
        self.code.setMaxLength(6)
        g3 = QGridLayout()
        g3.setHorizontalSpacing(14)
        g3.setVerticalSpacing(10)
        g3.addWidget(field("Default low-stock threshold", self.low,
                           "Used for medicines without their own reorder level"), 0, 0)
        g3.addWidget(field("Expiry warning", self.expiry, "Batches expiring within this many days are flagged"), 0, 1)
        g3.addWidget(field("Currency symbol", self.symbol, "Shown on screens and receipts, e.g. Rs. (restart to update every screen)"), 1, 0)
        g3.addWidget(field("Currency code", self.code, "e.g. PKR"), 1, 1)
        c3.add(g3)
        self.body.addWidget(c3)

        # --- backup + data
        c4 = Card()
        c4.add(label("Data safety", "SectionTitle"))
        self.auto_backup = QCheckBox("Automatically back up the database once a day when PharmaPro starts")
        self.keep = QSpinBox()
        self.keep.setRange(1, 365)
        self.keep.setSuffix(" automatic backups")
        c4.add(self.auto_backup)
        c4.add(hbox(label("Keep the latest"), self.keep, None))
        c4.add(label(f"Database file: {ctx.db.path}", "Muted"))
        demo = button("Load sample data", "database")
        demo.setToolTip("Adds fictional medicines, stock, sales and expenses so you can try PharmaPro. Only works on an empty database.")
        demo.clicked.connect(self._load_sample)
        c4.add(hbox(demo, label("For demonstration only — only available while the database is empty.", "Muted"), None))
        self.body.addWidget(c4)
        self.body.addStretch(1)

    def refresh(self) -> None:
        s = self.ctx.settings.all()
        self.name.setText(s["pharmacy_name"])
        self.address.setText(s["address"])
        self.phone.setText(s["phone"])
        self.email.setText(s["email"])
        self.license.setText(s.get("license_number", ""))
        self.footer.setText(s["receipt_footer"])
        self.paper.setCurrentIndex(max(0, self.paper.findData(s["receipt_paper"])))
        self.printer.clear()
        self.printer.addItem(SYSTEM_DEFAULT, "")
        for p in receipt_printer.printers_available():
            self.printer.addItem(p, p)
        if s["printer_name"] and self.printer.findData(s["printer_name"]) < 0:
            self.printer.addItem(f"{s['printer_name']} (not connected)", s["printer_name"])
        self.printer.setCurrentIndex(max(0, self.printer.findData(s["printer_name"])))
        self.prompt.setChecked(s["auto_print_prompt"] == "1")
        self.low.setValue(int(s["low_stock_threshold"] or 0))
        self.expiry.setValue(int(s["expiry_warning_days"] or 90))
        self.symbol.setText(s["currency_symbol"])
        self.code.setText(s["currency_code"])
        self.auto_backup.setChecked(s["auto_backup"] == "1")
        self.keep.setValue(int(s["backup_keep"] or 30))

    def handle_save(self) -> bool:
        values = {
            "pharmacy_name": self.name.text(), "address": self.address.text(), "phone": self.phone.text(),
            "email": self.email.text(), "license_number": self.license.text(), "receipt_footer": self.footer.text(),
            "receipt_paper": self.paper.currentData(), "printer_name": self.printer.currentData() or "",
            "auto_print_prompt": "1" if self.prompt.isChecked() else "0",
            "low_stock_threshold": str(self.low.value()), "expiry_warning_days": str(self.expiry.value()),
            "currency_symbol": self.symbol.text(), "currency_code": self.code.text(),
            "auto_backup": "1" if self.auto_backup.isChecked() else "0", "backup_keep": str(self.keep.value()),
        }
        if run_safely(self, self.ctx.settings.update, values) is not FAILED:
            Toast.show_message(self, "Settings saved")
            self.on_data_changed()
        return True

    def _test_print(self):
        from datetime import datetime
        from decimal import Decimal

        from app.services.receipt_service import ReceiptData, ReceiptLine
        s = self.ctx.settings.all()
        data = ReceiptData(self.name.text() or s["pharmacy_name"], self.address.text(), self.phone.text(), self.email.text(),
                           self.license.text(), "TEST-PRINT", datetime.now(),
                           [ReceiptLine("Test item", 1, Decimal("100.00"), Decimal("100.00"))],
                           Decimal("100.00"), Decimal("0"), Decimal("100.00"), None, self.footer.text(), self.symbol.text())
        paper = self.paper.currentData()
        html = self.ctx.receipts.render_html(data, paper)
        if not receipt_printer.printers_available():
            warn(self, "No printer found", "No printer is installed on this computer. Install the printer driver and try again.")
            return
        run_safely(self, receipt_printer.preview, self, html, paper, self.printer.currentData() or "")

    def _load_sample(self):
        if sample_data.has_data(self.ctx):
            warn(self, "Database is not empty", "Sample data can only be loaded into an empty database, so your real records are never mixed with demo data.")
            return
        if not confirm(self, "Load sample data?", "Fictional medicines, stock, sales and expenses will be added for demonstration.", "Load sample data"):
            return
        res = run_safely(self, sample_data.seed, self.ctx)
        if res is not FAILED:
            Toast.show_message(self, f"Sample data loaded: {res['medicines']} medicines, {res['sales']} sales")
            self.on_data_changed()
