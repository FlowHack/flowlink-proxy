#!/usr/bin/env bash
#
# FlowLink Proxy — Linux source setup
#
# Проверяет Python3 + tkinter, создаёт venv, запускает сервер.
#
# Использование:
#   chmod +x setup-and-run-linux.sh
#   ./setup-and-run-linux.sh
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
error() { echo -e "${RED}[X]${NC} $1"; }

# --- Проверка Python3 ---
if ! command -v python3 &>/dev/null; then
    error "Python 3 не найден. Установите Python 3.10+."
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-tk"
    echo "  Fedora: sudo dnf install python3 python3-tkinter"
    exit 1
fi

info "Python3 найден: $(python3 --version)"

# --- Проверка tkinter ---
if ! python3 -c "import tkinter" 2>/dev/null; then
    warn "tkinter не установлен — кастомное трей-меню будет недоступно."
    echo "  Ubuntu/Debian: sudo apt install python3-tk"
    echo "  Fedora: sudo dnf install python3-tkinter"
    echo "  Бэкенд продолжит работу без трей-иконки."
fi

# --- Создание venv ---
if [ ! -d "venv" ]; then
    info "Создание виртуального окружения..."
    python3 -m venv venv
    info "Виртуальное окружение создано."
fi

# shellcheck disable=SC1091
source venv/bin/activate

# --- Установка зависимостей ---
if [ -f "server/requirements.txt" ]; then
    info "Установка зависимостей..."
    pip install -q -r server/requirements.txt
    info "Зависимости установлены."
fi

# --- Запуск сервера ---
info "Запуск FlowLink Proxy..."
exec python -m server "$@"
