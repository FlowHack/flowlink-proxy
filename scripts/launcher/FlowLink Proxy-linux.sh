#!/usr/bin/env bash
#
# FlowLink Proxy — Linux-лаунчер (standalone)
#
# ТОЛЬКО запускает бинарник FlowLink Proxy.
# Браузер запускается самим бэкендом через .flowlink-settings.
#
# Использование:
#   chmod +x "FlowLink Proxy-linux.sh"
#   ./FlowLink Proxy-linux.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Поиск бинарника: рядом со скриптом или в PATH
BACKEND=""
if [ -f "$SCRIPT_DIR/FlowLink Proxy" ]; then
    BACKEND="$SCRIPT_DIR/FlowLink Proxy"
elif [ -f "$SCRIPT_DIR/flowlink-proxy" ]; then
    BACKEND="$SCRIPT_DIR/flowlink-proxy"
elif command -v "FlowLink Proxy" &>/dev/null; then
    BACKEND="FlowLink Proxy"
fi

if [ -z "$BACKEND" ]; then
    echo "[!] FlowLink Proxy не найден."
    echo "  Убедитесь, что бинарник лежит в одной папке со скриптом."
    exit 1
fi

exec "$BACKEND" "$@"
