@echo off
REM Wrapper for build.ps1 with ExecutionPolicy bypass (unsigned script).
REM Usage: scripts\build.bat

powershell -ExecutionPolicy Bypass -File "%~dp0build.ps1"
