# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build configuration for PharmaPro.
#
#   pyinstaller --noconfirm PharmaPro.spec
#
# Produces a one-folder build in dist/PharmaPro/ containing PharmaPro.exe (Windows)
# or PharmaPro (Linux). On first launch the app creates data/, backups/, logs/,
# receipts/ and exports/ next to the executable (or in the user's AppData folder
# when installed somewhere read-only such as Program Files).
import sys

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("app/resources", "app/resources")],
    hiddenimports=[
        "PySide6.QtSvg",
        "PySide6.QtPrintSupport",
        "sqlalchemy.dialects.sqlite",
        "matplotlib.backends.backend_qtagg",
        "reportlab.graphics.barcode.common",
        "reportlab.graphics.barcode.code128",
        "reportlab.graphics.barcode.code39",
        "reportlab.graphics.barcode.code93",
        "reportlab.graphics.barcode.usps",
        "reportlab.graphics.barcode.usps4s",
        "reportlab.graphics.barcode.ecc200datamatrix",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "PyQt5", "PyQt6", "IPython", "jupyter", "notebook", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtPositioning",
    ],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon = "app/resources/icons/pharmapro.ico" if sys.platform.startswith("win") else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PharmaPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app: no terminal window
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="PharmaPro")
