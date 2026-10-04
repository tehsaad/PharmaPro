"""Wires the database and all services together (simple dependency injection)."""
from __future__ import annotations

from pathlib import Path

from app.analytics.analytics_service import AnalyticsService
from app.config import Paths
from app.database.database import Database
from app.services.backup_service import BackupService
from app.services.expense_service import ExpenseService
from app.services.inventory_service import InventoryService
from app.services.medicine_service import MedicineService
from app.services.profit_service import ProfitService
from app.services.purchase_service import PurchaseService
from app.services.receipt_service import ReceiptService
from app.services.reporting_service import ReportingService
from app.services.sales_service import SalesService
from app.services.settings_service import SettingsService


class AppContext:
    def __init__(self, home: Path | None = None):
        self.paths = Paths(home)
        self.db = Database(self.paths.database)
        self.db.init_schema()
        self.settings = SettingsService(self.db)
        self.medicines = MedicineService(self.db)
        self.inventory = InventoryService(self.db, self.settings)
        self.purchases = PurchaseService(self.db)
        self.sales = SalesService(self.db)
        self.expenses = ExpenseService(self.db)
        self.profit = ProfitService(self.db)
        self.analytics = AnalyticsService(self.db)
        self.receipts = ReceiptService(self.settings, self.paths.receipts)
        self.reports = ReportingService(self.sales, self.purchases, self.inventory, self.expenses,
                                        self.analytics, self.settings)
        self.backups = BackupService(self.db, self.paths.backups)
        self.settings.all()  # warm cache + apply currency symbol

    def after_restore(self) -> None:
        self.settings.invalidate()
        self.settings.all()

    def close(self) -> None:
        self.db.dispose()
