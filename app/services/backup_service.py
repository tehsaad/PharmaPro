"""Local database backup and restore using SQLite's online backup API.

The backup API produces a consistent copy even while the app is running.
A restore always takes a safety backup of the current data first.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.database.database import Database
from app.services.errors import BackupError

log = logging.getLogger(__name__)

PREFIX = "PharmaPro_Backup_"
AUTO_PREFIX = "PharmaPro_AutoBackup_"
SAFETY_PREFIX = "PharmaPro_BeforeRestore_"
REQUIRED_TABLES = {"medicines", "batches", "sales", "sale_items", "purchases", "expenses", "settings"}


@dataclass
class BackupInfo:
    path: Path
    created: datetime
    size_bytes: int
    kind: str  # Manual / Automatic / Before restore


class BackupService:
    def __init__(self, db: Database, backup_dir: Path):
        self.db = db
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _target(self, prefix: str, folder: Path | None) -> Path:
        folder = Path(folder) if folder else self.backup_dir
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        path = folder / f"{prefix}{stamp}.db"
        n = 2
        while path.exists():
            path = folder / f"{prefix}{stamp}_{n}.db"
            n += 1
        return path

    @staticmethod
    def _copy(src: Path, dst: Path) -> None:
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(dst))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

    def create_backup(self, folder: Path | None = None, prefix: str = PREFIX) -> Path:
        if not self.db.path.exists():
            raise BackupError("There is no database to back up yet.")
        target = self._target(prefix, folder)
        try:
            self._copy(self.db.path, target)
        except (sqlite3.Error, OSError) as exc:
            log.exception("Backup failed")
            target.unlink(missing_ok=True)
            raise BackupError(
                "The backup could not be created. Please check that the backup folder exists and is not read-only."
            ) from exc
        log.info("Backup created: %s", target.name)
        return target

    def validate_backup(self, path: Path) -> None:
        path = Path(path)
        if not path.is_file():
            raise BackupError("The selected backup file could not be found.")
        try:
            with open(path, "rb") as fh:
                if fh.read(16) != b"SQLite format 3\x00":
                    raise BackupError("The selected file is not a PharmaPro backup.")
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise BackupError("The selected backup file is damaged and cannot be restored.")
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise BackupError("The selected file is not a valid PharmaPro backup.") from exc
        if not REQUIRED_TABLES.issubset(tables):
            raise BackupError("The selected file is not a PharmaPro backup.")

    def restore(self, path: Path) -> Path:
        """Replace the active database with ``path``. Returns the safety-backup path.

        The caller must have asked the user for confirmation first.
        """
        path = Path(path)
        self.validate_backup(path)
        if path.resolve() == self.db.path.resolve():
            raise BackupError("That is the database currently in use. Please choose a backup file.")
        safety = self.create_backup(prefix=SAFETY_PREFIX)
        self.db.dispose()
        try:
            self._copy(path, self.db.path)
        except (sqlite3.Error, OSError) as exc:
            log.exception("Restore failed, rolling back to safety copy")
            try:
                self._copy(safety, self.db.path)
            finally:
                self.db.reconnect()
            raise BackupError("The restore could not be completed. Your previous data has been kept.") from exc
        self.db.reconnect()
        log.info("Database restored from %s", path.name)
        return safety

    def list_backups(self) -> list[BackupInfo]:
        out = []
        for p in self.backup_dir.glob("PharmaPro_*.db"):
            kind = "Automatic" if p.name.startswith(AUTO_PREFIX) else (
                "Before restore" if p.name.startswith(SAFETY_PREFIX) else "Manual")
            st = p.stat()
            out.append(BackupInfo(p, datetime.fromtimestamp(st.st_mtime), st.st_size, kind))
        return sorted(out, key=lambda b: b.created, reverse=True)

    def auto_backup(self, keep: int = 30) -> Path | None:
        """Take at most one automatic backup per day and prune old automatic ones."""
        today = date.today().strftime("%Y-%m-%d")
        if any(p.name.startswith(f"{AUTO_PREFIX}{today}") for p in self.backup_dir.glob(f"{AUTO_PREFIX}*.db")):
            return None
        path = self.create_backup(prefix=AUTO_PREFIX)
        autos = sorted(self.backup_dir.glob(f"{AUTO_PREFIX}*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in autos[max(keep, 1):]:
            old.unlink(missing_ok=True)
        return path
