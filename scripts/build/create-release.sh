#!/usr/bin/env bash
#
# Создание архивов релиза FlowLink Proxy для Linux и macOS.
# Запускать ПОСЛЕ сборки бинарника (build.sh).
#
# Использование:
#   ./scripts/build/create-release.sh
#   ./scripts/build/create-release.sh --version
#
# На выходе:
#   releases/FlowLink-Proxy-vX.X.X-{platform}-{arch}.tar.gz
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[X]${NC} $1"; exit 1; }

# --- Определение версии ---
if [ ! -f "server/version.py" ]; then
    error "Файл server/version.py не найден."
fi

VERSION=$(python3 -c "import sys; sys.path.insert(0,'server'); from server.version import __version__; print(__version__)")

if [ "${1:-}" = "--version" ]; then
    echo "$VERSION"
    exit 0
fi

# --- Определение платформы ---
case "$(uname -s)" in
    Linux*)  OS_NAME="linux";  ARCH="x64";;
    Darwin*) ARCH_UNAME="$(uname -m)"
             OS_NAME="macos"
             if [ "$ARCH_UNAME" = "arm64" ]; then ARCH="arm64"; else ARCH="x64"; fi;;
    *)       error "Неизвестная ОС: $(uname -s)"; exit 1;;
esac

RELEASE_NAME="FlowLink-Proxy-v${VERSION}-${OS_NAME}-${ARCH}"
OUTPUT_DIR="$PROJECT_DIR/releases"

# --- Поиск бинарника ---
BINARY=""
if [ -f "releases/FlowLink Proxy" ]; then
    BINARY="releases/FlowLink Proxy"
elif [ -f "releases/flowlink-proxy" ]; then
    BINARY="releases/flowlink-proxy"
fi

if [ -z "$BINARY" ] || [ ! -f "$BINARY" ]; then
    error "Бинарник не найден в releases/. Сначала запустите build.sh"
fi
info "Бинарник найден: $BINARY"

# --- Создание временной папки ---
TEMP_DIR=$(mktemp -d)
RELEASE_DIR="$TEMP_DIR/$RELEASE_NAME"
mkdir -p "$RELEASE_DIR"

info "Сборка релиза $RELEASE_NAME..."

# --- Копирование файлов ---
cp "$BINARY" "$RELEASE_DIR/"

# Документация
for doc in EULA.rtf LICENSE.txt README.md; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        cp "$PROJECT_DIR/$doc" "$RELEASE_DIR/"
    fi
done

# Лаунчер
if [ "$OS_NAME" = "linux" ]; then
    if [ -f "$PROJECT_DIR/scripts/launcher/FlowLink Proxy-linux.sh" ]; then
        cp "$PROJECT_DIR/scripts/launcher/FlowLink Proxy-linux.sh" "$RELEASE_DIR/"
        chmod +x "$RELEASE_DIR/FlowLink Proxy-linux.sh"
    fi
elif [ "$OS_NAME" = "macos" ]; then
    if [ -f "$PROJECT_DIR/scripts/launcher/FlowLink Proxy-macos.sh" ]; then
        cp "$PROJECT_DIR/scripts/launcher/FlowLink Proxy-macos.sh" "$RELEASE_DIR/"
        chmod +x "$RELEASE_DIR/FlowLink Proxy-macos.sh"
    fi
fi

# --- Создание tar.gz ---
mkdir -p "$OUTPUT_DIR"
TARBALL="$OUTPUT_DIR/$RELEASE_NAME.tar.gz"
info "Создание $TARBALL..."
tar -czf "$TARBALL" -C "$TEMP_DIR" "$RELEASE_NAME/"

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
echo "  Содержимое архива:"
echo "    $RELEASE_NAME/"
echo "    ├── flowlink-proxy              # Бинарник"
echo "    ├── FlowLink Proxy-${OS_NAME}.sh # Лаунчер"
echo "    ├── EULA.rtf                     # Лицензия"
echo "    ├── LICENSE.txt                  # GNU AGPL v3"
echo "    └── README.md                    # Инструкция"
echo "========================================"
