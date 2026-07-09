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

# PID-файлы для отслеживания фоновых процессов
PID_DIR="/tmp/flowlink-proxy"
mkdir -p "$PID_DIR"
BACKEND_PIDFILE="$PID_DIR/backend.pid"
BROWSER_PIDFILE="$PID_DIR/browser.pid"

# Cleanup — убиваем фоновые процессы при выходе
cleanup() {
    local exit_code=$?
    if [ -f "$BACKEND_PIDFILE" ]; then
        local pid
        pid=$(cat "$BACKEND_PIDFILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            info "Остановка бэкенда (PID $pid)..."
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$BACKEND_PIDFILE"
    fi
    if [ -f "$BROWSER_PIDFILE" ]; then
        local pid
        pid=$(cat "$BROWSER_PIDFILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$BROWSER_PIDFILE"
    fi
    rm -rf "$PID_DIR"
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

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

if [ -f "$BACKEND_PIDFILE" ] && kill -0 "$(cat "$BACKEND_PIDFILE")" 2>/dev/null; then
    info "Бэкенд уже запущен (PID $(cat "$BACKEND_PIDFILE"))."
else
    info "Запускаю бэкенд FlowLink Proxy..."
    chmod +x "$BACKEND_EXE"
    "$BACKEND_EXE" --proxy-port "$PROXY_PORT" &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PIDFILE"
    # Ждём готовности бэкенда
    for i in $(seq 1 10); do
        if curl -s -o /dev/null -w '' http://127.0.0.1:"$PROXY_PORT"/ 2>/dev/null ||
           curl -s -o /dev/null -w '' http://127.0.0.1:"$PROXY_PORT" 2>/dev/null; then
            info "Бэкенд запущен (PID $BACKEND_PID)."
            break
        fi
        sleep 0.5
    done
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        error "Бэкенд не запустился. Проверьте логи."
        exit 1
    fi
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

if [ -f "$BROWSER_PIDFILE" ] && kill -0 "$(cat "$BROWSER_PIDFILE")" 2>/dev/null; then
    info "Браузер уже запущен (PID $(cat "$BROWSER_PIDFILE"))."
else
    info "Запускаю браузер с --proxy-server=127.0.0.1:$PROXY_PORT..."
    "$BROWSER_PATH" --proxy-server="127.0.0.1:$PROXY_PORT" &
    BROWSER_PID=$!
    echo "$BROWSER_PID" > "$BROWSER_PIDFILE"
fi

echo ""
info "Всё готово к работе!"
