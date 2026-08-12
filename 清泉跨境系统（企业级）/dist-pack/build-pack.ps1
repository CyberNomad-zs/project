# Build TK collector zip WITH secrets (stores.config.json + .env)
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path (Join-Path $root 'collectors\tiktok-ads'))) {
  throw "collectors/tiktok-ads not found under $root"
}
$outDir = Join-Path $root 'dist-pack'
$zipPath = Join-Path $outDir "TK-数据采集脚本-$stamp.zip"
$stage = Join-Path $outDir "_stage-$stamp"

Write-Host "root=$root"
Write-Host "stage=$stage"
Write-Host "zip=$zipPath"

if (Test-Path -LiteralPath $stage) {
  cmd.exe /c "rd /s /q `"$stage`""
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$src = Join-Path $root 'collectors\tiktok-ads'
$dst = Join-Path $stage 'collectors\tiktok-ads'
New-Item -ItemType Directory -Force -Path $dst | Out-Null

# robocopy: exit codes 0-7 are success
$rcArgs = @(
  $src, $dst, '/E',
  '/XD', 'logs', '__pycache__', '_extract', '.git', 'node_modules', '.playwright-mcp', '日报',
  '/XF', '*.log', '*.pyc', '*.pyo',
  '/NFL', '/NDL', '/NJH', '/NJS', '/nc', '/ns', '/np'
)
& robocopy.exe @rcArgs
$rc = $LASTEXITCODE
Write-Host "robocopy exit=$rc"
if ($rc -ge 8) { throw "robocopy failed: $rc" }

New-Item -ItemType Directory -Force -Path (Join-Path $dst 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dst '日报') | Out-Null
Set-Content -LiteralPath (Join-Path $dst 'logs\.gitkeep') -Value '' -Encoding utf8
Set-Content -LiteralPath (Join-Path $dst '日报\.gitkeep') -Value '' -Encoding utf8

$rs = Join-Path $stage 'scripts'
New-Item -ItemType Directory -Force -Path $rs | Out-Null
foreach ($f in @(
  'tk-p0-post-collect.ps1',
  'feishu-tk-daily-sync.ps1',
  'feishu_tk_daily_sync.py',
  'install-tk-p0-post-collect-daily-task.ps1',
  'sync-tk-feishu-from-db.ps1'
)) {
  $p = Join-Path $root "scripts\$f"
  if (Test-Path -LiteralPath $p) {
    Copy-Item -LiteralPath $p -Destination (Join-Path $rs $f) -Force
  }
}

# Feishu store-table map / migration note (post-collect reads FEISHU_TK_STORE_TABLES_JSON)
$packConfigDir = Join-Path $stage 'config'
if (-not (Test-Path -LiteralPath $packConfigDir)) {
  New-Item -ItemType Directory -Force -Path $packConfigDir | Out-Null
}
foreach ($f in @(
  'feishu-tk-store-tables.json',
  'feishu-tk-migration-map.json'
)) {
  $p = Join-Path $root "config\$f"
  if (Test-Path -LiteralPath $p) {
    Copy-Item -LiteralPath $p -Destination (Join-Path $packConfigDir $f) -Force
  }
}

$envFile = Join-Path $root '.env'
if (Test-Path -LiteralPath $envFile) {
  Copy-Item -LiteralPath $envFile -Destination (Join-Path $stage '.env') -Force
}

$readme = @"
# TK 数据采集脚本包（含密钥）

打包时间: $stamp
本包含 stores.config.json / .env 等敏感信息，仅内网分发，勿上传公网/勿进公开 Git。

## 目录
- collectors/tiktok-ads/  采集主目录（启动器、scripts、config、docs）
- scripts/               规则+飞书 post-collect / 同步
- config/                飞书分店表映射（清泉 Base）
- .env                   中心 PG / 飞书环境变量（若有）

## 飞书（2026-08-10 起 · 清泉组织）
- Base: LzTAbQsThaPOzis2lFvciDMlnyh
- 广告直写: TK广告日报 tblRI8j92JuAtVDx（stores.config.json）
- PG同步: T1/T2/异常/T6/T7 + 分店表（.env + config/feishu-tk-store-tables.json）
- 旧金猫 Base 保留不删，脚本已不再写入

## 使用
1. 解压到目标机固定目录
2. 双击 collectors\tiktok-ads\美化启动器.bat
3. 交接说明: collectors\tiktok-ads\docs\运营交接一页纸.md
4. 装夜间任务: 启动器 -> 安装夜间拆分任务包
5. 中心机规则飞书需要 scripts\ + .env + config\（或目标机已有同等环境变量）

## 注意
- 紫鸟须本机已装并登录
- 广告 17:20 默认在同事机
- 若目标机已有自己的 .env / stores.config.json，解压前先备份

## 未包含
- logs 历史日志
- __pycache__ / _extract
- 完整 backend / web
"@
Set-Content -LiteralPath (Join-Path $stage 'README-打包说明.txt') -Value $readme -Encoding UTF8

$files = Get-ChildItem -LiteralPath $stage -Recurse -File
Write-Host ("staged files={0} sizeMB={1:N2}" -f $files.Count, (($files | Measure-Object Length -Sum).Sum / 1MB))
Write-Host ("stores.config=" + (Test-Path -LiteralPath (Join-Path $dst 'config\stores.config.json')))
Write-Host (".env=" + (Test-Path -LiteralPath (Join-Path $stage '.env')))
Write-Host ("store-tables=" + (Test-Path -LiteralPath (Join-Path $packConfigDir 'feishu-tk-store-tables.json')))

if (Test-Path -LiteralPath $zipPath) {
  cmd.exe /c "del /f /q `"$zipPath`""
}

Push-Location $stage
try {
  # 必须用 Windows 自带 bsdtar；Git Bash 的 GNU tar 会把 E:\ 当远程主机
  & "$env:SystemRoot\System32\tar.exe" -a -cf $zipPath *
  if ($LASTEXITCODE -ne 0) { throw "tar failed: $LASTEXITCODE" }
} finally {
  Pop-Location
}

if (-not (Test-Path -LiteralPath $zipPath)) { throw "zip not created" }

$sizeMb = (Get-Item -LiteralPath $zipPath).Length / 1MB
Write-Host ("ZIP sizeMB={0:N2}" -f $sizeMb)
Write-Host "ZIP=$zipPath"
Write-Host '--- verify ---'
& "$env:SystemRoot\System32\tar.exe" -tf $zipPath | Select-String -Pattern 'stores\.config\.json$|\.env$|gui\.py$|feishu-tk-store|tk-p0-post|tblRI8j|LzTAbQ|README'

cmd.exe /c "rd /s /q `"$stage`""
Write-Host 'DONE'
