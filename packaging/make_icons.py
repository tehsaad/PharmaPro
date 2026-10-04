"""Regenerate the application icon files (SVG, PNG, ICO) from the logo in app/ui/icons.py.

Usage:  python packaging/make_icons.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402  (installed with matplotlib)
from PySide6.QtGui import QGuiApplication  # noqa: E402


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - needed for QPixmap
    from app.ui.icons import _render, logo_svg

    out = ROOT / "app" / "resources" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pharmapro.svg").write_text(logo_svg(), encoding="utf-8")
    pm = _render(logo_svg(), 128)  # 256 px physical
    pm.setDevicePixelRatio(1.0)
    pm.save(str(out / "pharmapro.png"))
    img = Image.open(out / "pharmapro.png")
    img.save(out / "pharmapro.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"Icons written to {out}")


if __name__ == "__main__":
    main()
