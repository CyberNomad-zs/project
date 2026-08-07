# Daily orders wrapper (Windows Task Scheduler)
# Full-store via config\stores.config.json filter (TikTok + requireIp + exclude).
# Qingquan ingest only (tiktok_orders). No Feishu.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-orders-daily.ps1

param(
  [string]$ConfigPath = ""
)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = Join-Path $logDir "orders-daily-$stamp.log"

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Add-Content -Path $logFile -Value $line -Encoding UTF8
  Write-Host $line
}

Log "===== TK Orders Daily START ====="
Log "root=$root log=$logFile"
Set-Location $root

$script = Join-Path $root 'scripts\run-orders.ps1'
if (-not (Test-Path $script)) { Log "FATAL missing $script"; exit 1 }
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
if (-not (Test-Path $ConfigPath)) { Log "FATAL missing $ConfigPath"; exit 1 }
Log "config=$ConfigPath"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = (Get-Command powershell.exe).Source
$psi.Arguments = @(
  '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
  '-File', "`"$script`"",
  '-ConfigPath', "`"$ConfigPath`"",
  '-DryRun', 'false'
) -join ' '
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$utf8 = [System.Text.UTF8Encoding]::new($false)
$psi.StandardOutputEncoding = $utf8
$psi.StandardErrorEncoding = $utf8

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
[void]$p.Start()
$stdout = $p.StandardOutput.ReadToEnd()
$stderr = $p.StandardError.ReadToEnd()
$p.WaitForExit()
$code = $p.ExitCode

if ($stdout) {
  foreach ($line in ($stdout -split "`r?`n")) { if ($line.Length -gt 0) { Log "OUT $line" } }
}
if ($stderr) {
  foreach ($line in ($stderr -split "`r?`n")) { if ($line.Length -gt 0) { Log "ERR $line" } }
}

Log "exitCode=$code"
Log "===== TK Orders Daily END ====="
exit $code
