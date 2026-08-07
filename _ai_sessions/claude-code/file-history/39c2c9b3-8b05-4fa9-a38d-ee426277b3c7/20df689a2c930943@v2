# Enable auto-start: register scheduled task 'TemuMonitor' (runs daemon at logon).
# Requires admin; self-elevates via UAC if not already elevated.
$ErrorActionPreference = 'Stop'

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
  exit
}

$root = $PSScriptRoot
$daemon = Join-Path $root 'run-forever.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $daemon + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

$params = @{
  TaskName    = 'TemuMonitor'
  Action      = $action
  Trigger     = $trigger
  Principal   = $principal
  Settings    = $settings
  Description = 'Temu monitor (auto-start at logon, auto-restart, 15-min polling)'
  Force       = $true
}
Register-ScheduledTask @params | Out-Null
Start-ScheduledTask -TaskName 'TemuMonitor'

Write-Host ''
Write-Host ('  [OK] Auto-start enabled and started. Account: ' + $user)
Write-Host '  It runs in background after you log in. Logs are in the logs folder.'
Write-Host ''
Write-Host '  Press Enter to close...'
Read-Host | Out-Null
