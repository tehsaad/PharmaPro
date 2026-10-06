"""Application paths, constants and logging configuration.

Everything PharmaPro stores lives on the local disk. Locations are resolved as:

1. ``PHARMAPRO_HOME`` environment variable, if set.
2. The folder of the packaged executable (when it is writable).
3. A per-user application-data folder (when the executable folder is read-only,
   e.g. installed under *Program Files*).
4. The project root when running from source.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "PharmaPro"
APP_VERSION = "1.0.0"
DB_FILENAME = "pharmapro.db"


def _is_writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _user_data_dir() -> Path:
    if sys.platform.startswith("win"):
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_NAME


def resource_dir() -> Path:
    """Folder that holds bundled read-only resources (icons)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "app" / "resources"
    return Path(__file__).resolve().parent / "resources"


def app_home() -> Path:
    env = os.environ.get("PHARMAPRO_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if _is_writable(exe_dir / "data"):
            return exe_dir
        return _user_data_dir()
    return Path(__file__).resolve().parent.parent


class Paths:
    """Resolved runtime folders. Created on construction."""

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else app_home()
        self.data = self.home / "data"
        self.backups = self.home / "backups"
        self.logs = self.home / "logs"
        self.receipts = self.home / "receipts"
        self.exports = self.home / "exports"
        for folder in (self.data, self.backups, self.logs, self.receipts, self.exports):
            folder.mkdir(parents=True, exist_ok=True)

    @property
    def database(self) -> Path:
        return self.data / DB_FILENAME


def setup_logging(log_dir: Path) -> None:
    """Log technical errors locally. Logs never leave the computer."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    handler = RotatingFileHandler(log_dir / "pharmapro.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # SQL statements may contain business data; keep them out of the log.
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
