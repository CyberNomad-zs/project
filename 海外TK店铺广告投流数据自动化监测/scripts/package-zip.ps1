# 打包卖家自研插件 ZIP（根目录含 manifest.json）
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$ext = Join-Path $root 'extension'
$outDir = Join-Path $root 'dist'
$manifest = Join-Path $ext 'manifest.json'

if (-not (Test-Path $manifest)) {
  throw "找不到 manifest.json: $manifest"
}

$ver = '1.0.0'
try {
  $raw = Get-Content $manifest -Raw -Encoding UTF8
  $ver = ($raw | ConvertFrom-Json).version
} catch {
  # fallback: regex
  if ($raw -match '"version"\s*:\s*"([^"]+)"') { $ver = $Matches[1] }
}
if (-not $ver) { $ver = '1.0.0' }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$zipName = "tk-ad-scraper-v$ver.zip"
$zipPath = Join-Path $outDir $zipName

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

# Compress-Archive 会把路径层级压进 zip；先复制到临时根再压
$tmp = Join-Path $env:TEMP "tk-ad-pack-$(Get-Random)"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  Copy-Item -Path (Join-Path $ext '*') -Destination $tmp -Recurse -Force
  Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $zipPath -Force
  Write-Host "OK: $zipPath"
  Write-Host "上传到紫鸟开放平台 → 卖家自研插件 → 版本管理"
}
finally {
  Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
