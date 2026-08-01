# Сборка CRX расширения FlowLink Proxy (Windows).
# Использование:
#   .\scripts\crx\build-crx.ps1                    # использует crx-private-key.pem
#   .\scripts\crx\build-crx.ps1 -Key .\mykey.pem   # кастомный ключ
#
# На выходе: releases\FlowLink-Proxy-vX.X.X.crx
# Версия берётся из extension\manifest.json (канонический источник версии расширения).
#
# Требования:
#   - Node.js (npm) с npx — для crx3-utils
#   - OpenSSL — для извлечения публичного ключа из приватного
#     (можно установить через Chocolatey: choco install openssl)

param(
    [string]$Key = ""
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

# Ключ по умолчанию — рядом со скриптом
if (-not $Key) {
    $Key = Join-Path $ScriptDir 'crx-private-key.pem'
}

if (-not (Test-Path $Key)) {
    Write-Host "[!] Приватный ключ не найден: $Key" -ForegroundColor Red
    Write-Host "    Сгенерируйте: openssl genrsa -out $Key 2048"
    exit 1
}

# Версия расширения из manifest.json
$ManifestSrc = Join-Path $ProjectDir 'extension\manifest.json'
if (-not (Test-Path $ManifestSrc)) {
    Write-Host "[!] Не найден extension\manifest.json" -ForegroundColor Red
    exit 1
}
$ManifestMeta = Get-Content $ManifestSrc -Raw | ConvertFrom-Json
$Version = $ManifestMeta.version
if (-not $Version) {
    Write-Host "[!] Не удалось определить версию из extension\manifest.json" -ForegroundColor Red
    exit 1
}
$CrxName = "FlowLink-Proxy-v$Version.crx"

# Проверка наличия openssl
if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    Write-Host "[!] openssl не найден. Установите OpenSSL для сборки CRX." -ForegroundColor Red
    Write-Host "    Chocolatey: choco install openssl"
    Write-Host "    Или скачайте: https://slproweb.com/products/Win32OpenSSL.html (Light версия)"
    exit 1
}

# Проверка наличия npx
if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Host "[!] npx не найден. Установите Node.js (npm) для сборки CRX." -ForegroundColor Red
    Write-Host "    Chocolatey: choco install nodejs"
    Write-Host "    Или скачайте: https://nodejs.org (LTS)"
    exit 1
}

# Подготовка временной папки с расширением
$TmpDir = Join-Path $env:TEMP ("flowlink-crx-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
Copy-Item -Path (Join-Path $ProjectDir 'extension\*') -Destination $TmpDir -Recurse -Force

try {
    # Добавление публичного ключа в manifest.json
    $ManifestPath = Join-Path $TmpDir 'manifest.json'
    $Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

    # Извлекаем публичный ключ (DER) из приватного через openssl.
    # Записываем DER в файл, чтобы надёжно прочитать его как байты
    # (в PowerShell захват stdout у openssl возвращает строки, а не байты).
    $PubKeyDerPath = Join-Path $TmpDir 'pubkey.der'
    & openssl rsa -pubout -in $Key -outform DER -out $PubKeyDerPath 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось извлечь публичный ключ из $Key"
    }
    $PubKeyB64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($PubKeyDerPath))

    $Manifest | Add-Member -NotePropertyName 'key' -NotePropertyValue $PubKeyB64 -Force
    # Записываем JSON без BOM (Chrome не принимает BOM в manifest.json).
    # ConvertTo-Json экранирует кириллицу в \uXXXX — это валидный JSON.
    $Json = $Manifest | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($ManifestPath, $Json, (New-Object System.Text.UTF8Encoding($false)))

    # Создание ZIP
    $ZipPath = Join-Path $env:TEMP 'flowlink-extension.zip'
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Compress-Archive -Path (Join-Path $TmpDir '*') -DestinationPath $ZipPath -CompressionLevel Optimal

    # Сборка CRX через crx3-utils.
    # crx3-new читает ZIP из stdin и пишет CRX в stdout.
    # Используем cmd /c с перенаправлением файлов — это надёжно для
    # бинарных данных (в PowerShell pipe искажает байты).
    $ReleasesDir = Join-Path $ProjectDir 'releases'
    New-Item -ItemType Directory -Path $ReleasesDir -Force | Out-Null
    $OutCrx = Join-Path $ReleasesDir $CrxName

    $CmdLine = "npx -p crx3-utils crx3-new `"$Key`" < `"$ZipPath`" > `"$OutCrx`""
    cmd /c $CmdLine
    if ($LASTEXITCODE -ne 0) {
        throw "Ошибка сборки CRX через crx3-utils"
    }

    Write-Host "[+] CRX создан: $OutCrx" -ForegroundColor Green
}
finally {
    # Очистка временных файлов
    if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
    $ZipPath = Join-Path $env:TEMP 'flowlink-extension.zip'
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
}
