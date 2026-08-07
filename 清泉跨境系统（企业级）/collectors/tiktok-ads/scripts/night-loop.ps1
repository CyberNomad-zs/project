# Night loop for TK collectors (ads + orders + products + shop-modules)
# Runs until stopped. When Ziniao Bridge is up, executes collect scripts.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1 -IntervalSec 600
#   powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1 -AdsOnly
#   powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1 -SkipAds

param(
  [int]$IntervalSec = 900,
  [switch]$AdsOnly,
  [switch]$OrdersOnly,
  [switch]$SkipAds,
  [switch]$SkipOrders,
  [switch]$SkipProducts,
  [switch]$SkipShopModules,
  [string]$DryRun = "false",
  # After a successful collector round: rules + Feishu sync (tk-p0-post-collect.ps1)
  [switch]$RunPostCollect,
  [int]$PostLookbackDays = 7
)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$logFile = Join-Path $logs ("night-loop-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Log([string]$m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
  Write-Host $line
  Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

function Test-Bridge {
  try {
    $tnc = Test-NetConnection -ComputerName '127.0.0.1' -Port 9481 -WarningAction SilentlyContinue
    if ($tnc -and $tnc.TcpTestSucceeded) { return $true }
  } catch { }
  try {
    Invoke-WebRequest -Uri 'http://127.0.0.1:9481/' -TimeoutSec 3 -UseBasicParsing | Out-Null
    return $true
  } catch {
    $msg = [string]$_.Exception.Message
    if ($msg -match '401|403|400|200') { return $true }
    if ($_.Exception.Response) { return $true }
    return $false
  }
}

function Invoke-Collector([string]$name, [string]$file, [string[]]$extra) {
  Log "$name ..."
  try {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot $file)) + $extra
    & powershell @args
    Log ("{0} exit={1}" -f $name, $LASTEXITCODE)
  } catch {
    Log ("{0} error: {1}" -f $name, $_)
  }
}

Log "night-loop start interval=${IntervalSec}s log=$logFile"
$round = 0
while ($true) {
  $round++
  Log "===== round $round ====="
  if (-not (Test-Bridge)) {
    Log "Bridge down — skip scrape"
  } else {
    Log "Bridge up — run collectors"
    $doAds = -not $SkipAds -and -not $OrdersOnly
    $doOrders = -not $SkipOrders -and -not $AdsOnly
    $doProducts = -not $SkipProducts -and -not $AdsOnly -and -not $OrdersOnly
    $doShop = -not $SkipShopModules -and -not $AdsOnly -and -not $OrdersOnly

    if ($doAds) { Invoke-Collector 'ads' 'run-multi-store.ps1' @('-DryRun', $DryRun) }
    if ($doShop) { Invoke-Collector 'shop-modules' 'run-shop-modules.ps1' @('-DryRun', $DryRun) }
    if ($doOrders) { Invoke-Collector 'orders' 'run-orders.ps1' @('-DryRun', $DryRun) }
    if ($doProducts) { Invoke-Collector 'products' 'run-products.ps1' @('-DryRun', $DryRun) }

    if ($RunPostCollect -and $DryRun -ne 'true') {
      $repoRoot = Split-Path $root -Parent
      $post = Join-Path $repoRoot 'scripts\tk-p0-post-collect.ps1'
      if (Test-Path $post) {
        Log "post-collect ..."
        try {
          & powershell -NoProfile -ExecutionPolicy Bypass -File $post -LookbackDays $PostLookbackDays
          Log ("post-collect exit={0}" -f $LASTEXITCODE)
        } catch {
          Log ("post-collect error: {0}" -f $_)
        }
      } else {
        Log "WARN post-collect missing: $post"
      }
    }
  }
  Log "sleep ${IntervalSec}s"
  Start-Sleep -Seconds $IntervalSec
}
