# Install Windows Scheduled Task: daily products (full-store main config)
# Default 20:20 — after orders 20:00.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-products-daily-task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-products-daily-task.ps1 -Time "20:20"
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-products-daily-task.ps1 -Uninstall

param(
  [string]$Time = '20:20',
  [string]$TaskName = 'TK-Products-Daily',
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$wrapper = Join-Path $root 'scripts\run-products-daily.ps1'
$mainConfig = Join-Path $root 'config\stores.config.json'

if ($Uninstall) {
  cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
  Write-Host "Removed task: $TaskName"
  exit 0
}

if (-not (Test-Path $wrapper)) { throw "Missing $wrapper" }
if (-not (Test-Path $mainConfig)) { throw "Missing $mainConfig" }

if ($Time -notmatch '^(\d{1,2}):(\d{2})$') { throw "Invalid -Time $Time" }
$st = '{0:D2}:{1:D2}' -f [int]$Matches[1], [int]$Matches[2]

try {
  $cfg = Get-Content -LiteralPath $mainConfig -Raw -Encoding UTF8 | ConvertFrom-Json
  $inc = @()
  if ($cfg.filter -and $cfg.filter.includeStoreIds) {
    $inc = @($cfg.filter.includeStoreIds | Where-Object { $_ -and ("$_").Trim() -ne '' })
  }
  if ($inc.Count -gt 0) {
    Write-Host ("WARN: includeStoreIds set -> not full-store: {0}" -f ($inc -join ','))
  } else {
    Write-Host "OK: includeStoreIds empty -> full-store filter."
  }
} catch {
  Write-Host ("WARN: config check failed: {0}" -f $_)
}

$ErrorActionPreference = 'Continue'
cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
$ErrorActionPreference = 'Stop'

$tr = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $wrapper
Write-Host ("Creating {0} daily {1} ..." -f $TaskName, $st)
$createOut = cmd /c "schtasks /Create /TN `"$TaskName`" /TR `"$tr`" /SC DAILY /ST $st /RL LIMITED /F 2>&1"
Write-Host $createOut
if ($LASTEXITCODE -ne 0) { throw "schtasks failed: $createOut" }

Write-Host ""
Write-Host "OK. Task $TaskName at $st -> $wrapper"
Write-Host "  Note: product/manage uses open+settle (no page visit) to protect Bridge."
Write-Host "Test: schtasks /Run /TN $TaskName"
Write-Host "Uninstall: powershell -File .\scripts\install-products-daily-task.ps1 -Uninstall"
