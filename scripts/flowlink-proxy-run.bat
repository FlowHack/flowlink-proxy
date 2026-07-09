@echo off
chcp 65001 >nul
title FlowLink Proxy

:: ─────────────────────────────────────────────────────────────
:: FlowLink Proxy — лаунчер (для standalone-сборки)
::
:: Бэкенд запускается по относительному пути рядом с этим bat.
:: Браузер — укажите путь ниже в переменной BROWSER_PATH.
:: ─────────────────────────────────────────────────────────────

:: ═══ УКАЖИТЕ ПУТЬ К БРАУЗЕРУ ═══
:: Примеры:
::   set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
::   set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
::   set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
::   set BROWSER_PATH=C:\Program Files\Mozilla Firefox\firefox.exe
set BROWSER_PATH=ПУТЬ_К_БРАУЗЕРУ
:: ════════════════════════════════

:: Порт прокси (по умолчанию 8080)
set PROXY_PORT=8080

:: --- Запуск бэкенда ---
set BACKEND_EXE=%~dp0FlowLink Proxy.exe
if not exist "%BACKEND_EXE%" (
    echo [!] FlowLink Proxy.exe не найден рядом с этим bat-файлом.
    echo     Убедитесь, что bat лежит в одной папке с exe.
    pause
    exit /b 1
)

tasklist /FI "IMAGENAME eq FlowLink Proxy.exe" /NH 2>nul | find /i "FlowLink Proxy" >nul
if errorlevel 1 (
    echo [+] Запускаю бэкенд FlowLink Proxy...
    start "" "%BACKEND_EXE%" --proxy-port %PROXY_PORT%
) else (
    echo [=] Бэкенд уже запущен.
)

:: --- Запуск браузера ---
if "%BROWSER_PATH%"=="ПУТЬ_К_БРАУЗЕРУ" (
    echo.
    echo [!] Путь к браузеру не указан.
    echo     Откройте этот bat-файл в текстовом редакторе и замените
    echo     "ПУТЬ_К_БРАУЗЕРУ" на путь к вашему браузеру.
    echo.
    pause
    exit /b 1
)

if not exist "%BROWSER_PATH%" (
    echo [!] Браузер не найден: %BROWSER_PATH%
    echo     Проверьте путь в переменной BROWSER_PATH.
    pause
    exit /b 1
)

set BROWSER_EXE=
for %%i in ("%BROWSER_PATH%") do set BROWSER_EXE=%%~nxi

tasklist /FI "IMAGENAME eq %BROWSER_EXE%" /NH 2>nul | find /i "%BROWSER_EXE%" >nul
if errorlevel 1 (
    echo [+] Запускаю браузер с --proxy-server=127.0.0.1:%PROXY_PORT%...
    start "" "%BROWSER_PATH%" --proxy-server=127.0.0.1:%PROXY_PORT%
) else (
    echo [=] Браузер уже запущен.
)

echo.
echo [+] Всё готово к работе!
