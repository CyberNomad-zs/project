# Install / update Windows Scheduled Task: daily 17:20
# Run as Administrator recommended if task must start when user not interactive.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-daily-task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-daily-task.ps1 -Time "17:20"
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-daily-task.ps1 -Uninstall

param(
  [string]$Time = '17:20',
  [string]$TaskName = 'TK-Ad-Daily-Report',
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$wrapper = Join-Path $root 'scripts\run-daily-report.ps1'

if ($Uninstall) {
  cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
  Write-Host "Removed task: $TaskName"
  exit 0
}

if (-not (Test-Path $wrapper)) {
  throw "Missing $wrapper"
}

# Parse HH:mm
if ($Time -notmatch '^(\d{1,2}):(\d{2})$') {
  throw "Invalid -Time $Time, use HH:mm e.g. 17:20"
}
$hh = [int]$Matches[1]
$mm = [int]$Matches[2]
if ($hh -gt 23 -or $mm -gt 59) { throw "Invalid time $Time" }
$st = '{0:D2}:{1:D2}' -f $hh, $mm

# Remove old (ignore if not exists)
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
cmd /c "schtasks /Delete /TN `"$TaskName`" /F >nul 2>&1"
$ErrorActionPreference = $prevEap

# Create: run as current user when logged on (Ziniao needs desktop session)
$tr = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $wrapper

Write-Host "Creating task $TaskName at daily $st ..."
Write-Host "Command: $tr"
$createOut = cmd /c "schtasks /Create /TN `"$TaskName`" /TR `"$tr`" /SC DAILY /ST $st /RL LIMITED /F 2>&1"
Write-Host $createOut
if ($LASTEXITCODE -ne 0) {
  throw "schtasks create failed exit=$LASTEXITCODE `n$createOut"
}

Write-Host ""
Write-Host "OK. Task installed."
Write-Host "  Name : $TaskName"
Write-Host "  When : every day $st (local time)"
Write-Host "  Run  : $wrapper"
Write-Host ""
Write-Host "Prerequisites at run time:"
Write-Host "  1) This Windows user is logged in (desktop session)"
Write-Host "  2) Ziniao browser client is running and logged in"
Write-Host "  3) config\stores.config.json has Feishu credentials"
Write-Host "  4) Stores bound with IP (requireIp=true)"
Write-Host ""
Write-Host "Manual test now:"
Write-Host "  schtasks /Run /TN $TaskName"
Write-Host "  Get-Content logs\daily-report-*.log -Tail 50"
Write-Host ""
Write-Host "Query:"
Write-Host "  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Uninstall:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\install-daily-task.ps1 -Uninstall"
