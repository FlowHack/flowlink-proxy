#!/usr/bin/env bash
#
# FlowLink Proxy — сборка .pkg для macOS
#
# Требования: pkgbuild + productbuild (входят в Xcode Command Line Tools)
#
# Использование:
#   chmod +x build-pkg.sh
#   ./build-pkg.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION=$(PROJECT_DIR="$PROJECT_DIR" python3 -c "import os, sys; sys.path.insert(0, os.environ['PROJECT_DIR']); from server.version import __version__; print(__version__)" 2>/dev/null) || { echo "[!] Не удалось определить версию из server/version.py"; exit 1; }
PKG_NAME="FlowLink-Proxy"
IDENTIFIER="com.flowlink.proxy"
INSTALL_DIR="/usr/local"

# Определение архитектуры (для уникального имени pkg на intel и arm)
ARCH_UNAME="$(uname -m)"
if [ "$ARCH_UNAME" = "arm64" ]; then
    ARCH="arm64"
else
    ARCH="x64"
fi

echo "[+] Сборка $PKG_NAME v$VERSION (.pkg)"

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

# --- Подготовка структуры ---
BUILD_DIR="$PROJECT_DIR/releases/pkg-build"
rm -rf "$BUILD_DIR"

# --- Очистка временной папки сборки даже при ошибке ---
trap 'rm -rf "$BUILD_DIR"' EXIT

ROOT_DIR="$BUILD_DIR/root"
mkdir -p "$ROOT_DIR$INSTALL_DIR/bin"
mkdir -p "$ROOT_DIR$INSTALL_DIR/FlowHack/$PKG_NAME"

install -m 755 "$BINARY" "$ROOT_DIR$INSTALL_DIR/bin/FlowLink Proxy"

for doc in EULA.rtf LICENSE.txt; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        install -m 644 "$PROJECT_DIR/$doc" "$ROOT_DIR$INSTALL_DIR/FlowHack/$PKG_NAME/$doc"
    fi
done

# --- Проверка наличия pkgbuild и productbuild ---
if ! command -v pkgbuild &>/dev/null || ! command -v productbuild &>/dev/null; then
    echo "[!] pkgbuild/productbuild не найдены. Установите Xcode Command Line Tools."
    exit 1
fi

# --- pkgbuild ---
pkgbuild --root "$ROOT_DIR" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --install-location "/" \
    "$BUILD_DIR/$PKG_NAME-component.pkg"

# --- productbuild ---
productbuild --package "$BUILD_DIR/$PKG_NAME-component.pkg" \
    "$PROJECT_DIR/releases/${PKG_NAME}-${VERSION}-macos-${ARCH}.pkg"

# --- Очистка ---
rm -rf "$BUILD_DIR"

echo "[+] .pkg создан: releases/${PKG_NAME}-${VERSION}-macos-${ARCH}.pkg"
