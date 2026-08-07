# Pack local Playwright traffic package — MAINTAINER / EMERGENCY ONLY (2026-07-31).
# Daily traffic for colleagues = Chrome extension temu-plugin (v14+), NOT this zip.
# Delist/onshelf = server temu-sellfox only.
# Do NOT hand this zip to colleagues as the default workflow (dual Feishu + .userdata pain).
# Run:
#   powershell -NoProfile -ExecutionPolicy Bypass -File temu-monitor\deploy\pack-traffic-local.ps1
$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '  !! WARNING: traffic-local pack is EMERGENCY/MAINTAINER only.'
Write-Host '  !! Colleagues should use temu-plugin v14 (traffic) + server sellfox (delist).'
Write-Host ''

$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repo = Split-Path $src -Parent
if (-not (Test-Path (Join-Path $src 'src\cli.js'))) {
  throw "Cannot find src/cli.js under $src"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$distParent = Join-Path $repo '_dist'
$outName = "temu-traffic-local-$stamp"
$outDir = Join-Path $distParent $outName
$zipPath = Join-Path $distParent ("$outName.zip")

if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'src') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'deploy') | Out-Null

# Private / heavy — never pack (API keys only; team shares config.json feishu+stores)
$excludeNames = [System.Collections.Generic.HashSet[string]]::new(
  [string[]]@(
    'node_modules', '.userdata', 'logs', 'data', 'capture', '__pycache__',
    'sellfox.config.json', 'openapi.config.json',
    '.git'
  )
)

# Top-level: whitelist by English name + pattern for Chinese twin files
# (avoid hardcoding Chinese in .ps1 — PS5.1 encoding often mangles non-ASCII literals)
# config.json 打进包：团队共用飞书 webhook + storeList，同事免再填
$topExact = @(
  'package.json',
  'package-lock.json',
  '.gitignore',
  'config.json',
  'config.example.json',
  'sellfox.config.example.json',
  'openapi.config.example.json',
  'README.md',
  'PLUGIN_PARITY.md',
  'SELLFOX.md',
  'OPENAPI.md',
  'usage.txt',
  'first-run.bat',
  'start-menu.bat',
  'launch-gui.bat',
  'gui.py',
  'run-forever.ps1',
  'install-autostart.ps1',
  'uninstall-autostart.ps1'
)

$copied = 0
foreach ($rel in $topExact) {
  $from = Join-Path $src $rel
  if (-not (Test-Path -LiteralPath $from)) {
    Write-Warning "skip missing: $rel"
    continue
  }
  Copy-Item -LiteralPath $from -Destination (Join-Path $outDir $rel) -Force
  $copied++
}

# Chinese-named twins (使用说明 / 首次运行 / 启动 / 美化启动器) — pick by extension + exclude already-copied English names
$englishBat = [System.Collections.Generic.HashSet[string]]::new(
  [string[]]@('first-run.bat', 'start-menu.bat', 'launch-gui.bat')
)
Get-ChildItem -LiteralPath $src -File | ForEach-Object {
  $n = $_.Name
  $take = $false
  if ($n -like '*.txt' -and $n -ne 'usage.txt' -and $n -notlike '*probe*' -and $n -notlike '*calibrat*') { $take = $true }
  if ($n -like '*.bat' -and -not $englishBat.Contains($n)) { $take = $true }
  if (-not $take) { return }
  if ($excludeNames.Contains($n)) { return }
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $outDir $n) -Force
  $copied++
  Write-Host ("  + extra: " + $n)
}

# Full src/ tree (browser + sellfox code; secrets not in src)
$srcRoot = Join-Path $src 'src'
Get-ChildItem -LiteralPath $srcRoot -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($srcRoot.Length).TrimStart('\', '/')
  $to = Join-Path (Join-Path $outDir 'src') $rel
  $parent = Split-Path $to -Parent
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  Copy-Item -LiteralPath $_.FullName -Destination $to -Force
  $copied++
}

# Pack script itself + short server note (optional reference, not required for local)
foreach ($rel in @('deploy\pack-traffic-local.ps1', 'deploy\pack-sellfox.ps1', 'deploy\README-SERVER.md')) {
  $from = Join-Path $src $rel
  if (Test-Path -LiteralPath $from) {
    $to = Join-Path $outDir $rel
    $parent = Split-Path $to -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Copy-Item -LiteralPath $from -Destination $to -Force
    $copied++
  }
}

# Empty dirs
Set-Content -Path (Join-Path $outDir 'data\.gitkeep') -Value '' -Encoding utf8
Set-Content -Path (Join-Path $outDir 'logs\.gitkeep') -Value '' -Encoding utf8

# Safety: refuse API keys / login state / node_modules (config.json is allowed)
$forbidden = @(
  'sellfox.config.json',
  'openapi.config.json',
  '.userdata',
  'node_modules'
)
foreach ($f in $forbidden) {
  $p = Join-Path $outDir $f
  if (Test-Path $p) {
    throw "Refusing to pack secret/private path present in staging: $f"
  }
}

# Extra scan: only sellfox/openapi real configs are forbidden
$badHits = Get-ChildItem -LiteralPath $outDir -Recurse -File |
  Where-Object { $_.Name -match '^(sellfox\.config|openapi\.config)\.json$' -and $_.Name -notmatch 'example' }
if ($badHits) {
  throw ("Refusing: found API key config files: " + ($badHits.FullName -join ', '))
}
if (-not (Test-Path (Join-Path $outDir 'config.json'))) {
  Write-Warning 'config.json missing in source — colleagues must copy from config.example.json'
}

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
New-Item -ItemType Directory -Force -Path $distParent | Out-Null
# Zip contents of outDir as a single root folder (colleague unzips → one folder)
$stageRoot = Join-Path $distParent ("_zipstage-$stamp")
if (Test-Path $stageRoot) { Remove-Item $stageRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
$zipInner = Join-Path $stageRoot 'temu-monitor'
New-Item -ItemType Directory -Force -Path $zipInner | Out-Null
Copy-Item -Path (Join-Path $outDir '*') -Destination $zipInner -Recurse -Force
Compress-Archive -Path (Join-Path $stageRoot 'temu-monitor') -DestinationPath $zipPath -Force
Remove-Item $stageRoot -Recurse -Force

$sizeKB = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
Write-Host ''
Write-Host ('  [OK] Packed: ' + $zipPath)
Write-Host ('  Size: ' + $sizeKB + ' KB  files~' + $copied)
Write-Host ('  Staging dir kept: ' + $outDir)
Write-Host ''
Write-Host '  EMERGENCY use only. Prefer temu-plugin for daily traffic.'
Write-Host '  If you must use this zip:'
Write-Host '    1. Unzip  2. first-run.bat  3. Login  4. once (do NOT dual-run with plugin)'
Write-Host ''
Write-Host '  NOT included: .userdata  data/  logs/  node_modules/  sellfox secrets'
Write-Host ''
