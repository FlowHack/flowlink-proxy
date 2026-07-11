#!/usr/bin/env bash
#
# Создание архивов релиза FlowLink Proxy для Linux и macOS.
# Запускать ПОСЛЕ сборки бинарника (build.sh).
#
# Использование:
#   ./scripts/create-release.sh             # Создать архивы
#   ./scripts/create-release.sh --version   # Только показать версию
#
# На выходе:
#   releases/FlowLink-Proxy-vX.X.X-linux-x64.tar.gz
#   releases/FlowLink-Proxy-vX.X.X-linux-x64.zip
#   (на macOS: releases/FlowLink-Proxy-vX.X.X-macos-x64.tar.gz + .zip)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# --- Определение версии ---
if [ ! -f "server/version.py" ]; then
    error "Файл server/version.py не найден. Запустите из корня проекта."
    exit 1
fi

VERSION=$(python3 -c "import sys; sys.path.insert(0,'server'); from server.version import __version__; print(__version__)")

if [ "${1:-}" = "--version" ]; then
    echo "$VERSION"
    exit 0
fi

# --- Определение платформы ---
case "$(uname -s)" in
    Linux*)  OS_NAME="linux";   ARCH="x64";;
    Darwin*) OS_NAME="macos";   ARCH="x64";;
    CYGWIN*|MINGW*|MSYS*) warn "Запуск Windows-сборки. Для Windows используйте build.ps1"; OS_NAME="windows"; ARCH="x64";;
    *)       error "Неизвестная ОС: $(uname -s)"; exit 1;;
esac

RELEASE_NAME="FlowLink-Proxy-v${VERSION}-${OS_NAME}-${ARCH}"
OUTPUT_DIR="$PROJECT_DIR/releases"

BINARY="$PROJECT_DIR/server/FlowLink Proxy/FlowLink Proxy"
if [ "$OS_NAME" = "windows" ]; then
    BINARY="${BINARY}.exe"
fi

# --- Проверка бинарника ---
if [ ! -f "$BINARY" ]; then
    error "Бинарник не найден: $BINARY"
    echo "  Сначала соберите: ./scripts/build.sh"
    exit 1
fi
info "Бинарник найден: $BINARY"

# --- Создание временной папки для сборки архива ---
TEMP_DIR=$(mktemp -d)
RELEASE_DIR="$TEMP_DIR/$RELEASE_NAME"
mkdir -p "$RELEASE_DIR"

info "Сборка релиза $RELEASE_NAME..."

# --- Копирование файлов ---
cp "$BINARY" "$RELEASE_DIR/"
cp "$PROJECT_DIR/LICENSE.txt" "$RELEASE_DIR/"

# Лаунчер
if [ "$OS_NAME" = "windows" ]; then
    cp "$PROJECT_DIR/scripts/FlowLink Proxy.bat" "$RELEASE_DIR/"
else
    cp "$PROJECT_DIR/scripts/FlowLink Proxy.sh" "$RELEASE_DIR/"
    chmod +x "$RELEASE_DIR/FlowLink Proxy.sh"
fi

# Документация
cp "$PROJECT_DIR/README.md" "$RELEASE_DIR/"
cp "$PROJECT_DIR/SETUP.md" "$RELEASE_DIR/"
cp "$PROJECT_DIR/DEBUG.md" "$RELEASE_DIR/"

# --- Создание архива ---
mkdir -p "$OUTPUT_DIR"

# tar.gz
TARBALL="$OUTPUT_DIR/$RELEASE_NAME.tar.gz"
info "Создание $TARBALL..."
tar -czf "$TARBALL" -C "$TEMP_DIR" "$RELEASE_NAME/"

# zip
ZIPFILE="$OUTPUT_DIR/$RELEASE_NAME.zip"
info "Создание $ZIPFILE..."
(cd "$TEMP_DIR" && zip -r "$ZIPFILE" "$RELEASE_NAME/") >/dev/null 2>&1

# --- Очистка ---
rm -rf "$TEMP_DIR"

# --- Вывод результатов ---
echo ""
echo "========================================"
echo "  Готово! Релиз $VERSION для $OS_NAME ($ARCH)"
echo ""
echo "  $TARBALL"
echo "    $(du -h "$TARBALL" | cut -f1)"
echo ""
echo "  $ZIPFILE"
echo "    $(du -h "$ZIPFILE" | cut -f1)"
echo ""
echo "  Содержимое архива:"
echo "    $RELEASE_NAME/"
echo "    ├── FlowLink Proxy          # Бинарник"
echo "    ├── FlowLink Proxy.sh       # Лаунчер"
echo "    ├── README.md               # Краткая инструкция"
echo "    ├── SETUP.md                # Подробная установка"
echo "    ├── DEBUG.md                # Отладка и API"
echo "    └── LICENSE.txt             # GNU AGPL v3"
echo "========================================"

info "Готово!"

if [ "$OS_NAME" != "macos" ]; then
    echo ""
    warn "Этот скрипт запущен на $OS_NAME."
    echo "  Для сборки под macOS запустите build.sh, а затем create-release.sh на macOS."
    echo "  Либо настройте GitHub Actions для автоматической сборки."
fi
