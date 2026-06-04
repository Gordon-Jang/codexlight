@echo off
setlocal

cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
    echo [CodexLight] PowerShell was not found in PATH.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '.').Path; " ^
  "$pidFile = Join-Path $root 'codexlight.pid'; " ^
  "$ids = @(); " ^
  "if (Test-Path $pidFile) { $ids += Get-Content $pidFile | Where-Object { $_ -match '^\d+$' } }; " ^
  "$targets = @(); " ^
  "foreach ($id in $ids) { " ^
  "  $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue; " ^
  "  if ($process -and $process.Name -match '^python(?:\.exe)?$' -and $process.CommandLine -match 'codexlight\.cli') { $targets += @($process) } " ^
  "}; " ^
  "if (-not $targets) { " ^
  "  $targets = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(?:\.exe)?$' -and $_.CommandLine -match 'codexlight\.cli' }) " ^
  "}; " ^
  "if (-not $targets) { Write-Host '[CodexLight] No monitor process found.'; exit 0 }; " ^
  "foreach ($process in $targets) { " ^
  "  Stop-Process -Id $process.ProcessId -Force; " ^
  "  Write-Host ('[CodexLight] Stopped monitor process ' + $process.ProcessId) " ^
  "}; " ^
  "Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue"

endlocal
