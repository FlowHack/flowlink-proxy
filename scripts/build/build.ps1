$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSCommandPath))
Set-Location $ProjectRoot

function Info  { Write-Host "[+] $args" -ForegroundColor Green }
function Warn  { Write-Host "[!] $args" -ForegroundColor Yellow }
function Error { Write-Host "[X] $args" -ForegroundColor Red; exit 1 }

$pythonCmd = "python"
$py = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $py) {
    # Пробуем py-лаунчер (Windows Store Python), если python нет в PATH
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        $pythonCmd = "py"
    }
}
if (-not $py) {
    Error "Python не найден. Установите Python 3.10+ с python.org"
}
Info "Python найден"

# Проверка версии Python (нужна 3.10+)
& $pythonCmd -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Error "Требуется Python 3.10 или новее."
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
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Error "Не удалось создать venv"
    }
}

$pip = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "pip.exe"
$python = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "python.exe"

# Проверка tkinter в venv (системный python мог отличаться от venv-питона)
$tkCheck = & $python -c "import tkinter" 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "tkinter не установлен — трей-меню не будет работать."
    Warn "Переустановите Python с python.org с отметкой 'tcl/tk and IDLE'."
}

Info "Обновление pip..."
& $python -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) {
    if ($cleanVenv) { Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue }
    Error "Не удалось обновить pip"
}

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
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($VERSION)) {
    if ($cleanVenv) { Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue }
    Error "Не удалось определить версию из server/version.py"
}
Info "Сборка FlowLink Proxy v$VERSION для Windows..."

# Иконки из scripts/icons/
$iconFlag = ""
if (Test-Path "scripts/icons/icon.ico") {
    $iconFlag = "--icon=scripts/icons/icon.ico"
} elseif (Test-Path "server/icons/icon.ico") {
    $iconFlag = "--icon=server/icons/icon.ico"
}

$binaryName = "FlowLink Proxy.exe"

# Генерация version resource для Windows (снижает ложные срабатывания Defender)
New-Item -ItemType Directory -Force -Path "server/work" | Out-Null
& $python "scripts/build/make_version_info.py" $VERSION "server/work/version_info.txt"
if ($LASTEXITCODE -ne 0) {
    Error "Не удалось сгенерировать version resource"
}
$versionFlag = "--version-file=server/work/version_info.txt"

& $python -m PyInstaller `
    --onedir `
    --noconsole `
    --name $binaryName `
    $iconFlag `
    --add-data "server/requirements.txt;server/" `
    --add-data "server/icons;icons/" `
    --add-data "server/locales;server/locales/" `
    --add-data "extension;extension/" `
    --hidden-import tkinter `
    --hidden-import _tkinter `
    --hidden-import pystray `
    --hidden-import PIL `
    --collect-all tkinter `
    $versionFlag `
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

# Копирование в releases/ (onedir: переносим папку с бинарником и _internal)
New-Item -ItemType Directory -Force -Path "releases" | Out-Null
$bundleDir = Join-Path "server/dist" $binaryName
$destDir = Join-Path "releases" $binaryName
try {
    Move-Item $bundleDir $destDir -Force -ErrorAction Stop
} catch {
    if ($cleanVenv) { Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue }
    Error "Не удалось переместить сборку в releases/: $($_.Exception.Message)"
}
Remove-Item -Recurse -Force "server/dist" -ErrorAction SilentlyContinue

$binary = Get-Item (Join-Path $destDir $binaryName) -ErrorAction SilentlyContinue
if (-not $binary) {
    Error "Бинарник не найден. Сборка могла завершиться с ошибкой."
}
$size = "{0:N0} KB" -f ((Get-ChildItem -Recurse -File $destDir | Measure-Object -Property Length -Sum).Sum / 1KB)

Info "Сборка завершена!"
Write-Host ""
Write-Host "Бинарник: $destDir\$binaryName ($size)"
Write-Host ""
Write-Host "Запуск:"
Write-Host "  .\$destDir\$binaryName"
