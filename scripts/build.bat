@echo off
chcp 65001 >nul
REM Обёртка для build.ps1 с обходом ExecutionPolicy (файл без подписи).
REM Использование: scripts\build.bat

powershell -ExecutionPolicy Bypass -File "%~dp0build.ps1"
