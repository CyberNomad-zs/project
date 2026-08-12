# Disable auto-start: stop and remove scheduled task 'TemuMonitor'. Self-elevates.
$ErrorActionPreference = 'SilentlyContinue'

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
  exit
}

Stop-ScheduledTask -TaskName 'TemuMonitor' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'TemuMonitor' -Confirm:$false -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '  [OK] Auto-start removed.'
Write-Host '  (If a monitoring window is still open, just close it.)'
Write-Host ''
Write-Host '  Press Enter to close...'
Read-Host | Out-Null
