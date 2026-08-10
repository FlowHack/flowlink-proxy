@echo off
REM FlowLink Proxy - Windows Build Wrapper
REM Runs build.ps1 with ExecutionPolicy Bypass.

powershell -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
exit /b %errorlevel%
