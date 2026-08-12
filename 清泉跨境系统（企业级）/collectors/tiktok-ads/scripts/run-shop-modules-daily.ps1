# Daily shop-modules wrapper (Windows Task Scheduler)
# 主配置全店：KPI + 健康 + 体验分 + 财务 + 违规 + 差评 + 达人健康
# 使用 config\stores.config.json 的 filter（TikTok + requireIp 等），不绑死单店。
# 只写清泉 Ingest，不写飞书。
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-shop-modules-daily.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-shop-modules-daily.ps1 -Modules shop_daily,health_daily
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-shop-modules-daily.ps1 -Modules violation,reviews

param(
  [string]$ConfigPath = "",
  [string]$Modules = "shop_daily,health_daily,experience_daily,finance_daily,violation,reviews,creator_health"
)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = Join-Path $logDir "shop-modules-daily-$stamp.log"

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Add-Content -Path $logFile -Value $line -Encoding UTF8
  Write-Host $line
}

Log "===== TK Shop-Modules Daily START ====="
Log "root=$root"
Log "log=$logFile"
Log "modules=$Modules"

Set-Location $root

$script = Join-Path $root 'scripts\run-shop-modules.ps1'
if (-not (Test-Path $script)) {
  Log "FATAL missing $script"
  exit 1
}

if (-not $ConfigPath) {
  $ConfigPath = Join-Path $root 'config\stores.config.json'
}
if (-not (Test-Path $ConfigPath)) {
  Log "FATAL missing config $ConfigPath"
  exit 1
}
Log "config=$ConfigPath"

# Hidden child PS：计划任务下避免弹窗；强制 DryRun=false 实写清泉
Log "invoke run-shop-modules.ps1 -DryRun false (hidden child)"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = (Get-Command powershell.exe).Source
$psi.Arguments = @(
  '-NoProfile',
  '-NonInteractive',
  '-ExecutionPolicy', 'Bypass',
  '-File', "`"$script`"",
  '-ConfigPath', "`"$ConfigPath`"",
  '-DryRun', 'false',
  '-Modules', "`"$Modules`""
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
  foreach ($line in ($stdout -split "`r?`n")) {
    if ($line.Length -gt 0) { Log "OUT $line" }
  }
}
if ($stderr) {
  foreach ($line in ($stderr -split "`r?`n")) {
    if ($line.Length -gt 0) { Log "ERR $line" }
  }
}

Log "exitCode=$code"
Log "===== TK Shop-Modules Daily END ====="
exit $code
