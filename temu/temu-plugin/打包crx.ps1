# 一键把本插件打包成 .crx，方便发给同事。
# 用 Chrome 自带的 --pack-extension 功能：首次生成 .crx + .pem 密钥文件，
# 之后复用同一 .pem，保证每次打包出的扩展 ID 不变。
# 用法：右键“用 PowerShell 运行”，或在本文件夹执行  powershell -ExecutionPolicy Bypass -File 打包crx.ps1
$ErrorActionPreference = 'Stop'

$srcRoot = $PSScriptRoot                        # 源码目录（本脚本所在）
$parent = Split-Path $srcRoot -Parent
$name = Split-Path $srcRoot -Leaf
$crx = Join-Path $parent ($name + '.crx')  # Chrome 会把产物输出到父目录、以文件夹名命名
$pem = Join-Path $parent ($name + '.pem')  # ⚠️密钥必须放在插件文件夹【外面】，否则会被打进 .crx 泄露私钥

# 仅打运行时需要的文件。Chrome 禁止扩展目录出现以下划线 _ 开头的文件名
#（保留给系统，如 _metadata）；测试脚本、打包脚本、抓包目录也不该进包。
$runtimeFiles = @(
  'manifest.json',
  'background.js',
  'content.js',
  'content-front.js',
  'inject.js',
  'logger.js',
  'popup.html',
  'popup.js',
  'options.html',
  'options.js'
)

$stage = Join-Path $env:TEMP ('temu-plugin-pack-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
  foreach ($f in $runtimeFiles) {
    $from = Join-Path $srcRoot $f
    if (-not (Test-Path $from)) {
      Write-Host ("[错误] 缺少运行时文件: " + $f) -ForegroundColor Red
      Read-Host '回车退出'
      exit 1
    }
    Copy-Item $from (Join-Path $stage $f)
  }

  # 定位 chrome.exe
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  $chrome = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $chrome) {
    try { $chrome = (Get-Command chrome.exe -ErrorAction Stop).Source } catch {}
  }
  if (-not $chrome) { Write-Host '[错误] 找不到 chrome.exe，请确认已安装 Google Chrome。' -ForegroundColor Red; Read-Host '回车退出'; exit 1 }
  Write-Host ("Chrome: " + $chrome)
  Write-Host ("打包源(干净暂存): " + $stage)

  # 组装参数：有密钥就复用（ID 不变），没有则首次生成
  # 注意：--pack-extension 的输出 .crx/.pem 按「文件夹名」放在其父目录
  $packArgs = @("--pack-extension=$stage")
  if (Test-Path $pem) {
    $packArgs += "--pack-extension-key=$pem"
    Write-Host ("复用密钥: " + $pem)
  } else {
    Write-Host '首次打包，将生成新密钥（请妥善保存，之后更新插件要用它）。'
  }

  & $chrome @packArgs
  Start-Sleep -Seconds 2

  # 暂存目录名随机，产物在 TEMP 父级：把 .crx 挪到项目期望位置
  $stageName = Split-Path $stage -Leaf
  $stageParent = Split-Path $stage -Parent
  $tempCrx = Join-Path $stageParent ($stageName + '.crx')
  $tempPem = Join-Path $stageParent ($stageName + '.pem')

  if (Test-Path $tempCrx) {
    if (Test-Path $crx) { Remove-Item -Force $crx }
    Move-Item $tempCrx $crx
    if ((-not (Test-Path $pem)) -and (Test-Path $tempPem)) {
      Move-Item $tempPem $pem
      Write-Host ("[密钥] 已保存: " + $pem) -ForegroundColor Cyan
    } elseif (Test-Path $tempPem) {
      Remove-Item -Force $tempPem
    }
    Write-Host ''
    Write-Host ('[成功] 已生成: ' + $crx) -ForegroundColor Green
    Write-Host '把这个 .crx 发给同事即可。'
    Write-Host ''
    Write-Host '提醒：新版 Chrome 常拒装“从外部拖入的 .crx”。若对方装不上，' -ForegroundColor Yellow
    Write-Host '让他改用“加载已解压”方式（只发运行时文件，不要带 test_*.js / 打包脚本）。' -ForegroundColor Yellow
  } else {
    Write-Host '[失败] 未生成 .crx，请检查上面的 Chrome 输出。' -ForegroundColor Red
  }
} finally {
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
}
Read-Host '回车退出'
