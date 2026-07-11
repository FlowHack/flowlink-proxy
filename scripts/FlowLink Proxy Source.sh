#!/usr/bin/env bash
#
# FlowLink Proxy Source — лаунчер для разработки и повседневного использования.
#
# Запускает бэкенд FlowLink Proxy из исходного кода Python.
# Создаёт виртуальное окружение, устанавливает зависимости, запускает backend и браузер.
#
# Использование:
#   ./scripts/"FlowLink Proxy Source.sh"                    # Запуск со стандартными портами
#   ./scripts/"FlowLink Proxy Source.sh" --proxy-port 9090  # Кастомный порт прокси
#   ./scripts/"FlowLink Proxy Source.sh" --api-port 9091    # Кастомный порт API
#   ./scripts/"FlowLink Proxy Source.sh" --debug            # Режим отладки
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
PROXY_PORT="${PROXY_PORT:-8080}"

# ═══ КОНЕЦ НАСТРОЙКИ ═════════════════════════════════════════════

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

# --- PID-трекинг и очистка при завершении ---
BACKEND_PID=""
BROWSER_PID=""

cleanup() {
    info "Остановка процессов..."
    if [ -n "$BROWSER_PID" ] && kill -0 "$BROWSER_PID" 2>/dev/null; then
        kill "$BROWSER_PID" 2>/dev/null || true
        info "Браузер (PID $BROWSER_PID) остановлен."
    fi
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        info "Бэкенд (PID $BACKEND_PID) остановлен."
    fi
    # Деактивация venv не требуется — она привязана к сессии shell
}
trap cleanup EXIT INT TERM

# --- Чтение настройки autostart_browser из .flowlink-settings ---
# Директория данных: $FLOWLINK_DATA_DIR или $HOME/.flowlink-proxy
DATA_DIR="${FLOWLINK_DATA_DIR:-$HOME/.flowlink-proxy}"
SETTINGS_FILE="$DATA_DIR/.flowlink-settings"
AUTOSTART_BROWSER="true"

if [ -f "$SETTINGS_FILE" ]; then
    AUTOSTART_BROWSER=$(grep "^autostart_browser=" "$SETTINGS_FILE" 2>/dev/null | cut -d'=' -f2 | tr '[:upper:]' '[:lower:]' || echo "true")
    case "$AUTOSTART_BROWSER" in
        true|1|yes|on)  AUTOSTART_BROWSER="true" ;;
        false|0|no|off) AUTOSTART_BROWSER="false" ;;
        *)              AUTOSTART_BROWSER="true" ;;
    esac
fi

# --- Проверка Python ---
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

# --- Создание виртуального окружения ---
if [ ! -d "venv" ]; then
    info "Создание виртуального окружения..."
    $PYTHON -m venv venv
    info "Виртуальное окружение создано"
fi

source venv/bin/activate

# --- Установка зависимостей ---
if [ -f "server/requirements.txt" ]; then
    info "Установка зависимостей..."
    pip install -q -r server/requirements.txt
    info "Зависимости установлены"
fi

# --- Запуск бэкенда в фоне ---
info "Запуск FlowLink Proxy из исходного кода..."
$PYTHON -m server --proxy-port "$PROXY_PORT" "$@" &
BACKEND_PID=$!

# Ожидание готовности бэкенда (опрос через kill -0 + curl)
READY=false
for i in $(seq 1 15); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        error "Бэкенд не запустился. Проверьте логи."
        exit 1
    fi
    if command -v curl &>/dev/null; then
        if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PROXY_PORT/" 2>/dev/null; then
            READY=true
            break
        fi
    else
        # curl недоступен — ждём фиксированное время
        sleep 2
        READY=true
        break
    fi
    sleep 1
done

if [ "$READY" != "true" ]; then
    error "Бэкенд не ответил за 15 секунд. Проверьте логи."
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
fi
info "Бэкенд запущен (PID $BACKEND_PID)."

# --- Запуск браузера (только если autostart_browser=true) ---
if [ "$AUTOSTART_BROWSER" = "false" ]; then
    info "Автозапуск браузера отключён (настройка autostart_browser=false)."
    info "Для включения: расширение → Настройки → Автозапуск браузера."
    echo ""
    info "Бэкенд продолжает работать. Нажмите Ctrl+C для остановки."
    wait "$BACKEND_PID"
    exit 0
fi

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
    echo ""
    echo "  Бэкенд продолжает работать. Нажмите Ctrl+C для остановки."
    wait "$BACKEND_PID"
    exit 0
fi

if [ ! -f "$BROWSER_PATH" ] && [ ! -d "$BROWSER_PATH" ]; then
    warn "Браузер не найден: $BROWSER_PATH"
    echo "  Бэкенд продолжает работать. Нажмите Ctrl+C для остановки."
    wait "$BACKEND_PID"
    exit 0
fi

info "Запускаю браузер с --proxy-server=127.0.0.1:$PROXY_PORT..."
"$BROWSER_PATH" --proxy-server="127.0.0.1:$PROXY_PORT" &
BROWSER_PID=$!

echo ""
info "Всё готово к работе!"
echo "  Бэкенд: PID $BACKEND_PID"
echo "  Браузер: PID $BROWSER_PID"
echo ""
echo "  Нажмите Ctrl+C для остановки."

# Ожидание завершения
wait "$BACKEND_PID" 2>/dev/null || true
