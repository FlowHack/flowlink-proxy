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
VERSION=$(PROJECT_DIR="$PROJECT_DIR" python3 -c "import os, sys; sys.path.insert(0, os.environ['PROJECT_DIR']); from server.version import __version__; print(__version__)" 2>/dev/null || exit 1)
PKG_NAME="FlowLink-Proxy"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo "amd64")"
BUILD_DIR="$PROJECT_DIR/releases/deb-build"

# --- Очистка временной папки сборки даже при ошибке ---
trap 'rm -rf "$BUILD_DIR"' EXIT

echo "[+] Сборка $PKG_NAME v$VERSION (.deb)"

# --- Очистка ---
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/local/bin"
mkdir -p "$BUILD_DIR/usr/local/share/FlowHack/$PKG_NAME"
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
        install -m 644 "$PROJECT_DIR/$doc" "$BUILD_DIR/usr/local/share/FlowHack/$PKG_NAME/$doc"
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
Maintainer: FlowLink Proxy <flowlink.proxy@atomicmail.io>
Description: FlowLink Proxy - traffic routing gateway
 FlowLink Proxy is a Python proxy-gateway with Chrome extension
 for routing traffic through SOCKS5 proxies with mask-based matching.
License: AGPL-3.0
EOF

# --- Сборка ---
mkdir -p "$PROJECT_DIR/releases"
dpkg-deb --build "$BUILD_DIR" "$PROJECT_DIR/releases/${PKG_NAME}_${VERSION}_${ARCH}.deb"

# Очистка временной папки сборки
rm -rf "$BUILD_DIR"

echo "[+] .deb пакет создан: releases/${PKG_NAME}_${VERSION}_${ARCH}.deb"
