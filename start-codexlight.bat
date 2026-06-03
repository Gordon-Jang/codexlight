@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [CodexLight] Python was not found in PATH.
    echo Install Python or add it to PATH, then run this file again.
    pause
    exit /b 1
)

echo [CodexLight] Starting the top status light monitor...
echo [CodexLight] Close the light window to stop the monitor.
echo.

python -m codexlight.cli %*

echo.
echo [CodexLight] CodexLight exited.
pause
