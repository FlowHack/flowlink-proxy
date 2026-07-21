$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSCommandPath))
Set-Location $ProjectRoot

function Info  { Write-Host "[+] $args" -ForegroundColor Green }
function Warn  { Write-Host "[!] $args" -ForegroundColor Yellow }
function Error { Write-Host "[X] $args" -ForegroundColor Red; exit 1 }

$py = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $py) {
    Error "Python не найден. Установите Python 3.10+ с python.org"
}
Info "Python найден"

# Проверка tkinter
$tkCheck = & python -c "import tkinter" 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "tkinter не установлен — трей-меню не будет работать."
    Warn "Переустановите Python с python.org с отметкой 'tcl/tk and IDLE'."
}

$devVenv = Join-Path $ProjectRoot "venv"
$buildVenv = Join-Path $ProjectRoot "build-tmp"

if (Test-Path $devVenv) {
    $venvPath = $devVenv
    $cleanVenv = $false
    Info "Использование существующего venv..."
} else {
    $venvPath = $buildVenv
    $cleanVenv = $true
    Info "Создание временного venv..."
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Error "Не удалось создать venv"
    }
}

$pip = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "pip.exe"
$python = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "python.exe"

Info "Обновление pip..."
& $python -m pip install --upgrade pip -q

Info "Установка зависимостей..."
& $pip install -q pysocks
if ($LASTEXITCODE -ne 0) {
    Warn "Не удалось установить pysocks — SOCKS-поддержка pip может не работать"
}
& $pip install -q -r "server/requirements.txt"
if ($LASTEXITCODE -ne 0) {
    if ($cleanVenv) { Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue }
    Error "Не удалось установить зависимости"
}

& $pip install -q pyinstaller
if ($LASTEXITCODE -ne 0) {
    if ($cleanVenv) { Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue }
    Error "Не удалось установить PyInstaller"
}

Info "Очистка предыдущей сборки..."
Remove-Item -Recurse -Force "server/dist", "server/work" -ErrorAction SilentlyContinue

$VERSION = & $python -c "import sys; sys.path.insert(0,'server'); from server.version import __version__; print(__version__)"
Info "Сборка FlowLink Proxy v$VERSION для Windows..."

# Иконки из scripts/icons/
$iconFlag = ""
if (Test-Path "scripts/icons/icon.ico") {
    $iconFlag = "--icon=scripts/icons/icon.ico"
} elseif (Test-Path "server/icons/icon.ico") {
    $iconFlag = "--icon=server/icons/icon.ico"
}

$binaryName = "FlowLink Proxy.exe"

& $python -m PyInstaller `
    --onefile `
    --noconsole `
    --name $binaryName `
    $iconFlag `
    --add-data "server/requirements.txt;server/" `
    --add-data "server/icons;icons/" `
    --hidden-import tkinter `
    --hidden-import _tkinter `
    --hidden-import pystray `
    --hidden-import PIL `
    --collect-all tkinter `
    --paths server `
    --distpath server/dist `
    --workpath server/work `
    --clean `
    --noconfirm `
    server/__main__.py

$buildExit = $LASTEXITCODE

Info "Очистка временных файлов..."
Remove-Item -Recurse -Force "server/work" -ErrorAction SilentlyContinue
Remove-Item "*.spec" -ErrorAction SilentlyContinue
if ($cleanVenv) {
    Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue
}

if ($buildExit -ne 0) {
    Error "Сборка не удалась"
}

# Копирование в releases/
New-Item -ItemType Directory -Force -Path "releases" | Out-Null
$destPath = Join-Path "releases" $binaryName
Move-Item "server/dist/$binaryName" $destPath -Force
Remove-Item -Recurse -Force "server/dist" -ErrorAction SilentlyContinue

$binary = Get-Item $destPath -ErrorAction SilentlyContinue
if (-not $binary) {
    Error "Бинарник не найден. Сборка могла завершиться с ошибкой."
}
$size = "{0:N0} KB" -f ($binary.Length / 1KB)

Info "Сборка завершена!"
Write-Host ""
Write-Host "Бинарник: $destPath ($size)"
Write-Host ""
Write-Host "Запуск:"
Write-Host "  .\$destPath"
