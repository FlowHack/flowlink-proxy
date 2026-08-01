#!/usr/bin/env bash
#
# Сборка FlowLink Proxy в standalone-бинарник через PyInstaller.
# Создаёт временное venv, устанавливает зависимости, собирает, чистит.
#
# На выходе: releases/flowlink-proxy (или releases/"FlowLink Proxy")
#
# Использование:
#   ./scripts/build/build.sh
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

# --- Путь к бинарникам venv (bin для Unix, Scripts для Windows) ---
if [ "$OS_DIR" = "windows" ]; then
    VENV_BIN="$VENV_DIR/Scripts"
else
    VENV_BIN="$VENV_DIR/bin"
fi

# --- Проверка Python ---
if ! command -v python3 &>/dev/null; then
    error "Python 3 не найден."
fi
PYTHON="python3"
PY_VERSION=$($PYTHON --version 2>&1)
info "$PY_VERSION найден"

# --- Проверка версии Python (нужна 3.10+) ---
if ! $PYTHON -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    error "Требуется Python 3.10 или новее."
fi

# --- Проверка tkinter ---
if ! $PYTHON -c "import tkinter" 2>/dev/null; then
    warn "tkinter не установлен — кастомное трей-меню не будет работать."
    if command -v apt &>/dev/null; then
        sudo apt install -y python3-tk 2>/dev/null && info "tkinter установлен." || warn "Установите: sudo apt install python3-tk"
    elif command -v brew &>/dev/null; then
        brew install python-tk@3.12 2>/dev/null && info "tkinter установлен." || warn "Установите: brew install python-tk@3.12"
    fi
fi

# --- Проверка python3-venv (ensurepip) ---
if [ "$CLEAN_VENV" = true ]; then
    if ! $PYTHON -m venv --help >/dev/null 2>&1; then
        warn "python3-venv не установлен — создание venv может не сработать."
        if command -v apt &>/dev/null; then
            sudo apt install -y python3-venv 2>/dev/null && info "python3-venv установлен." || warn "Установите: sudo apt install python3-venv"
        fi
    fi
fi

# --- Создание/использование venv ---
if [ "$CLEAN_VENV" = true ]; then
    info "Создание временного venv..."
    $PYTHON -m venv "$VENV_DIR"
else
    info "Использование существующего venv..."
fi
source "$VENV_BIN/activate"

# --- Установка зависимостей ---
info "Установка зависимостей..."
pip install -q --upgrade pip
pip install -q -r server/requirements.txt
pip install -q pyinstaller

# --- Версия ---
VERSION=$(python3 -c "import sys; sys.path.insert(0,'server'); from server.version import __version__; print(__version__)")
info "Версия: $VERSION"

# --- Сборка ---
info "Очистка предыдущей сборки..."
rm -rf server/dist server/work

info "Сборка FlowLink Proxy v$VERSION для $OS_DIR..."

# Иконки из scripts/icons/
ICON_FLAG=""
if [ -f "scripts/icons/icon.icns" ] && [ "$OS_DIR" = "macos" ]; then
    ICON_FLAG="--icon=scripts/icons/icon.icns"
elif [ -f "scripts/icons/icon.ico" ]; then
    ICON_FLAG="--icon=scripts/icons/icon.ico"
elif [ -f "server/icons/icon.ico" ]; then
    ICON_FLAG="--icon=server/icons/icon.ico"
fi

NOCONSOLE_FLAG=""
[ "$OS_DIR" = "windows" ] && NOCONSOLE_FLAG="--noconsole"

DATA_SEP=":"
[ "$OS_DIR" = "windows" ] && DATA_SEP=";"

$PYTHON -m PyInstaller \
    --onefile \
    $NOCONSOLE_FLAG \
    --name "$BINARY_NAME" \
    $ICON_FLAG \
    --add-data "server/requirements.txt${DATA_SEP}server/" \
    --add-data "server/icons${DATA_SEP}icons/" \
    --add-data "extension${DATA_SEP}extension/" \
    --hidden-import tkinter \
    --hidden-import _tkinter \
    --hidden-import pystray \
    --hidden-import PIL \
    --collect-all tkinter \
    --paths=server \
    --distpath server/dist \
    --workpath server/work \
    --clean \
    --noconfirm \
    server/__main__.py

info "Сборка завершена!"

# --- Проверка, что бинарник действительно собран ---
if [ ! -f "server/dist/$BINARY_NAME" ]; then
    error "Бинарник не найден: server/dist/$BINARY_NAME. Сборка PyInstaller завершилась неудачно."
fi

# --- Копирование в releases/ ---
mkdir -p releases
rm -f "releases/$BINARY_NAME"
mv "server/dist/$BINARY_NAME" "releases/"
rm -rf server/dist

BINARY="releases/$BINARY_NAME"
echo ""
echo "========================================"
echo "  Бинарник: $BINARY"
BIN_SIZE=$(du -h "$BINARY" 2>/dev/null | cut -f1 || echo "?")
echo "  Размер:   $BIN_SIZE"
echo ""
echo "  Запуск:"
echo "    ./$BINARY"
echo ""
echo "  Архив релиза:"
echo "    ./scripts/build/create-release.sh"
echo "========================================"
