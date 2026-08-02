# ============================================================================
# FlowLink Proxy — скрипт развёртывания для Windows
#
# Выполняет полный цикл:
#   1. Очистка данных приложения в AppData (сохраняя прокси, ключ и соль)
#   2. Сборка exe из проекта (лежащего в WSL)
#   3. Копирование exe в целевую папку
#   4. Очистка мусорных артефактов сборки
#
# Запуск из Windows PowerShell:
#   powershell -ExecutionPolicy Bypass -File deploy.ps1
# ============================================================================

$ErrorActionPreference = 'Stop'

# --- Конфигурация -----------------------------------------------------------
# Путь к проекту в WSL (сетевой путь, видимый из Windows)
$ProjectWsl = '\\wsl.localhost\Ubuntu\home\flowhack-wsl\GitHub\flowlink-proxy'
# Целевая папка для итогового exe
$TargetDir = 'P:\FlowLink Proxy'
# Папка данных приложения
$DataDir = Join-Path $env:APPDATA 'FlowHack\FlowLink Proxy'

# --- Хелперы вывода ---------------------------------------------------------
function Info  { Write-Host "[+] $args" -ForegroundColor Green }
function Warn  { Write-Host "[!] $args" -ForegroundColor Yellow }
function Error { Write-Host "[X] $args" -ForegroundColor Red; exit 1 }

# --- Проверка доступности проекта -------------------------------------------
if (-not (Test-Path $ProjectWsl)) {
    Error "Проект WSL не найден: $ProjectWsl"
}

# --- 1. Очистка данных приложения (сохраняя прокси, ключ и соль) ------------
Info 'Очистка данных приложения (сохраняю прокси, ключ и соль)...'

$removedCount = 0
if (Test-Path $DataDir) {
    # Файлы, которые НЕ удаляем (нужны для расшифровки паролей прокси)
    $KeepFiles = @('config.json', '.flowlink.key', '.flowlink.salt')

    Get-ChildItem -Path $DataDir -Force | ForEach-Object {
        if ($KeepFiles -contains $_.Name) {
            return
        }
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
        $removedCount++
    }
    Info "Удалено элементов данных: $removedCount"
} else {
    Warn "Папка данных не найдена: $DataDir"
}

# --- 2. Сборка exe из проекта в WSL -----------------------------------------
Info 'Запуск сборки из WSL-проекта...'

Push-Location $ProjectWsl
try {
    # build.bat — обёртка, запускающая build.ps1 (PyInstaller)
    & "$ProjectWsl\scripts\build\build.bat"
    if ($LASTEXITCODE -ne 0) {
        Error "Сборка завершилась с ошибкой (код $LASTEXITCODE)"
    }
} finally {
    Pop-Location
}

$BuiltExe = Join-Path $ProjectWsl 'releases\FlowLink Proxy.exe'
if (-not (Test-Path $BuiltExe)) {
    Error "Собранный exe не найден: $BuiltExe"
}

# --- 3. Копирование exe в целевую папку -------------------------------------
Info 'Копирование exe в целевую папку...'

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}
Copy-Item -LiteralPath $BuiltExe -Destination $TargetDir -Force
Info "Скопировано: $BuiltExe -> $TargetDir"

# --- 4. Очистка мусорных артефактов сборки ----------------------------------
Info 'Очистка артефактов сборки...'

# Папка releases/ в проекте (exe уже скопирован)
$ReleasesDir = Join-Path $ProjectWsl 'releases'
if (Test-Path $ReleasesDir) {
    Remove-Item -LiteralPath $ReleasesDir -Recurse -Force
    Info 'Удалена папка releases/'
}

# __pycache__ по всему проекту, КРОМЕ .venv (рабочий venv разработки)
$pycacheCount = 0
Get-ChildItem -Path $ProjectWsl -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\\.venv\\' } |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
        $pycacheCount++
    }
if ($pycacheCount -gt 0) {
    Info "Удалено папок __pycache__: $pycacheCount"
}

# --- Запуск ----------------------------------------------------------------
$TargetExe = Join-Path $TargetDir 'FlowLink Proxy.exe'
Info "Запуск: $TargetExe"
Start-Process -FilePath $TargetExe

Info 'Готово.'
