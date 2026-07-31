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

# --- Проверка Python ---
if ! command -v python3 &>/dev/null; then
    error "Python 3 не найден."
fi
PYTHON="python3"
PY_VERSION=$($PYTHON --version 2>&1)
info "$PY_VERSION найден"

# --- Проверка tkinter ---
if ! $PYTHON -c "import tkinter" 2>/dev/null; then
    warn "tkinter не установлен — кастомное трей-меню не будет работать."
    if command -v apt &>/dev/null; then
        sudo apt install -y python3-tk 2>/dev/null && info "tkinter установлен." || warn "Установите: sudo apt install python3-tk"
    elif command -v brew &>/dev/null; then
        brew install python-tk 2>/dev/null && info "tkinter установлен." || warn "Установите: brew install python-tk"
    fi
fi

# --- Создание/использование venv ---
if [ "$CLEAN_VENV" = true ]; then
    info "Создание временного venv..."
    $PYTHON -m venv "$VENV_DIR"
else
    info "Использование существующего venv..."
fi
source "$VENV_DIR/bin/activate"

# --- Установка зависимостей ---
info "Установка зависимостей..."
pip install -q --upgrade pip
pip install -q -r server/requirements.txt
pip install -q pyinstaller

# --- Версия ---
VERSION=$(python3 -c "import sys; sys.path.insert(0,'server'); from server.version import __version__; print(__version__)")
info "Версия: $VERSION"

# ─── Сборка CRX расширения ───
CRX_DATA=""
if [ -f "$SCRIPT_DIR/crx-private-key.pem" ]; then
    info "Сборка CRX расширения..."
    if ! command -v npx &>/dev/null; then
        warn "npx не найден. Установите Node.js (npm) для сборки CRX."
        warn "  Windows: https://nodejs.org (скачайте LTS, установите)"
        warn "  Linux:   sudo apt install nodejs npm  (или аналог для вашего пакетного менеджера)"
        warn "  macOS:   brew install node"
    else
        bash "$SCRIPT_DIR/build-crx.sh"
    fi
    if [ -f "$PROJECT_DIR/releases/flowlink-proxy.crx" ]; then
        CRX_DATA="--add-data releases/flowlink-proxy.crx${DATA_SEP}."
        info "CRX собран: releases/flowlink-proxy.crx"
    else
        warn "Не удалось собрать CRX"
    fi
else
    warn "Приватный ключ CRX не найден ($SCRIPT_DIR/crx-private-key.pem)."
    warn "CRX не будет включён в сборку. Расширение можно будет установить только из исходников."
    warn "Сгенерируйте ключ: openssl genrsa -out $SCRIPT_DIR/crx-private-key.pem 2048"
fi

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
    $CRX_DATA \
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
