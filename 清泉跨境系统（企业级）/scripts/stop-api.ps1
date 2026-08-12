# 停止清泉 API 常驻进程
# 用法: .\scripts\stop-api.ps1 [-Port 8000]

param([int]$Port = 8000)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$pidFile = Join-Path $root 'logs\api.pid'

function Get-ListenerPids([int]$p) {
  $pids = @()
  try {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($c in @($conns)) {
      if ($c.OwningProcess) { $pids += [int]$c.OwningProcess }
    }
  } catch {}
  return ($pids | Select-Object -Unique)
}

$stopped = @()
if (Test-Path $pidFile) {
  $old = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($old -match '^\d+$') {
    try {
      Stop-Process -Id ([int]$old) -Force -ErrorAction Stop
      $stopped += [int]$old
    } catch {}
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

foreach ($procId in (Get-ListenerPids $Port)) {
  try {
    Stop-Process -Id $procId -Force -ErrorAction Stop
    $stopped += $procId
  } catch {}
}

Start-Sleep -Milliseconds 500
$left = @(Get-ListenerPids $Port)
if ($left.Count -eq 0) {
  Write-Host "API 已停止 (port $Port). stopped=$($stopped -join ',')" -ForegroundColor Green
} else {
  Write-Host "仍有监听 PID=$($left -join ',')，请手动 Stop-Process" -ForegroundColor Yellow
  exit 1
}
