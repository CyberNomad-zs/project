# 无 Docker 时本地启动清泉 API（需本机 PostgreSQL）
# 用法（管理员 PowerShell 可选）:
#   .\scripts\dev-local.ps1
#   .\scripts\dev-local.ps1 -Seed
#   .\scripts\dev-local.ps1 -Mock

param(
  [switch]$Seed,
  [switch]$Mock,
  [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'backend'
$envFile = Join-Path $root '.env'

Write-Host "== 清泉本地开发启动 ==" -ForegroundColor Cyan

# 定位 psql / postgres
$pgRoots = @(
  'C:\Program Files\PostgreSQL\16',
  'C:\Program Files\PostgreSQL\17',
  'C:\Program Files\PostgreSQL\15',
  'C:\Program Files\PostgreSQL\14'
)
$pgRoot = $pgRoots | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pgRoot) {
  Write-Warning "未找到 PostgreSQL 安装目录。请先安装 PostgreSQL 16，或改用 Docker。"
  Write-Host "winget install --id PostgreSQL.PostgreSQL.16 -e"
  exit 1
}
$psql = Join-Path $pgRoot 'bin\psql.exe'
$env:Path = "$(Join-Path $pgRoot 'bin');$env:Path"
Write-Host "PostgreSQL: $pgRoot"

if (-not (Test-Path $envFile)) {
  Copy-Item (Join-Path $root '.env.example') $envFile
  Write-Host "已复制 .env.example -> .env"
}

# 读取简单 env（KEY=VALUE）
function Get-DotEnv([string]$path) {
  $map = @{}
  Get-Content $path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $i = $line.IndexOf('=')
    if ($i -lt 1) { return }
    $k = $line.Substring(0, $i).Trim()
    $v = $line.Substring($i + 1).Trim()
    $map[$k] = $v
  }
  return $map
}

$envMap = Get-DotEnv $envFile
$pgUser = if ($envMap['POSTGRES_USER']) { $envMap['POSTGRES_USER'] } else { 'qingquan' }
$pgPass = if ($envMap['POSTGRES_PASSWORD']) { $envMap['POSTGRES_PASSWORD'] } else { 'qingquan' }
$pgDb = if ($envMap['POSTGRES_DB']) { $envMap['POSTGRES_DB'] } else { 'qingquan' }
$pgPort = if ($envMap['POSTGRES_PORT']) { $envMap['POSTGRES_PORT'] } else { '5432' }

# 尝试用当前 Windows 用户连 postgres 维护库创建角色（若失败则提示手动）
$env:PGPASSWORD = $pgPass
$createSql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$pgUser') THEN
    CREATE ROLE $pgUser LOGIN PASSWORD '$pgPass';
  END IF;
END
`$`$;
SELECT 'role_ok' AS s;
"@

Write-Host "检查/创建数据库角色与库..."
$ok = $false
foreach ($super in @('postgres', $env:USERNAME)) {
  try {
    $env:PGPASSWORD = if ($super -eq 'postgres') {
      # 常见默认；若安装时设了别的密码会失败
      if ($env:POSTGRES_SUPER_PASSWORD) { $env:POSTGRES_SUPER_PASSWORD } else { 'postgres' }
    } else { $pgPass }
    & $psql -h 127.0.0.1 -p $pgPort -U $super -d postgres -v ON_ERROR_STOP=1 -c $createSql 2>$null | Out-Null
    $exists = & $psql -h 127.0.0.1 -p $pgPort -U $super -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$pgDb'" 2>$null
    if ("$exists".Trim() -ne '1') {
      & $psql -h 127.0.0.1 -p $pgPort -U $super -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $pgDb OWNER $pgUser;" 2>$null | Out-Null
    }
    $env:PGPASSWORD = $pgPass
    & $psql -h 127.0.0.1 -p $pgPort -U $pgUser -d $pgDb -v ON_ERROR_STOP=1 -f (Join-Path $backend 'migrations\001_init.sql') | Out-Null
    $ok = $true
    Write-Host "数据库就绪: $pgDb @ 127.0.0.1:$pgPort"
    break
  } catch {
    continue
  }
}

if (-not $ok) {
  Write-Warning @"
自动建库失败。请手动执行（把密码换成你的 postgres 超级用户密码）:

  set PGPASSWORD=你的postgres密码
  "$psql" -U postgres -c "CREATE USER $pgUser WITH PASSWORD '$pgPass';"
  "$psql" -U postgres -c "CREATE DATABASE $pgDb OWNER $pgUser;"
  "$psql" -U $pgUser -d $pgDb -f "$backend\migrations\001_init.sql"

或安装时记住的超级用户密码设到环境变量 POSTGRES_SUPER_PASSWORD 后重跑本脚本。
"@
  exit 1
}

# Python venv
$venv = Join-Path $backend '.venv'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) {
  Write-Host "创建 venv..."
  python -m venv $venv
}
if (-not $SkipInstall) {
  Write-Host "安装 Python 依赖..."
  & $py -m pip install -q -r (Join-Path $backend 'requirements.txt')
}

$env:DATABASE_URL = "postgresql+asyncpg://${pgUser}:${pgPass}@127.0.0.1:${pgPort}/${pgDb}"
$env:APP_SECRET_KEY = if ($envMap['APP_SECRET_KEY']) { $envMap['APP_SECRET_KEY'] } else { 'dev-secret' }
$env:INGEST_DEFAULT_API_KEY = if ($envMap['INGEST_DEFAULT_API_KEY']) { $envMap['INGEST_DEFAULT_API_KEY'] } else { 'dev-ingest-key' }
$env:ADMIN_USERNAME = if ($envMap['ADMIN_USERNAME']) { $envMap['ADMIN_USERNAME'] } else { 'admin' }
$env:ADMIN_PASSWORD = if ($envMap['ADMIN_PASSWORD']) { $envMap['ADMIN_PASSWORD'] } else { 'admin123' }
$env:REDIS_URL = if ($envMap['REDIS_URL']) { $envMap['REDIS_URL'] } else { 'redis://127.0.0.1:6379/0' }
$env:APP_ENV = 'dev'

Set-Location $backend
if ($Seed) {
  Write-Host "seed..."
  & $py -m app.scripts.seed
}

if ($Mock) {
  Write-Host "启动 API 后台并跑 mock..."
  $api = Start-Process -FilePath $py -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -PassThru -WindowStyle Minimized
  try {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
      Start-Sleep -Seconds 1
      try {
        $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        if ($h.status -eq 'ok') { $ready = $true; break }
      } catch {}
    }
    if (-not $ready) { throw 'API health 超时' }
    Write-Host "health OK"
    if (-not $Seed) { & $py -m app.scripts.seed }
    $env:QINGQUAN_URL = 'http://127.0.0.1:8000'
    $env:QINGQUAN_API_KEY = $env:INGEST_DEFAULT_API_KEY
    & $py (Join-Path $root 'collectors\agent-core\mock_ingest_tiktok.py')
    Write-Host "验证完成。API 仍在运行 PID=$($api.Id)  http://127.0.0.1:8000/docs" -ForegroundColor Green
    Write-Host "停止: Stop-Process -Id $($api.Id)"
  } catch {
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    throw
  }
  return
}

Write-Host "启动 uvicorn http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "另开终端: python -m app.scripts.seed"
Write-Host "文档: http://127.0.0.1:8000/docs"
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
