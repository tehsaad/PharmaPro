# -*- mode: python ; coding: utf-8 -*-
# Single-file build of PharmaPro (one PharmaPro.exe on Windows, one PharmaPro binary on Linux).
#
#   pyinstaller --noconfirm --clean PharmaPro-onefile.spec
#
# The executable unpacks itself to a temporary folder at start-up. All user data
# (data/, backups/, logs/, receipts/, exports/) is created NEXT TO the executable,
# or in the user's application-data folder when that location is read-only.
import re
import sys

block_cipher = None
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

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
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "PyQt5", "PyQt6", "IPython", "jupyter", "notebook", "pytest",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPdf",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtVirtualKeyboard",
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------- slimming
# Qt modules PharmaPro never uses (pulled in only by optional plugins).
UNUSED = re.compile(
    r"(Qt6?(Quick|Qml|VirtualKeyboard|Pdf|WebEngine|3D|Multimedia|Charts|DataVisualization|Bluetooth|"
    r"Positioning|Sensors|SerialPort|Test|Designer|Help|ShaderTools|SpatialAudio|Location|RemoteObjects|Scxml)"
    r"|qtvirtualkeyboard|imageformats[/\\](lib)?qpdf|platformthemes[/\\]libqgtk3|"
    r"[/\\]translations[/\\]|qml[/\\])",
    re.IGNORECASE,
)

# Linux: never bundle the build machine's own system libraries. They are tied to its
# glibc version and would stop the binary from running on other distributions; the
# target desktop provides its own copies (X11/Wayland, fontconfig, OpenGL, libstdc++…).
SYSTEM_PREFIXES = ("/usr/", "/lib/", "/lib64/")


def keep(entry) -> bool:
    dest, src, _kind = entry
    if UNUSED.search(dest) or UNUSED.search(src or ""):
        return False
    if IS_LINUX and src and src.startswith(SYSTEM_PREFIXES):
        return False
    return True


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PharmaPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,  # windowed app: no terminal window
    icon="app/resources/icons/pharmapro.ico" if IS_WIN else None,
    version="packaging/version_info.txt" if IS_WIN else None,
)
