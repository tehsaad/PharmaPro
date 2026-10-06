#!/usr/bin/env bash
# Build PharmaPro for Linux. Run from anywhere:
#   bash packaging/build_linux.sh          -> dist/PharmaPro            (single file, recommended)
#   bash packaging/build_linux.sh onedir   -> dist/PharmaPro/PharmaPro  (folder, starts faster)
#
# For the widest compatibility build on the OLDEST Linux you want to support, or use
# a portable Python (e.g. `uv python install 3.12`), which is built against an old glibc.
set -euo pipefail
cd "$(dirname "$0")/.."

SPEC=PharmaPro-onefile.spec
[ "${1:-}" = "onedir" ] && SPEC=PharmaPro.spec

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

QT_QPA_PLATFORM=offscreen python -m pytest -q
pyinstaller --noconfirm --clean "$SPEC"

echo
if [ "$SPEC" = "PharmaPro.spec" ]; then
    echo "Build complete: dist/PharmaPro/PharmaPro"
else
    chmod +x dist/PharmaPro
    echo "Build complete: dist/PharmaPro  (single file)"
fi
