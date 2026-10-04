from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from app.context import AppContext
from app.ui import theme
from app.ui.base import Page
from app.ui.dialogs.receipt_dialog import open_file
from app.ui.widgets import (
    FAILED,
    Banner,
    Card,
    Column,
    DataTable,
    PageHeader,
    Toast,
    button,
    confirm,
    hbox,
    info,
    label,
    run_safely,
)


def _size(n: int) -> str:
    return f"{n / 1024:,.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:,.1f} MB"


class BackupPage(Page):
    title = "Backup"

    def __init__(self, ctx: AppContext):
        super().__init__(ctx)
        self.on_restored = lambda: None
        header = PageHeader("Backup & Restore", "Your data lives only on this computer — keep regular copies safe.")
        self.body.addWidget(header)

        banner = Banner("Tip: copy a backup to a USB drive regularly. If this computer is lost or damaged, "
                        "a backup on another device is the only way to recover your records.", "info")
        self.body.addWidget(banner)

        actions = Card()
        actions.add(label("Back up", "SectionTitle"))
        actions.add(label("Creates a complete copy of the database. Safe to do at any time, even during work.", "Muted"))
        now = button("Back up now", "database", "primary")
        now.clicked.connect(self.backup_now)
        to = button("Back up to USB / folder…", "folder")
        to.clicked.connect(self.backup_to)
        actions.add(hbox(now, to, None))
        actions.add(label("Restore", "SectionTitle"))
        actions.add(label("Replaces ALL current data with a backup. A safety copy of the current data is made first.", "Muted"))
        restore_file = button("Restore from file…", "upload", "danger")
        restore_file.clicked.connect(self.restore_from_file)
        actions.add(hbox(restore_file, None))
        self.body.addWidget(actions)

        lst = Card()
        lst.add(hbox(label("Backups on this computer", "SectionTitle"), None, label(str(ctx.paths.backups), "Muted")))
        self.table = DataTable([
            Column("Created", lambda b: b.created, "datetime", width=210),
            Column("File", lambda b: b.path.name, width=360, bold=True),
            Column("Size", lambda b: _size(b.size_bytes), width=100, align_right=True),
            Column("Type", lambda b: b.kind, "status", width=150, stretch=True),
        ], "No backups yet", "Click “Back up now” to create your first backup.", "database", sort=None)
        lst.add(self.table, 1)
        restore_sel = button("Restore selected", "upload", "danger")
        restore_sel.clicked.connect(lambda: self._restore(self.table.selected().path if self.table.selected() else None))
        folder = button("Open backup folder", "folder")
        folder.clicked.connect(lambda: open_file(ctx.paths.backups))
        lst.add(hbox(folder, None, restore_sel))
        self.body.addWidget(lst, 1)

    def refresh(self) -> None:
        self.table.set_rows(self.ctx.backups.list_backups())

    def backup_now(self):
        res = run_safely(self, self.ctx.backups.create_backup)
        if res is not FAILED:
            Toast.show_message(self, f"Backup created: {res.name}")
            self.refresh()

    def backup_to(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose where to save the backup")
        if not folder:
            return
        res = run_safely(self, self.ctx.backups.create_backup, Path(folder))
        if res is not FAILED:
            info(self, "Backup saved", f"The backup was saved to:\n{res}")

    def restore_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a PharmaPro backup", str(self.ctx.paths.backups),
                                              "PharmaPro backups (*.db);;All files (*)")
        if path:
            self._restore(Path(path))

    def _restore(self, path: Path | None):
        if path is None:
            return
        if run_safely(self, self.ctx.backups.validate_backup, path) is FAILED:
            return
        if not confirm(self, "Replace all current data?",
                       f"Restore from “{path.name}”?\n\nAll current medicines, stock, sales and expenses will be "
                       "replaced by the contents of this backup.\n\nA safety copy of your current data will be "
                       "saved first, so this can be undone.", "Restore backup", danger=True):
            return
        res = run_safely(self, self.ctx.backups.restore, path)
        if res is FAILED:
            return
        self.ctx.after_restore()
        self.on_restored()
        info(self, "Restore complete",
             f"Your data has been restored from {path.name}.\n\nThe previous data was saved as:\n{res.name}")
        self.refresh()
