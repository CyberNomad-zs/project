# 清泉 API 常驻启动（后台进程，不占当前终端）
# 用法:
#   .\scripts\start-api.ps1
#   .\scripts\start-api.ps1 -Port 8000 -ForceRestart
#
# 停止: .\scripts\stop-api.ps1
# 状态: .\scripts\status-api.ps1

param(
  [int]$Port = 8000,
  [switch]$ForceRestart
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'backend'
$venvPy = Join-Path $backend '.venv\Scripts\python.exe'
$envFile = Join-Path $root '.env'
$logsDir = Join-Path $root 'logs'
$pidFile = Join-Path $logsDir 'api.pid'
$outLog = Join-Path $logsDir 'api-daemon.out.log'
$errLog = Join-Path $logsDir 'api-daemon.err.log'

if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

function Get-DotEnv([string]$path) {
  $map = @{}
  if (-not (Test-Path $path)) { return $map }
  Get-Content $path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $i = $line.IndexOf('=')
    if ($i -lt 1) { return }
    $map[$line.Substring(0, $i).Trim()] = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
  }
  return $map
}

function Test-ApiHealth([int]$p) {
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$p/health" -TimeoutSec 2
    return ($h.status -eq 'ok')
  } catch { return $false }
}

function Get-ListenerPids([int]$p) {
  $pids = @()
  try {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($c in @($conns)) {
      if ($c.OwningProcess) { $pids += [int]$c.OwningProcess }
    }
  } catch {}
  return @($pids | Select-Object -Unique)
}

if (-not (Test-Path $venvPy)) {
  Write-Error "未找到 venv Python: $venvPy  请先跑 .\scripts\dev-local.ps1 或创建 backend\.venv"
}

if ((Test-ApiHealth $Port) -and -not $ForceRestart) {
  $existing = Get-ListenerPids $Port
  Write-Host "API 已在运行 http://127.0.0.1:$Port/health  PID=$($existing -join ',')" -ForegroundColor Green
  if ($existing.Count -gt 0) { "$($existing[0])" | Set-Content -Path $pidFile -Encoding ascii }
  exit 0
}

if ($ForceRestart) {
  Write-Host "ForceRestart: 停止占用 $Port 的进程..."
  foreach ($procId in (Get-ListenerPids $Port)) {
    try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {}
  }
  if (Test-Path $pidFile) {
    $old = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($old -match '^\d+$') { try { Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue } catch {} }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 1
}

if (-not (Test-ApiHealth $Port)) {
  foreach ($procId in (Get-ListenerPids $Port)) {
    Write-Host "清理僵死监听 PID=$procId"
    try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {}
  }
  Start-Sleep -Seconds 1
}

$envMap = Get-DotEnv $envFile
$pgUser = if ($envMap['POSTGRES_USER']) { $envMap['POSTGRES_USER'] } else { 'qingquan' }
$pgPass = if ($envMap['POSTGRES_PASSWORD']) { $envMap['POSTGRES_PASSWORD'] } else { 'qingquan' }
$pgDb = if ($envMap['POSTGRES_DB']) { $envMap['POSTGRES_DB'] } else { 'qingquan' }
$pgPort = if ($envMap['POSTGRES_PORT']) { $envMap['POSTGRES_PORT'] } else { '5432' }

$dbUrl = if ($envMap['DATABASE_URL']) { $envMap['DATABASE_URL'] } else {
  "postgresql+asyncpg://${pgUser}:${pgPass}@127.0.0.1:${pgPort}/${pgDb}"
}
$dbUrl = $dbUrl -replace '@db:', '@127.0.0.1:'

# Start-Process 继承当前进程环境
$env:DATABASE_URL = $dbUrl
$env:APP_SECRET_KEY = if ($envMap['APP_SECRET_KEY']) { $envMap['APP_SECRET_KEY'] } else { 'dev-secret' }
$env:INGEST_DEFAULT_API_KEY = if ($envMap['INGEST_DEFAULT_API_KEY']) { $envMap['INGEST_DEFAULT_API_KEY'] } else { 'dev-ingest-key' }
$env:APP_ENV = 'dev'
$env:TZ = 'Asia/Shanghai'
foreach ($k in @('FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_BITABLE_APP_TOKEN','FEISHU_BITABLE_TABLE_TASKS','REDIS_URL','ADMIN_USERNAME','ADMIN_PASSWORD')) {
  if ($envMap[$k]) { Set-Item -Path "Env:$k" -Value $envMap[$k] }
}

# 清空/追加日志
"" | Set-Content -Path $outLog -Encoding utf8
"" | Set-Content -Path $errLog -Encoding utf8

Write-Host "启动 API 常驻: http://127.0.0.1:$Port ..." -ForegroundColor Cyan
$p = Start-Process -FilePath $venvPy `
  -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port") `
  -WorkingDirectory $backend `
  -WindowStyle Hidden `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -PassThru

$ready = $false
$apiPid = $null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 1
  if (Test-ApiHealth $Port) {
    $ready = $true
    $listen = Get-ListenerPids $Port
    $apiPid = if ($listen.Count -gt 0) { $listen[0] } else { $p.Id }
    break
  }
  if ($p.HasExited) {
    Write-Host "启动进程已退出 exit=$($p.ExitCode)。err log:" -ForegroundColor Red
    if (Test-Path $errLog) { Get-Content $errLog -Tail 40 }
    exit 1
  }
}

if (-not $ready) {
  Write-Host "health 超时。err log:" -ForegroundColor Red
  if (Test-Path $errLog) { Get-Content $errLog -Tail 40 }
  exit 1
}

"$apiPid" | Set-Content -Path $pidFile -Encoding ascii
Write-Host "API 常驻已启动 PID=$apiPid  health=ok" -ForegroundColor Green
Write-Host "  文档: http://127.0.0.1:$Port/docs"
Write-Host "  日志: $outLog / $errLog"
Write-Host "  停止: .\scripts\stop-api.ps1"
