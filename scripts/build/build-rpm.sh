#!/usr/bin/env bash
#
# FlowLink Proxy — сборка .rpm пакета
#
# Требования: rpmbuild (rpm-build)
#
# Использование:
#   chmod +x build-rpm.sh
#   ./build-rpm.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Чтение версии
VERSION=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from server.version import __version__; print(__version__)" 2>/dev/null || echo "0.3.0")
PKG_NAME="flowlink-proxy"

echo "[+] Сборка $PKG_NAME v$VERSION (.rpm)"

# --- Подготовка структуры rpmbuild ---
RPMBUILD_DIR="$HOME/rpmbuild"
mkdir -p "$RPMBUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# --- Копирование spec-файла ---
cp "$SCRIPT_DIR/flowlink.spec" "$RPMBUILD_DIR/SPECS/flowlink.spec"

# --- Создание tarball ---
TARBALL_DIR="$RPMBUILD_DIR/SOURCES/$PKG_NAME-$VERSION"
rm -rf "$RPMBUILD_DIR/SOURCES/$PKG_NAME-"*
mkdir -p "$TARBALL_DIR"

# Копирование бинарника
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

install -m 755 "$BINARY" "$TARBALL_DIR/FlowLink Proxy"

# Копирование EULA и LICENSE
for doc in EULA.rtf LICENSE.txt; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        install -m 644 "$PROJECT_DIR/$doc" "$TARBALL_DIR/$doc"
    fi
done

# Копирование .desktop файла
if [ -f "$PROJECT_DIR/scripts/autostart/flowlink.desktop" ]; then
    install -m 644 "$PROJECT_DIR/scripts/autostart/flowlink.desktop" "$TARBALL_DIR/flowlink.desktop"
fi

# Упаковка tarball
cd "$RPMBUILD_DIR/SOURCES"
tar czf "$PKG_NAME-$VERSION.tar.gz" "$PKG_NAME-$VERSION"
rm -rf "$TARBALL_DIR"

# --- Сборка ---
rpmbuild -ba "$RPMBUILD_DIR/SPECS/flowlink.spec" --define "version $VERSION"

echo "[+] .rpm пакет создан в ~/rpmbuild/RPMS/"
