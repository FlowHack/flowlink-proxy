#!/usr/bin/env bash
#
# FlowLink Proxy — macOS-лаунчер (standalone)
#
# ТОЛЬКО запускает бинарник FlowLink Proxy.
# Браузер запускается самим бэкендом через .flowlink-settings.
#
# Использование:
#   chmod +x "FlowLink Proxy-macos.sh"
#   ./FlowLink Proxy-macos.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Поиск бинарника: рядом со скриптом или в PATH
BACKEND=""
if [ -f "$SCRIPT_DIR/flowlink-proxy" ]; then
    BACKEND="$SCRIPT_DIR/flowlink-proxy"
elif [ -f "$SCRIPT_DIR/FlowLink Proxy" ]; then
    BACKEND="$SCRIPT_DIR/FlowLink Proxy"
elif command -v flowlink-proxy &>/dev/null; then
    BACKEND="flowlink-proxy"
fi

if [ -z "$BACKEND" ]; then
    echo "[!] FlowLink Proxy не найден."
    echo "  Убедитесь, что бинарник лежит в одной папке со скриптом."
    exit 1
fi

exec "$BACKEND" "$@"
