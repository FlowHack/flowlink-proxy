#!/usr/bin/env bash
#
# FlowLink Proxy — лаунчер (для standalone-сборки / исходников)
#
# Бэкенд запускается по относительному пути рядом с этим скриптом.
# Браузер — укажите путь ниже в переменной BROWSER_PATH.
#
# Использование:
#   ./scripts/flowlink-proxy-run.sh
#   PROXY_PORT=9090 ./scripts/flowlink-proxy-run.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# ═══ УКАЖИТЕ ПУТЬ К БРАУЗЕРУ ═══
# Примеры:
#   BROWSER_PATH="/usr/bin/google-chrome-stable"
#   BROWSER_PATH="/usr/bin/chromium-browser"
#   BROWSER_PATH="/usr/bin/firefox"
#   BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BROWSER_PATH="ПУТЬ_К_БРАУЗЕРУ"
# ════════════════════════════════

PROXY_PORT="${PROXY_PORT:-8080}"
BACKEND_EXE="./server/FlowLink Proxy/FlowLink Proxy"

# --- Запуск бэкенда ---
if [ ! -f "$BACKEND_EXE" ]; then
    error "FlowLink Proxy не найден рядом с этим скриптом."
    echo "  Убедитесь, что скрипт лежит в одной папке с бинарником."
    exit 1
fi

if pgrep -f "^$BACKEND_EXE" >/dev/null 2>&1; then
    info "Бэкенд уже запущен."
else
    info "Запускаю бэкенд FlowLink Proxy..."
    chmod +x "$BACKEND_EXE"
    "$BACKEND_EXE" --proxy-port "$PROXY_PORT" &
    sleep 1
fi

# --- Запуск браузера ---
if [ "$BROWSER_PATH" = "ПУТЬ_К_БРАУЗЕРУ" ]; then
    echo ""
    warn "Путь к браузеру не указан."
    echo "  Откройте этот скрипт в текстовом редакторе и замените"
    echo "  \"ПУТЬ_К_БРАУЗЕРУ\" на путь к вашему браузеру."
    echo ""
    exit 1
fi

if [ ! -f "$BROWSER_PATH" ] && [ ! -d "$BROWSER_PATH" ]; then
    error "Браузер не найден: $BROWSER_PATH"
    echo "  Проверьте путь в переменной BROWSER_PATH."
    exit 1
fi

if pgrep -f "^$BROWSER_PATH" >/dev/null 2>&1; then
    info "Браузер уже запущен."
else
    info "Запускаю браузер с --proxy-server=127.0.0.1:$PROXY_PORT..."
    "$BROWSER_PATH" --proxy-server="127.0.0.1:$PROXY_PORT" &
fi

echo ""
info "Всё готово к работе!"
