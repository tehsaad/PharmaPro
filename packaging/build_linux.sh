#!/usr/bin/env bash
# Build PharmaPro for Linux. Run from anywhere:  bash packaging/build_linux.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

QT_QPA_PLATFORM=offscreen python -m pytest -q
pyinstaller --noconfirm --clean PharmaPro.spec

echo
echo "Build complete: dist/PharmaPro/PharmaPro"
