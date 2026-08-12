# Install one combined daily task: shop-modules + orders + products (NOT ads).
# Default 19:50 — night chain (+2h vs old 17:50); after ads 17:20. Prefer this OR the three split tasks, not both.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-full-site-daily-task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-full-site-daily-task.ps1 -Time "19:50"
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-full-site-daily-task.ps1 -Uninstall

param(
  [string]$Time = '19:50',
  [string]$TaskName = 'TK-Full-Site-Daily',
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$wrapper = Join-Path $root 'scripts\run-full-site-daily.ps1'

if ($Uninstall) {
  cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
  Write-Host "Removed task: $TaskName"
  exit 0
}

if (-not (Test-Path $wrapper)) { throw "Missing $wrapper" }
if ($Time -notmatch '^(\d{1,2}):(\d{2})$') { throw "Invalid -Time $Time" }
$st = '{0:D2}:{1:D2}' -f [int]$Matches[1], [int]$Matches[2]

Write-Host "NOTE: If TK-Shop-Modules-Daily / TK-Orders-Daily / TK-Products-Daily are also installed,"
Write-Host "      disable them to avoid double runs the same evening."

$ErrorActionPreference = 'Continue'
cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
$ErrorActionPreference = 'Stop'

$tr = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $wrapper
$createOut = cmd /c "schtasks /Create /TN `"$TaskName`" /TR `"$tr`" /SC DAILY /ST $st /RL LIMITED /F 2>&1"
Write-Host $createOut
if ($LASTEXITCODE -ne 0) { throw "schtasks failed: $createOut" }

Write-Host ""
Write-Host "OK. $TaskName daily $st -> run-full-site-daily.ps1"
Write-Host "  Chain: shop-modules -> orders -> products (ads separate)"
Write-Host "Test: schtasks /Run /TN $TaskName"
Write-Host "Uninstall: powershell -File .\scripts\install-full-site-daily-task.ps1 -Uninstall"
