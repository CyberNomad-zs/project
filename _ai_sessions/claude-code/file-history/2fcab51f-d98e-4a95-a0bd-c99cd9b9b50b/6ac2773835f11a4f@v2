# Pack a minimal Sellfox-only tarball for Linux upload (no Playwright / no secrets).
# Run on Windows from anywhere:
#   powershell -NoProfile -ExecutionPolicy Bypass -File temu-monitor\deploy\pack-sellfox.ps1
$ErrorActionPreference = 'Stop'

# deploy/ → temu-monitor/ → repo root (for _dist output)
$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repo = Split-Path $src -Parent
if (-not (Test-Path (Join-Path $src 'src\sellfox\cli.js'))) {
  throw "Cannot find src/sellfox under $src"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$distParent = Join-Path $repo '_dist'
$outDir = Join-Path $distParent ("sellfox-linux-" + $stamp)
$zipPath = Join-Path $distParent ("temu-sellfox-linux-" + $stamp + ".zip")

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'src\sellfox') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'deploy') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'logs') | Out-Null

# Minimal runtime files (Sellfox = pure Node, no playwright)
$files = @(
  'package.json',
  'SELLFOX.md',
  'sellfox.config.example.json',
  'src\config.js',
  'src\logger.js',
  'src\feishu.js',
  'src\sellfox\cli.js',
  'src\sellfox\client.js',
  'src\sellfox\config.js',
  'src\sellfox\diff.js',
  'src\sellfox\monitor.js',
  'src\sellfox\products.js',
  'deploy\sellfox.service',
  'deploy\install-sellfox-linux.sh',
  'deploy\pack-sellfox.ps1',
  'deploy\README-SERVER.md'
)

foreach ($rel in $files) {
  $from = Join-Path $src $rel
  if (-not (Test-Path $from)) {
    Write-Warning "skip missing: $rel"
    continue
  }
  $to = Join-Path $outDir $rel
  $toParent = Split-Path $to -Parent
  if (-not (Test-Path $toParent)) { New-Item -ItemType Directory -Force -Path $toParent | Out-Null }
  Copy-Item -LiteralPath $from -Destination $to -Force
}

# Lean package.json: no playwright on server
# (write manually — ConvertTo-Json may mangle empty dependencies)
$pkgText = @'
{
  "name": "temu-sellfox-monitor",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "description": "Temu delist monitor via Sellfox OpenAPI (server, no browser)",
  "engines": { "node": ">=18" },
  "scripts": {
    "sellfox:init": "node src/sellfox/cli.js init",
    "sellfox:probe": "node src/sellfox/cli.js probe",
    "sellfox:once": "node src/sellfox/cli.js once",
    "sellfox:start": "node src/sellfox/cli.js start",
    "sellfox:dry": "node src/sellfox/cli.js dry",
    "start": "node src/sellfox/cli.js start",
    "once": "node src/sellfox/cli.js once",
    "probe": "node src/sellfox/cli.js probe"
  },
  "dependencies": {}
}
'@
Set-Content -Path (Join-Path $outDir 'package.json') -Value $pkgText -Encoding utf8

# Placeholder so empty dirs survive some zip tools
Set-Content -Path (Join-Path $outDir 'data\.gitkeep') -Value '' -Encoding utf8
Set-Content -Path (Join-Path $outDir 'logs\.gitkeep') -Value '' -Encoding utf8

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
New-Item -ItemType Directory -Force -Path (Split-Path $zipPath -Parent) | Out-Null
Compress-Archive -Path (Join-Path $outDir '*') -DestinationPath $zipPath -Force

Write-Host ''
Write-Host ('  [OK] Packed: ' + $zipPath)
Write-Host ('  Dir:  ' + $outDir)
Write-Host '  Upload zip to server, unzip, then:'
Write-Host '    sudo bash deploy/install-sellfox-linux.sh'
Write-Host '  Do NOT put sellfox.config.json inside the zip (secrets).'
Write-Host '  Copy config separately: scp sellfox.config.json user@server:/opt/temu-monitor/'
Write-Host ''
