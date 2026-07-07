#!/usr/bin/env bash
#
# FlowLink Proxy — лаунчер для разработки и повседневного использования.
# Создаёт виртуальное окружение, устанавливает зависимости и запускает gateway.
#
# Использование:
#   ./scripts/flowlink.sh                    # Запуск со стандартными портами
#   ./scripts/flowlink.sh --proxy-port 9090  # Кастомный порт прокси
#   ./scripts/flowlink.sh --api-port 9091    # Кастомный порт API
#   ./scripts/flowlink.sh --debug            # Режим отладки
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

if ! command -v python3 &>/dev/null; then
    error "Python 3 не найден. Установите Python 3.10+ и повторите попытку."
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv"
    echo "  macOS: brew install python3"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

PYTHON="python3"

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python $PY_VERSION найден"

if [ ! -d "venv" ]; then
    info "Создание виртуального окружения..."
    $PYTHON -m venv venv
    info "Виртуальное окружение создано"
fi

source venv/bin/activate

if [ -f "server/requirements.txt" ]; then
    info "Установка зависимостей..."
    pip install -q -r server/requirements.txt
    info "Зависимости установлены"
fi

info "Запуск FlowLink Proxy..."
echo ""

# Запускаем как пакет
$PYTHON -m server "$@"

echo ""
info "FlowLink Proxy остановлен."
