# Install / update Windows Scheduled Task: TK P0 post-collect
# (ads + product anomaly rules → Feishu T1/T2/anomaly sync)
#
# Place AFTER collectors on the same machine that can reach PG + Feishu:
#   ads ~17:20 (colleague) · shop 19:45 · orders 20:00 · products 20:20
# Default post-collect: 21:00
#
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-tk-p0-post-collect-daily-task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-tk-p0-post-collect-daily-task.ps1 -Time "21:00"
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-tk-p0-post-collect-daily-task.ps1 -LookbackDays 7
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-tk-p0-post-collect-daily-task.ps1 -Uninstall

param(
  [string]$Time = '21:00',
  [string]$TaskName = 'TK-P0-Post-Collect-Daily',
  [int]$LookbackDays = 14,
  [switch]$SkipRules,
  [switch]$SkipFeishu,
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $RepoRoot 'backend\app'))) {
  $RepoRoot = $PSScriptRoot
  if (-not (Test-Path (Join-Path $RepoRoot 'backend\app'))) {
    $RepoRoot = Split-Path $PSScriptRoot -Parent
  }
}
$wrapper = Join-Path $RepoRoot 'scripts\tk-p0-post-collect.ps1'

if ($Uninstall) {
  cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
  Write-Host "Removed task: $TaskName"
  exit 0
}

if (-not (Test-Path $wrapper)) {
  throw "Missing $wrapper"
}

if ($Time -notmatch '^(\d{1,2}):(\d{2})$') {
  throw "Invalid -Time $Time, use HH:mm e.g. 21:00"
}
$hh = [int]$Matches[1]
$mm = [int]$Matches[2]
if ($hh -gt 23 -or $mm -gt 59) { throw "Invalid time $Time" }
$st = '{0:D2}:{1:D2}' -f $hh, $mm

$argExtra = @('-LookbackDays', "$LookbackDays")
if ($SkipRules) { $argExtra += '-SkipRules' }
if ($SkipFeishu) { $argExtra += '-SkipFeishu' }
$argStr = ($argExtra -join ' ')

$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
$ErrorActionPreference = $prevEap

# schtasks /TR quoting: wrap whole powershell -File ... args
$tr = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}" {1}' -f $wrapper, $argStr

Write-Host ("Creating task {0} at daily {1} ..." -f $TaskName, $st)
Write-Host ("Command: {0}" -f $tr)
$createOut = cmd /c "schtasks /Create /TN `"$TaskName`" /TR `"$tr`" /SC DAILY /ST $st /RL LIMITED /F 2>&1"
Write-Host $createOut
if ($LASTEXITCODE -ne 0) {
  throw ("schtasks create failed exit={0}`n{1}" -f $LASTEXITCODE, $createOut)
}

Write-Host ""
Write-Host "OK. Task installed."
Write-Host ("  Name     : {0}" -f $TaskName)
Write-Host ("  When     : every day {0} (local time)" -f $st)
Write-Host ("  Run      : {0}" -f $wrapper)
Write-Host ("  Lookback : {0} days" -f $LookbackDays)
Write-Host "  Steps    : ads anomaly eval → product anomaly eval → feishu_tk_daily_sync"
Write-Host ""
Write-Host "Prerequisites at run time:"
Write-Host "  1) PostgreSQL reachable (DATABASE_URL / backend .env)"
Write-Host "  2) FEISHU_APP_ID/SECRET + TK table ids in .env"
Write-Host "  3) Collectors for the day already finished (or accept stale facts)"
Write-Host "  4) API not required (jobs use DB + Feishu directly)"
Write-Host ""
Write-Host "Manual test:"
Write-Host ("  schtasks /Run /TN {0}" -f $TaskName)
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\tk-p0-post-collect.ps1 -DryRun"
Write-Host "  Get-ChildItem logs\tk-p0-post-collect-*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Get-Content -LiteralPath `$_.FullName -Tail 80 }"
Write-Host ""
Write-Host "Query / Uninstall:"
Write-Host ("  schtasks /Query /TN {0} /V /FO LIST" -f $TaskName)
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\install-tk-p0-post-collect-daily-task.ps1 -Uninstall"
