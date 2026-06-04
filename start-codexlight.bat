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

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '.').Path; " ^
  "$python = (Get-Command python).Source; " ^
  "$process = Start-Process -FilePath $python -ArgumentList @('-m','codexlight.cli') -WorkingDirectory $root -WindowStyle Hidden -PassThru; " ^
  "$process.Id | Set-Content -Encoding ASCII -Path (Join-Path $root 'codexlight.pid'); " ^
  "Write-Host ('[CodexLight] Started monitor process ' + $process.Id); " ^
  "Write-Host '[CodexLight] Use stop-codexlight.bat to stop the monitor.'"
