$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $ProjectRoot

function Info  { Write-Host "[OK] $args" -ForegroundColor Green }
function Warn  { Write-Host "[!] $args" -ForegroundColor Yellow }
function Error { Write-Host "[FAIL] $args" -ForegroundColor Red; exit 1 }

$py = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $py) {
    Error "Python 3 не найден. Установите Python 3.10+ с python.org"
}
Info "Python найден"

$devVenv = Join-Path $ProjectRoot "venv"
$buildVenv = Join-Path $ProjectRoot "build-tmp"

if (Test-Path $devVenv) {
    $venvPath = $devVenv
    $cleanVenv = $false
    Info "Использование существующего виртуального окружения..."
} else {
    $venvPath = $buildVenv
    $cleanVenv = $true
    Info "Создание временного виртуального окружения..."
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Error "Не удалось создать виртуальное окружение"
    }
}

$pip = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "pip.exe"
$python = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "python.exe"

Info "Обновление pip..."
& $python -m pip install --upgrade pip -q

Info "Установка зависимостей..."
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

$iconFlag = ""
if (Test-Path "server/icons/icon.ico") {
    $iconFlag = "--icon=server/icons/icon.ico"
}

& $python -m PyInstaller `
    --onefile `
    --noconsole `
    --name "FlowLink Proxy" `
    $iconFlag `
    --add-data "server/requirements.txt;server/" `
    --add-data "server/icons;icons/" `
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
if ($buildExit -eq 0) {
    Remove-Item -Recurse -Force "server/FlowLink Proxy" -ErrorAction SilentlyContinue
    Move-Item "server/dist" "server/FlowLink Proxy"
}

if ($buildExit -ne 0) {
    Error "Сборка не удалась"
}

$binary = Get-Item "server/FlowLink Proxy/FlowLink Proxy.exe"
$size = "{0:N0} КБ" -f ($binary.Length / 1KB)

Info "Сборка завершена!"
Write-Host ""
Write-Host "Бинарник: server/FlowLink Proxy/FlowLink Proxy.exe ($size)"
Write-Host ""
Write-Host "Запуск:"
Write-Host '  .\server\"FlowLink Proxy\FlowLink Proxy.exe"'
