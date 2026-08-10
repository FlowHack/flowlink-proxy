#!/usr/bin/env bash
# Сборка CRX расширения FlowLink Proxy.
# Использование:
#   ./scripts/crx/build-crx.sh                    # использует crx-private-key.pem
#   ./scripts/crx/build-crx.sh --key ./mykey.pem  # кастомный ключ
#
# На выходе: releases/FlowLink-Proxy-vX.X.X.crx
# Версия берётся из extension/manifest.json (канонический источник версии расширения).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Разбор аргументов: --key <путь> или позиционный <путь>
KEY_FILE="$SCRIPT_DIR/crx-private-key.pem"
while [ $# -gt 0 ]; do
    case "$1" in
        --key)
            KEY_FILE="${2:-}"
            shift 2
            ;;
        *)
            KEY_FILE="$1"
            shift
            ;;
    esac
done

if [ ! -f "$KEY_FILE" ]; then
    echo "[!] Приватный ключ не найден: $KEY_FILE"
    echo "    Сгенерируйте: openssl genrsa -out $KEY_FILE 2048"
    exit 1
fi

# Проверка, что ключ не пустой (например, секрет не задан в CI)
if [ ! -s "$KEY_FILE" ]; then
    echo "[!] Приватный ключ пуст: $KEY_FILE"
    echo "    Убедитесь, что секрет CRX_PRIVATE_KEY задан в настройках репозитория."
    exit 1
fi

# Версия расширения из manifest.json
VERSION=$(python3 -c "
import json
with open('$PROJECT_DIR/extension/manifest.json') as f:
    print(json.load(f)['version'])
")
if [ -z "$VERSION" ]; then
    echo "[!] Не удалось определить версию из extension/manifest.json"
    exit 1
fi
CRX_NAME="FlowLink-Proxy-v${VERSION}.crx"

# Подготовка временной папки с расширением
TMP_DIR=$(mktemp -d)

# Очистка временных файлов даже при ошибке
cleanup() {
    rm -rf "$TMP_DIR" /tmp/extension.zip 2>/dev/null || true
    # Удаляем частично созданные артефакты при ошибке сборки (не при успехе)
    if [ "${BUILD_SUCCESS:-0}" != "1" ]; then
        if [ -n "${ZIP_NAME:-}" ] && [ -f "$PROJECT_DIR/releases/$ZIP_NAME" ]; then
            rm -f "$PROJECT_DIR/releases/$ZIP_NAME"
        fi
        if [ -n "${CRX_NAME:-}" ] && [ -f "$PROJECT_DIR/releases/$CRX_NAME" ]; then
            rm -f "$PROJECT_DIR/releases/$CRX_NAME"
        fi
    fi
}
trap cleanup EXIT

# Проверка наличия openssl и npx ДО создания артефактов
if ! command -v openssl &>/dev/null; then
    echo "[!] openssl не найден. Установите OpenSSL для сборки CRX."
    echo "    Windows: https://slproweb.com/products/Win32OpenSSL.html (скачайте Light версию)"
    echo "    Linux:   sudo apt install openssl  (или аналог для вашего пакетного менеджера)"
    echo "    macOS:   brew install openssl"
    exit 1
fi
if ! command -v npx &>/dev/null; then
    echo "[!] npx не найден. Установите Node.js (npm) для сборки CRX."
    echo "    Windows: https://nodejs.org (скачайте LTS, установите)"
    echo "    Linux:   sudo apt install nodejs npm  (или аналог для вашего пакетного менеджера)"
    echo "    macOS:   brew install node"
    exit 1
fi

# Копирование файлов расширения с исключением тестов, служебных и скрытых файлов
# (tests/, package.json, node_modules, скрытые файлы не должны попадать в CRX/ZIP)
cd "$PROJECT_DIR/extension"
tar cf - \
    --exclude='tests' \
    --exclude='package.json' \
    --exclude='node_modules' \
    --exclude='./.*' \
    . | tar xf - -C "$TMP_DIR"
cd "$PROJECT_DIR"

# Добавление key в manifest.json
python3 -c "
import json, subprocess, base64, sys
with open('$TMP_DIR/manifest.json') as f:
    m = json.load(f)
r = subprocess.run(['openssl', 'rsa', '-pubout', '-in', '$KEY_FILE', '-outform', 'DER'],
                  capture_output=True)
if r.returncode != 0 or not r.stdout:
    sys.stderr.write('Не удалось извлечь публичный ключ из ключа: ' + r.stderr.decode('utf-8', 'replace') + '\n')
    sys.exit(1)
pubkey_b64 = base64.b64encode(r.stdout).decode('ascii')
# Проверка соответствия ключа закоммиченному в manifest.json.
# Если ключ отличается — ID расширения изменится, установка поверх
# существующего расширения перестанет работать.
existing_key = m.get('key')
if existing_key and existing_key != pubkey_b64:
    sys.stderr.write('ВНИМАНИЕ: переданный ключ не соответствует закоммиченному в manifest.json.\n')
    sys.stderr.write('ID расширения изменится, установка поверх существующего расширения не сработает.\n')
    sys.stderr.write('Используйте ключ, соответствующий закоммиченному публичному ключу.\n')
    sys.exit(1)
m['key'] = pubkey_b64
with open('$TMP_DIR/manifest.json', 'w') as f:
    json.dump(m, f, indent=2)
"

# Создание ZIP
cd "$TMP_DIR"
python3 -c "
import zipfile, os
with zipfile.ZipFile('/tmp/extension.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('.'):
        for fn in files:
            fp = os.path.join(root, fn)
            zf.write(fp, os.path.relpath(fp, '.'))
"

# Сохранение ZIP-архива расширения (для ручной установки unpacked)
mkdir -p "$PROJECT_DIR/releases"
ZIP_NAME="FlowLink-Proxy-v${VERSION}.zip"
cp /tmp/extension.zip "$PROJECT_DIR/releases/$ZIP_NAME"
echo "[+] ZIP создан: $PROJECT_DIR/releases/$ZIP_NAME"

# Сборка CRX через crx3-utils
mkdir -p "$PROJECT_DIR/releases"
# --yes нужен, чтобы npx не задавал интерактивный вопрос при первом запуске (зависание в CI)
npx --yes -p crx3-utils crx3-new "$KEY_FILE" < /tmp/extension.zip > "$PROJECT_DIR/releases/$CRX_NAME"

echo "[+] CRX создан: $PROJECT_DIR/releases/$CRX_NAME"
echo "[+] ZIP создан: $PROJECT_DIR/releases/$ZIP_NAME"

# Помечаем успешное завершение (cleanup не удалит ZIP)
BUILD_SUCCESS=1
