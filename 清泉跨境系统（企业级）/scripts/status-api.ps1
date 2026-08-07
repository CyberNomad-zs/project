# 查看清泉 API 是否常驻
param([int]$Port = 8000)

$root = Split-Path $PSScriptRoot -Parent
$pidFile = Join-Path $root 'logs\api.pid'

$health = $false
try {
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
  $health = ($h.status -eq 'ok')
  Write-Host "health: $($h.status) time=$($h.time)"
} catch {
  Write-Host "health: DOWN ($($_.Exception.Message))"
}

$listeners = @()
try {
  $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess } | Select-Object -Unique)
} catch {}
Write-Host "listen port $Port PIDs: $(if ($listeners) { $listeners -join ',' } else { '(none)' })"

if (Test-Path $pidFile) {
  Write-Host "pid file: $(Get-Content $pidFile -Raw)"
} else {
  Write-Host "pid file: (missing)"
}

if ($health) { exit 0 } else { exit 1 }
