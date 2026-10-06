#!/usr/bin/env bash
# Package the single-file Linux build as a Debian/Ubuntu installer (.deb).
#
#   bash packaging/build_linux.sh          # first: produces dist/PharmaPro
#   bash packaging/build_deb.sh [BINARY]   # then:  produces dist/pharmapro_<version>_amd64.deb
#
# Install with:  sudo apt install ./pharmapro_1.0.0_amd64.deb
# The app is installed to /opt/pharmapro; because that folder is read-only, each user's
# data is stored in ~/.local/share/PharmaPro (database, backups, logs, receipts, exports).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(python3 -c "import re;print(re.search(r'APP_VERSION = \"(.+?)\"', open('app/config.py').read()).group(1))")
BINARY=${1:-dist/PharmaPro}
[ -f "$BINARY" ] || { echo "Binary not found: $BINARY (run packaging/build_linux.sh first)"; exit 1; }

PKG=build/deb/pharmapro_${VERSION}_amd64
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/pharmapro" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/256x256/apps" "$PKG/usr/share/icons/hicolor/scalable/apps" \
         "$PKG/usr/share/doc/pharmapro"

install -m 755 "$BINARY" "$PKG/opt/pharmapro/PharmaPro"
ln -s /opt/pharmapro/PharmaPro "$PKG/usr/bin/pharmapro"
install -m 644 app/resources/icons/pharmapro.png "$PKG/usr/share/icons/hicolor/256x256/apps/pharmapro.png"
install -m 644 app/resources/icons/pharmapro.svg "$PKG/usr/share/icons/hicolor/scalable/apps/pharmapro.svg"

cat > "$PKG/usr/share/applications/pharmapro.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PharmaPro
GenericName=Pharmacy Management
Comment=Offline pharmacy management – stock, sales, receipts and profit
Exec=/opt/pharmapro/PharmaPro
Icon=pharmapro
Terminal=false
Categories=Office;Finance;
Keywords=pharmacy;medicine;pos;inventory;stock;
StartupWMClass=PharmaPro
EOF

cat > "$PKG/usr/share/doc/pharmapro/copyright" <<EOF
PharmaPro ${VERSION}
Offline pharmacy management system.
EOF

SIZE_KB=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<EOF
Package: pharmapro
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE_KB}
Depends: libc6 (>= 2.34), libegl1, libfontconfig1, libdbus-1-3, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-xinerama0 | libxcb1
Maintainer: PharmaPro <tehsaad13453310@gmail.com>
Description: Offline pharmacy management system
 PharmaPro manages medicines, batches with expiry dates, stock receiving,
 point of sale with receipt printing, expenses, reports and profit analytics.
 It works completely offline; all data stays on this computer.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
EOF
cp "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
# Debian policy: directories 755, files 644, executables/scripts 755.
chmod -R u=rwX,go=rX "$PKG"
chmod 755 "$PKG/opt/pharmapro/PharmaPro" "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

mkdir -p dist
dpkg-deb --root-owner-group -Zxz --build "$PKG" "dist/pharmapro_${VERSION}_amd64.deb"
echo "Built dist/pharmapro_${VERSION}_amd64.deb"
