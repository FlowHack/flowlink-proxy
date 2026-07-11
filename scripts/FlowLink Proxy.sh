#!/usr/bin/env bash
#
# FlowLink Proxy — Linux/macOS-лаунчер
#
# Запускает бэкенд FlowLink Proxy и браузер с прокси.
# Разместите этот скрипт рядом с бинарником FlowLink Proxy.
#
# Использование:
#   chmod +x "FlowLink Proxy.sh"
#   ./FlowLink Proxy.sh
#

# ═══════════════════════════════════════════════════════════════════
# ═══ НАСТРОЙКА ПЕРЕМЕННЫХ ════════════════════════════════════════
# Откройте этот файл в текстовом редакторе и отредактируйте
# переменные ниже под вашу систему.
# ═══════════════════════════════════════════════════════════════════

# --- Путь к браузеру (ОБЯЗАТЕЛЬНО) ---
# Замените ПУТЬ_К_БРАУЗЕРУ на реальный путь к исполняемому файлу браузера.
# Примеры:
#   /usr/bin/google-chrome-stable
#   /usr/bin/chromium-browser
#   /usr/bin/yandex-browser
#   /usr/bin/firefox
#   /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
BROWSER_PATH="ПУТЬ_К_БРАУЗЕРУ"

# --- Порт прокси (по умолчанию 8080) ---
# Меняйте, только если порт 8080 занят другим процессом.
# При смене порта обновите также флаг --proxy-server в ярлыке браузера.
PROXY_PORT="${PROXY_PORT:-8080}"

# ═══ КОНЕЦ НАСТРОЙКИ ═════════════════════════════════════════════

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

# --- Чтение настройки autostart_browser из .flowlink-settings ---
# Директория данных: $FLOWLINK_DATA_DIR или $HOME/.flowlink-proxy
DATA_DIR="${FLOWLINK_DATA_DIR:-$HOME/.flowlink-proxy}"
SETTINGS_FILE="$DATA_DIR/.flowlink-settings"
AUTOSTART_BROWSER="true"

if [ -f "$SETTINGS_FILE" ]; then
    AUTOSTART_BROWSER=$(grep "^autostart_browser=" "$SETTINGS_FILE" 2>/dev/null | cut -d'=' -f2 | tr '[:upper:]' '[:lower:]' || echo "true")
    # Если значение не распознано — используем true по умолчанию
    case "$AUTOSTART_BROWSER" in
        true|1|yes|on)  AUTOSTART_BROWSER="true" ;;
        false|0|no|off) AUTOSTART_BROWSER="false" ;;
        *)              AUTOSTART_BROWSER="true" ;;
    esac
fi

# --- Определение пути к бэкенду ---
# Сначала проверяем рядом со скриптом (standalone), потом в server/FlowLink Proxy (dev)
BACKEND_EXE=""
if [ -f "./FlowLink Proxy" ]; then
    BACKEND_EXE="./FlowLink Proxy"
elif [ -f "./server/FlowLink Proxy/FlowLink Proxy" ]; then
    BACKEND_EXE="./server/FlowLink Proxy/FlowLink Proxy"
fi

if [ -z "$BACKEND_EXE" ]; then
    error "FlowLink Proxy не найден."
    echo "  Убедитесь, что скрипт лежит в одной папке с бинарником FlowLink Proxy"
    echo "  или в корне проекта (тогда бинарник будет в server/FlowLink Proxy/)."
    exit 1
fi

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

# --- Запуск бэкенда ---
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

# --- Запуск браузера (только если autostart_browser=true) ---
if [ "$AUTOSTART_BROWSER" = "false" ]; then
    info "Автозапуск браузера отключён (настройка autostart_browser=false)."
    info "Для включения: расширение → Настройки → Автозапуск браузера."
else
    # --- Проверка пути к браузеру ---
    if [ "$BROWSER_PATH" = "ПУТЬ_К_БРАУЗЕРУ" ]; then
        echo ""
        warn "Путь к браузеру не указан."
        echo "  Откройте этот скрипт в текстовом редакторе и замените"
        echo "  \"ПУТЬ_К_БРАУЗЕРУ\" на путь к вашему браузеру."
        echo ""
        echo "  Примеры:"
        echo "    BROWSER_PATH=\"/usr/bin/google-chrome-stable\""
        echo "    BROWSER_PATH=\"/usr/bin/chromium-browser\""
        echo "    BROWSER_PATH=\"/usr/bin/yandex-browser\""
        echo "    BROWSER_PATH=\"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\""
        echo ""
        exit 1
    fi

    if [ ! -f "$BROWSER_PATH" ] && [ ! -d "$BROWSER_PATH" ]; then
        error "Браузер не найден: $BROWSER_PATH"
        echo "  Проверьте путь в переменной BROWSER_PATH в начале этого файла."
        exit 1
    fi

    # --- Запуск браузера ---
    if [ -f "$BROWSER_PIDFILE" ] && kill -0 "$(cat "$BROWSER_PIDFILE")" 2>/dev/null; then
        info "Браузер уже запущен (PID $(cat "$BROWSER_PIDFILE"))."
    else
        info "Запускаю браузер с --proxy-server=127.0.0.1:$PROXY_PORT..."
        "$BROWSER_PATH" --proxy-server="127.0.0.1:$PROXY_PORT" &
        BROWSER_PID=$!
        echo "$BROWSER_PID" > "$BROWSER_PIDFILE"
    fi
fi

echo ""
info "Всё готово к работе!"
