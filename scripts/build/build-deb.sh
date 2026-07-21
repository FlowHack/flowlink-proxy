#!/usr/bin/env bash
#
# FlowLink Proxy — сборка .deb пакета
#
# Требования: dpkg-deb (Ubuntu/Debian)
#
# Использование:
#   chmod +x build-deb.sh
#   ./build-deb.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Чтение версии из server/version.py
VERSION=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from server.version import __version__; print(__version__)" 2>/dev/null || echo "0.3.0")
PKG_NAME="flowlink-proxy"
ARCH="amd64"
BUILD_DIR="$PROJECT_DIR/releases/deb-build"

echo "[+] Сборка $PKG_NAME v$VERSION (.deb)"

# --- Очистка ---
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/local/bin"
mkdir -p "$BUILD_DIR/usr/local/share/$PKG_NAME"
mkdir -p "$BUILD_DIR/usr/share/applications"

# --- Поиск бинарника ---
BINARY=""
for name in "FlowLink Proxy" "flowlink-proxy"; do
    if [ -f "$PROJECT_DIR/releases/$name" ]; then
        BINARY="$PROJECT_DIR/releases/$name"
        break
    fi
done

if [ -z "$BINARY" ]; then
    echo "[!] Бинарник не найден в releases/. Сначала запустите build.sh"
    exit 1
fi

install -m 755 "$BINARY" "$BUILD_DIR/usr/local/bin/FlowLink Proxy"

# --- Копирование EULA и LICENSE ---
for doc in EULA.rtf LICENSE.txt; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        install -m 644 "$PROJECT_DIR/$doc" "$BUILD_DIR/usr/local/share/$PKG_NAME/$doc"
    fi
done

# --- Копирование шаблона автозапуска ---
if [ -f "$PROJECT_DIR/scripts/autostart/flowlink.desktop" ]; then
    install -m 644 "$PROJECT_DIR/scripts/autostart/flowlink.desktop" \
        "$BUILD_DIR/usr/share/applications/flowlink-proxy.desktop"
fi

# --- DEBIAN/control ---
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $PKG_NAME
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10)
Maintainer: FlowLink Proxy <flowlink.proxy@atomicmail.io>
Description: FlowLink Proxy - traffic routing gateway
 FlowLink Proxy is a Python proxy-gateway with Chrome extension
 for routing traffic through SOCKS5 proxies with mask-based matching.
License: AGPL-3.0
EOF

# --- Сборка ---
mkdir -p "$PROJECT_DIR/releases"
dpkg-deb --build "$BUILD_DIR" "$PROJECT_DIR/releases/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "[+] .deb пакет создан: releases/${PKG_NAME}_${VERSION}_${ARCH}.deb"
