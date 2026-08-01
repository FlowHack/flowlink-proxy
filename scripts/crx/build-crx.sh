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

KEY_FILE="${2:-$SCRIPT_DIR/crx-private-key.pem}"

if [ ! -f "$KEY_FILE" ]; then
    echo "[!] Приватный ключ не найден: $KEY_FILE"
    echo "    Сгенерируйте: openssl genrsa -out $KEY_FILE 2048"
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
cp -r "$PROJECT_DIR/extension"/* "$TMP_DIR/"

# Проверка наличия openssl
if ! command -v openssl &>/dev/null; then
    echo "[!] openssl не найден. Установите OpenSSL для сборки CRX."
    echo "    Windows: https://slproweb.com/products/Win32OpenSSL.html (скачайте Light версию)"
    echo "    Linux:   sudo apt install openssl  (или аналог для вашего пакетного менеджера)"
    echo "    macOS:   brew install openssl"
    exit 1
fi

# Добавление key в manifest.json
python3 -c "
import json, subprocess, base64
with open('$TMP_DIR/manifest.json') as f:
    m = json.load(f)
r = subprocess.run(['openssl', 'rsa', '-pubout', '-in', '$KEY_FILE', '-outform', 'DER'],
                  capture_output=True)
m['key'] = base64.b64encode(r.stdout).decode('ascii')
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

# Сборка CRX через crx3-utils
mkdir -p "$PROJECT_DIR/releases"
if ! command -v npx &>/dev/null; then
    echo "[!] npx не найден. Установите Node.js (npm) для сборки CRX."
    echo "    Windows: https://nodejs.org (скачайте LTS, установите)"
    echo "    Linux:   sudo apt install nodejs npm  (или аналог для вашего пакетного менеджера)"
    echo "    macOS:   brew install node"
    exit 1
fi
npx -p crx3-utils crx3-new "$KEY_FILE" < /tmp/extension.zip > "$PROJECT_DIR/releases/$CRX_NAME"

rm -rf "$TMP_DIR" /tmp/extension.zip
echo "[+] CRX создан: $PROJECT_DIR/releases/$CRX_NAME"
