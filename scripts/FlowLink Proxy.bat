@echo off
chcp 65001 >nul
title FlowLink Proxy

:: ═══════════════════════════════════════════════════════════════════
:: FlowLink Proxy — Windows-лаунчер
::
:: Этот скрипт запускает бэкенд FlowLink Proxy и браузер с прокси.
:: Разместите этот bat-файл в одной папке с FlowLink Proxy.exe.
::
:: ═══ НАСТРОЙКА ПЕРЕМЕННЫХ ════════════════════════════════════════
:: Откройте этот файл в текстовом редакторе (ПКМ → «Изменить»)
:: и отредактируйте переменные ниже под вашу систему.
:: ═══════════════════════════════════════════════════════════════════

:: --- Путь к браузеру (ОБЯЗАТЕЛЬНО) ---
:: Замените ПУТЬ_К_БРАУЗЕРУ на реальный путь к exe-файлу вашего браузера.
:: Примеры:
::   C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
::   C:\Program Files\Google\Chrome\Application\chrome.exe
::   C:\Program Files\Microsoft\Edge\Application\msedge.exe
::   C:\Program Files\Mozilla Firefox\firefox.exe
set BROWSER_PATH=ПУТЬ_К_БРАУЗЕРУ

:: --- Порт прокси (по умолчанию 8080) ---
:: Меняйте, только если порт 8080 занят другим процессом.
:: При смене порта обновите также флаг --proxy-server в ярлыке браузера.
set PROXY_PORT=8080

:: ═══ КОНЕЦ НАСТРОЙКИ ═════════════════════════════════════════════

:: --- Определение директории данных и чтение настройки autostart_browser ---
:: Директория данных: %APPDATA%\FlowLink Proxy (Windows) или %USERPROFILE%\.flowlink-proxy
set "DATA_DIR=%USERPROFILE%\.flowlink-proxy"
if defined APPDATA set "DATA_DIR=%APPDATA%\FlowLink Proxy"

set "AUTOSTART_BROWSER=true"
set "SETTINGS_FILE=%DATA_DIR%\.flowlink-settings"
if exist "%SETTINGS_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SETTINGS_FILE%") do (
        if "%%a"=="autostart_browser" set "AUTOSTART_BROWSER=%%b"
    )
)

:: --- Определение пути к бэкенду ---
:: Проверяем: сначала рядом с bat (standalone), потом в server/FlowLink Proxy (dev)
set BACKEND_EXE=
if exist "%~dp0FlowLink Proxy.exe" (
    set "BACKEND_EXE=%~dp0FlowLink Proxy.exe"
) else if exist "%~dp0server\FlowLink Proxy\FlowLink Proxy.exe" (
    set "BACKEND_EXE=%~dp0server\FlowLink Proxy\FlowLink Proxy.exe"
)

if not defined BACKEND_EXE (
    echo.
    echo [!] FlowLink Proxy.exe не найден.
    echo     Убедитесь, что bat-файл лежит в одной папке с FlowLink Proxy.exe
    echo     или в корне проекта FlowLink Proxy.
    echo.
    echo     Если вы собрали бинарник самостоятельно, проверьте папку server\FlowLink Proxy\.
    echo.
    pause
    exit /b 1
)

:: --- Запуск бэкенда ---
tasklist /FI "IMAGENAME eq FlowLink Proxy.exe" /NH 2>nul | find /i "FlowLink Proxy" >nul
if errorlevel 1 (
    echo [+] Запускаю бэкенд FlowLink Proxy...
    start "" "%BACKEND_EXE%" --proxy-port %PROXY_PORT%
) else (
    echo [=] Бэкенд уже запущен.
)

:: --- Запуск браузера (только если autostart_browser=true) ---
if /i "%AUTOSTART_BROWSER%"=="false" (
    echo [=] Автозапуск браузера отключён (настройка autostart_browser=false).
    echo     Для включения: расширение → Настройки → Автозапуск браузера.
) else (
    :: --- Проверка пути к браузеру ---
    if "%BROWSER_PATH%"=="ПУТЬ_К_БРАУЗЕРУ" (
        echo.
        echo [!] Путь к браузеру не указан.
        echo     Откройте этот bat-файл в текстовом редакторе и замените
        echo     "ПУТЬ_К_БРАУЗЕРУ" на путь к вашему браузеру.
        echo.
        echo     Примеры:
        echo       set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
        echo       set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
        echo       set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
        echo.
        pause
        exit /b 1
    )

    if not exist "%BROWSER_PATH%" (
        echo.
        echo [!] Браузер не найден: %BROWSER_PATH%
        echo     Проверьте путь в переменной BROWSER_PATH в начале этого файла.
        echo.
        pause
        exit /b 1
    )

    :: --- Извлечение имени exe из полного пути ---
    set BROWSER_EXE=
    for %%i in ("%BROWSER_PATH%") do set BROWSER_EXE=%%~nxi

    tasklist /FI "IMAGENAME eq %BROWSER_EXE%" /NH 2>nul | find /i "%BROWSER_EXE%" >nul
    if errorlevel 1 (
        echo [+] Запускаю браузер с --proxy-server=127.0.0.1:%PROXY_PORT%...
        start "" "%BROWSER_PATH%" --proxy-server=127.0.0.1:%PROXY_PORT%
    ) else (
        echo [=] Браузер уже запущен.
    )
)

echo.
echo [+] Всё готово к работе!
