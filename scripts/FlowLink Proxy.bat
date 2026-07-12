@echo off
title FlowLink Proxy

:: ========================================================
:: FlowLink Proxy -- Windows-launcher
::
:: This script starts FlowLink Proxy backend and browser with proxy.
:: Place this bat file in the same folder as FlowLink Proxy.exe.
::
:: === SETTINGS ===
:: Open this file in a text editor (right-click -> Edit)
:: and edit the variables below for your system.
:: ========================================================

:: --- Browser path (REQUIRED) ---
:: Replace CHANGE_ME with the real path to your browser exe.
:: IMPORTANT: quotes are NOT needed in the set line (even if path has spaces).
:: Examples:
::   set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
::   set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
::   set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
::   set BROWSER_PATH=C:\Program Files\Mozilla Firefox\firefox.exe
set BROWSER_PATH=CHANGE_ME

:: --- Proxy port (default 8080) ---
:: Change only if port 8080 is occupied by another process.
:: When changing port, also update --proxy-server flag in browser shortcut.
set PROXY_PORT=8080

:: === END OF SETTINGS ===

:: --- Data directory detection and autostart_browser setting ---
set "DATA_DIR=%USERPROFILE%\.flowlink-proxy"
if defined APPDATA set "DATA_DIR=%APPDATA%\FlowLink Proxy"

set "AUTOSTART_BROWSER=true"
set "SETTINGS_FILE=%DATA_DIR%\.flowlink-settings"
if exist "%SETTINGS_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SETTINGS_FILE%") do (
        if "%%a"=="autostart_browser" set "AUTOSTART_BROWSER=%%b"
    )
)

:: --- Backend path detection ---
:: Check: first next to bat (standalone), then in server\FlowLink Proxy (dev)
set BACKEND_EXE=
if exist "%~dp0FlowLink Proxy.exe" (
    set "BACKEND_EXE=%~dp0FlowLink Proxy.exe"
) else if exist "%~dp0server\FlowLink Proxy\FlowLink Proxy.exe" (
    set "BACKEND_EXE=%~dp0server\FlowLink Proxy\FlowLink Proxy.exe"
)

if not defined BACKEND_EXE (
    echo.
    echo [!] FlowLink Proxy.exe not found.
    echo     Make sure the bat file is in the same folder as FlowLink Proxy.exe
    echo     or in the root of the FlowLink Proxy project.
    echo.
    echo     If you built the binary yourself, check the server\FlowLink Proxy\ folder.
    echo.
    pause
    exit /b 1
)

:: --- Start backend ---
tasklist /FI "IMAGENAME eq FlowLink Proxy.exe" /NH 2>nul | find /i "FlowLink Proxy" >nul
if errorlevel 1 (
    echo [+] Starting FlowLink Proxy backend...
    start "" "%BACKEND_EXE%" --proxy-port %PROXY_PORT%
) else (
    echo [=] Backend is already running.
)

:: --- Start browser (only if autostart_browser=true) ---
if /i not "%AUTOSTART_BROWSER%"=="false" goto :start_browser
echo [=] Browser autostart is disabled (autostart_browser=false).
echo     To enable: extension, Settings, Browser autostart.
goto :eof

:start_browser
if not "%BROWSER_PATH%"=="CHANGE_ME" goto :check_browser
echo.
echo [!] Browser path is not set.
echo     Open this bat file in a text editor and replace
echo     "CHANGE_ME" with the path to your browser.
echo.
echo     Examples:
echo       set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
echo       set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
echo       set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
echo.
pause
exit /b 1

:check_browser
if exist "%BROWSER_PATH%" goto :extract_name
echo.
echo [!] Browser not found: %BROWSER_PATH%
echo     Check the BROWSER_PATH variable at the top of this file.
echo.
pause
exit /b 1

:extract_name
set BROWSER_EXE=
for %%i in ("%BROWSER_PATH%") do set BROWSER_EXE=%%~nxi

tasklist /FI "IMAGENAME eq %BROWSER_EXE%" /NH 2>nul | find /i "%BROWSER_EXE%" >nul
if errorlevel 1 (
    echo [+] Starting browser with --proxy-server=127.0.0.1:%PROXY_PORT%...
    start "" "%BROWSER_PATH%" --proxy-server=127.0.0.1:%PROXY_PORT%
) else (
    echo [=] Browser is already running.
)

echo.
echo [+] Everything is ready!
