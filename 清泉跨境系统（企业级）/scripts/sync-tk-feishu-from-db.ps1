# 本机：在「能连服务器 PG」时，用本地代码把 tk 事实同步到飞书 T1/T2
# 用法：
#   $env:DATABASE_URL = "postgresql+asyncpg://user:pass@HOST:5432/qingquan"
#   # 可选覆盖飞书（默认读仓库根 .env）
#   powershell -ExecutionPolicy Bypass -File .\scripts\sync-tk-feishu-from-db.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\sync-tk-feishu-from-db.ps1 -LookbackDays 60 -DryRun
#
# 若只有同步协议 URL：postgresql://...  脚本会改成 postgresql+asyncpg://

param(
  [int]$LookbackDays = 60,
  [int]$Limit = 2000,
  [switch]$DryRun,
  [switch]$AdsOnly,
  [switch]$ShopOnly
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { throw "missing venv $Py" }

if (-not $env:DATABASE_URL) {
  throw "Set DATABASE_URL to server DB first, e.g. postgresql+asyncpg://qingquan:***@127.0.0.1:5432/qingquan (via SSH tunnel)"
}
# normalize scheme
if ($env:DATABASE_URL -match '^postgresql://') {
  $env:DATABASE_URL = $env:DATABASE_URL -replace '^postgresql://', 'postgresql+asyncpg://'
}

# Feishu mapping: prefer already-set env; else load 清泉 Base IDs from repo root .env
# (Do NOT hardcode old 金猫 Base — 2026-08-10 cutover to LzTAbQs…)
function Import-DotEnvKeys([string]$path, [string[]]$keys) {
  if (-not (Test-Path -LiteralPath $path)) { return }
  Get-Content -LiteralPath $path -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    if ($_ -match '^\s*([^=]+)=(.*)$') {
      $k = $Matches[1].Trim()
      $v = $Matches[2].Trim().Trim('"').Trim("'")
      if ($keys -contains $k) {
        $existing = [Environment]::GetEnvironmentVariable($k, 'Process')
        if ([string]::IsNullOrWhiteSpace($existing)) {
          Set-Item -Path "Env:$k" -Value $v
        }
      }
    }
  }
}
Import-DotEnvKeys (Join-Path $Root '.env') @(
  'FEISHU_APP_ID',
  'FEISHU_APP_SECRET',
  'FEISHU_BITABLE_APP_TOKEN',
  'FEISHU_BITABLE_APP_TOKEN_TK',
  'FEISHU_BITABLE_TABLE_TK_SHOP_DAILY',
  'FEISHU_BITABLE_TABLE_TK_ADS_CAMPAIGN',
  'FEISHU_BITABLE_TABLE_TK_ANOMALY_TASK',
  'FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY',
  'FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY',
  'FEISHU_TK_STORE_TABLES_JSON'
)
if (-not $env:FEISHU_BITABLE_APP_TOKEN_TK -and -not $env:FEISHU_BITABLE_APP_TOKEN) {
  throw 'FEISHU_BITABLE_APP_TOKEN_TK / FEISHU_BITABLE_APP_TOKEN missing (set env or repo .env)'
}

$keys = @('tk_ads_campaign', 'tk_shop_daily')
if ($AdsOnly) { $keys = @('tk_ads_campaign') }
if ($ShopOnly) { $keys = @('tk_shop_daily') }

$dry = if ($DryRun) { 'True' } else { 'False' }
$keysPy = ($keys | ForEach-Object { "'$_'" }) -join ', '

$script = @"
import asyncio, logging, sys
from pathlib import Path
sys.path.insert(0, r'$($Root -replace '\\','\\')\backend')
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

from app.config import get_settings
get_settings.cache_clear()
s = get_settings()
print('db', s.database_url.split('@')[-1] if '@' in s.database_url else s.database_url)
print('feishu_app', bool(s.feishu_app_id))
print('t1', s.feishu_bitable_table_tk_shop_daily)
print('t2', s.feishu_bitable_table_tk_ads_campaign)

KEYS = [$keysPy]
LOOKBACK = $LookbackDays
LIMIT = $Limit
DRY = $dry

async def main():
    from app.infra.db import SessionLocal
    from app.jobs.tk_feishu_sync import sync_table
    rc = 0
    async with SessionLocal() as db:
        for key in KEYS:
            print('---', key)
            try:
                stats = await sync_table(
                    db, table_key=key, mode='incremental',
                    lookback_days=LOOKBACK, limit=LIMIT, dry_run=DRY,
                )
                print('OK', stats)
                if stats.get('status') not in ('success', 'skipped', 'dry_run') or stats.get('failed'):
                    rc = 1
            except Exception as e:
                logging.exception('fail %s', key)
                print('ERR', key, e)
                rc = 1
    return rc

sys.exit(asyncio.run(main()))
"@

$tmp = Join-Path $env:TEMP ("tk-sync-db-" + [guid]::NewGuid().ToString('N') + '.py')
[System.IO.File]::WriteAllText($tmp, $script, [System.Text.UTF8Encoding]::new($false))
try {
  & $Py $tmp
  exit $LASTEXITCODE
} finally {
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}
