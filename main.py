"""PharmaPro - offline pharmacy management system.

Run:  python main.py
Options:
  --home PATH      use PATH for data/, backups/, logs/ (default: project folder)
  --sample-data    load fictional demonstration data into an empty database
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="PharmaPro - offline pharmacy management")
    parser.add_argument("--home", help="folder for data, backups and logs")
    parser.add_argument("--sample-data", action="store_true", help="load demo data into an empty database")
    return parser.parse_known_args(argv)[0]


def main(argv=None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.home:
        os.environ["PHARMAPRO_HOME"] = args.home

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.config import APP_NAME, Paths, setup_logging

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    from app.ui.icons import logo_icon
    from app.ui.theme import apply_theme

    apply_theme(app)
    app.setWindowIcon(logo_icon())

    try:
        paths = Paths()
        setup_logging(paths.logs)
    except OSError:
        QMessageBox.critical(None, APP_NAME, "PharmaPro cannot write to its data folder.\n\n"
                             "Please run it from a folder you have permission to write to.")
        return 1
    log = logging.getLogger("pharmapro")

    # Only one PharmaPro window per data folder (a single-file exe can be double-clicked twice
    # while it is still unpacking).
    from PySide6.QtCore import QLockFile

    lock = QLockFile(str(paths.data / "pharmapro.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        lock.removeStaleLockFile()
        if not lock.tryLock(100):
            QMessageBox.information(None, APP_NAME, "PharmaPro is already running.\n\n"
                                    "Look for its window in the taskbar.")
            return 0

    def excepthook(exc_type, exc, tb):
        log.error("Unhandled error:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        from app.ui.widgets import show_exception
        show_exception(QApplication.activeWindow(), exc)

    sys.excepthook = excepthook

    from app.context import AppContext

    try:
        ctx = AppContext(paths.home)
        if not ctx.db.integrity_ok():
            QMessageBox.warning(None, APP_NAME, "The database may be damaged. Please restore a recent backup "
                                "from the Backup screen as soon as possible.")
    except Exception:
        log.exception("Database could not be opened")
        QMessageBox.critical(None, APP_NAME, "The PharmaPro database could not be opened.\n\n"
                             f"Location: {paths.database}\n\nIf you have a backup, copy it to this location "
                             "(renamed to pharmapro.db) and start PharmaPro again.")
        return 1

    if args.sample_data:
        from app.services import sample_data
        if not sample_data.has_data(ctx):
            sample_data.seed(ctx)

    from app.ui.main_window import MainWindow

    window = MainWindow(ctx)
    window.showMaximized() if os.environ.get("QT_QPA_PLATFORM") != "offscreen" else window.show()

    def startup_backup():
        if ctx.settings.get_bool("auto_backup"):
            try:
                if ctx.backups.auto_backup(keep=ctx.settings.get_int("backup_keep")):
                    log.info("Automatic daily backup created")
            except Exception:
                log.exception("Automatic backup failed")

    QTimer.singleShot(1500, startup_backup)
    code = app.exec()
    ctx.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
