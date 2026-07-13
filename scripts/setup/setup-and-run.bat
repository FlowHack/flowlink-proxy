@echo off
setlocal

REM FlowLink Proxy - Windows Source Setup
REM Checks Python + tkinter, creates venv, runs server.

REM --- Check python ---
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python not found.
    echo     Download from: https://www.python.org/downloads/
    echo     Make sure to check "Add Python to PATH" during install.
    exit /b 1
)

REM --- Check tkinter ---
python -c "import tkinter" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] tkinter is not installed.
    echo     Reinstall Python and check "tcl/tk and IDLE" in Optional Features.
    exit /b 1
)

REM --- Create venv ---
if not exist "venv" (
    echo [+] Creating virtual environment...
    python -m venv venv
    echo [+] Virtual environment created.
)

REM --- Install dependencies ---
if exist "server\requirements.txt" (
    echo [+] Installing dependencies...
    call venv\Scripts\pip install -q -r server\requirements.txt
    echo [+] Dependencies installed.
)

REM --- Run server ---
echo [+] Starting FlowLink Proxy...
call venv\Scripts\python -m server %*
