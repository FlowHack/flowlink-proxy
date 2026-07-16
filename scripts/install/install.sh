#!/usr/bin/env bash
#
# FlowLink Proxy — универсальный standalone-установщик
#
# Определяет платформу и архитектуру, устанавливает бинарник
# и сопутствующие файлы в /usr/local/.
#
# Использование:
#   chmod +x install.sh
#   ./install.sh
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[X]${NC} $1"; exit 1; }

INSTALL_DIR="/usr/local/bin"
SHARE_DIR="/usr/local/share/FlowLink Proxy"

# --- Определение платформы ---
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="darwin" ;;
    *)      error "Неподдерживаемая платформа: $OS" ;;
esac

case "$ARCH" in
    x86_64|amd64)  ARCH_NAME="x64" ;;
    aarch64|arm64) ARCH_NAME="arm64" ;;
    *)             error "Неподдерживаемая архитектура: $ARCH" ;;
esac

info "Платформа: $PLATFORM ($ARCH_NAME)"

# --- Определение имени бинарника ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY=""

# Ищем бинарник рядом с install.sh
for name in "FlowLink Proxy" "flowlink-proxy" "flowlink-proxy-$PLATFORM-$ARCH_NAME"; do
    if [ -f "$SCRIPT_DIR/$name" ]; then
        BINARY="$SCRIPT_DIR/$name"
        break
    fi
done

if [ -z "$BINARY" ]; then
    error "Бинарник не найден рядом с install.sh."
fi

# --- Проверка прав ---
if [ "$(id -u)" -ne 0 ]; then
    warn "Требуются права root. Используем sudo..."
    SUDO="sudo"
else
    SUDO=""
fi

# --- Установка ---
info "Установка FlowLink Proxy..."
$SUDO mkdir -p "$INSTALL_DIR" "$SHARE_DIR"
$SUDO install -m 755 "$BINARY" "$INSTALL_DIR/FlowLink Proxy"

# Копирование документации
for doc in EULA.rtf LICENSE.txt; do
    if [ -f "$SCRIPT_DIR/$doc" ]; then
        $SUDO install -m 644 "$SCRIPT_DIR/$doc" "$SHARE_DIR/$doc"
        info "Установлен $doc"
    fi
done

# Копирование лаунчера
LAUNCHER=""
if [ "$PLATFORM" = "linux" ] && [ -f "$SCRIPT_DIR/FlowLink Proxy-linux.sh" ]; then
    LAUNCHER="$SCRIPT_DIR/FlowLink Proxy-linux.sh"
elif [ "$PLATFORM" = "darwin" ] && [ -f "$SCRIPT_DIR/FlowLink Proxy-macos.sh" ]; then
    LAUNCHER="$SCRIPT_DIR/FlowLink Proxy-macos.sh"
fi

if [ -n "$LAUNCHER" ]; then
    $SUDO install -m 755 "$LAUNCHER" "$INSTALL_DIR/flowlink-launcher"
    info "Установлен лаунчер"
fi

# Копирование шаблонов автозапуска
AUTOSTART_DIR="$SHARE_DIR/autostart"
$SUDO mkdir -p "$AUTOSTART_DIR"
for f in com.flowlink.proxy.plist flowlink.desktop flowlink.service; do
    if [ -f "$SCRIPT_DIR/autostart/$f" ]; then
        $SUDO install -m 644 "$SCRIPT_DIR/autostart/$f" "$AUTOSTART_DIR/$f"
    fi
done

info "FlowLink Proxy установлен в $INSTALL_DIR/FlowLink Proxy"
info "Для запуска: FlowLink Proxy"
info "Для автозапуска с системой: включите через расширение или tray-меню."
