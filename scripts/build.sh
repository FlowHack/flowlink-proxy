#!/usr/bin/env bash
#
# Сборка FlowLink Proxy в standalone-бинарник через PyInstaller.
# Создаёт временное venv, устанавливает зависимости, собирает, чистит.
#
# На выходе: server/dist/FlowLink Proxy (.exe на Windows)
#
# Использование:
#   ./scripts/build.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[FAIL]${NC} $1"; }

# --- Разделяем venv (dev) и build-tmp (build) ---
if [ -d "venv" ]; then
    VENV_DIR="$PROJECT_DIR/venv"
    CLEAN_VENV=false
else
    VENV_DIR="$PROJECT_DIR/build-tmp"
    CLEAN_VENV=true
fi

cleanup() {
    rm -rf server/work *.spec 2>/dev/null || true
    if [ "$CLEAN_VENV" = true ]; then
        rm -rf "$VENV_DIR"
    fi
}
trap cleanup EXIT

# --- Определяем платформу ---
case "$(uname -s)" in
    Linux*)     OS_DIR="linux";   EXT="";;
    Darwin*)    OS_DIR="macos";   EXT="";;
    CYGWIN*|MINGW*|MSYS*) OS_DIR="windows"; EXT=".exe";;
    *)          OS_DIR="unknown"; EXT="";;
esac

BINARY_NAME="FlowLink Proxy${EXT}"

# --- Проверка Python ---
if ! command -v python3 &>/dev/null; then
    error "Python 3 не найден."
    exit 1
fi
PYTHON="python3"
PY_VERSION=$($PYTHON --version 2>&1)
info "$PY_VERSION найден"

# --- Создание/использование venv ---
if [ "$CLEAN_VENV" = true ]; then
    info "Создание временного виртуального окружения..."
    $PYTHON -m venv "$VENV_DIR"
else
    info "Использование существующего venv..."
fi
source "$VENV_DIR/bin/activate"

# --- Установка зависимостей ---
info "Обновление pip..."
pip install -q --upgrade pip
info "Установка зависимостей..."
pip install -q -r server/requirements.txt
pip install -q pyinstaller

# --- Версия из server/version.py ---
VERSION=$(python3 -c "import sys; sys.path.insert(0,'server'); from version import __version__; print(__version__)")
info "Версия: $VERSION"

# --- Сборка ---
info "Очистка предыдущей сборки..."
rm -rf server/dist server/work "server/FlowLink Proxy"

info "Сборка FlowLink Proxy v$VERSION для $OS_DIR..."

ICON_FLAG=""
[ -f "server/icons/icon.ico" ] && ICON_FLAG="--icon=server/icons/icon.ico"

# --noconsole только для Windows (скрыть терминал при двойном клике)
NOCONSOLE_FLAG=""
[ "$OS_DIR" = "windows" ] && NOCONSOLE_FLAG="--noconsole"

$PYTHON -m PyInstaller \
    --onefile \
    $NOCONSOLE_FLAG \
    --name "FlowLink Proxy" \
    $ICON_FLAG \
    --add-data "server/requirements.txt:server/" \
    --add-data "server/icons:icons/" \
    --paths=server \
    --distpath server/dist \
    --workpath server/work \
    --clean \
    --noconfirm \
    server/__main__.py

info "Сборка завершена!"

OUTPUT_DIR="server/FlowLink Proxy"
rm -rf "$OUTPUT_DIR"
mv server/dist "$OUTPUT_DIR"
BINARY="$OUTPUT_DIR/$BINARY_NAME"

echo ""
echo "========================================"
echo "Бинарник: $BINARY"
BIN_SIZE=$(du -h "$BINARY" 2>/dev/null | cut -f1 || echo "?")
echo "Размер:   $BIN_SIZE"
echo ""
echo "Запуск:"
echo "  \"./$BINARY\""
echo ""
echo "========================================"
