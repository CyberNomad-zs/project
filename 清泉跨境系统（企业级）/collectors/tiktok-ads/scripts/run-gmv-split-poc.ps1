# P0.7 渠道 GMV 拆解 POC - 完整开发
# 功能：抓取店铺数据分析页 GMV 拆解（直播/视频/商品卡占比）

param(
  [string]$StoreId = "",
  [string]$ConfigPath = "",
  [switch]$ListOnly,
  [string]$DryRun = "",
  [string]$DateMode = "",
  [string]$Modules = "gmv_split",
  [switch]$SkipIngest = $true
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }

. (Join-Path $PSScriptRoot 'ziniao-window.ps1')
. (Join-Path $PSScriptRoot 'qingquan-client.ps1')

$script:logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $script:logsDir | Out-Null
$script:runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:runLogFile = Join-Path $script:logsDir ("gmv-split-poc-run-{0}.log" -f $script:runStamp)

function Write-RunLog([string]$msg) { Add-Content -LiteralPath $script:runLogFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" -Encoding UTF8 }
function Write-Step([string]$msg) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg); Write-RunLog $msg }

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$stores = @()
if ($StoreId) { $stores = @([pscustomobject]@{storeId = $StoreId}) } else {
  $listOut = Invoke-Ziniao @('store', 'list')
  $storesObj = $listOut | ConvertFrom-Json
  $stores = $storesObj.data.items | ForEach-Object { [pscustomobject]@{storeId = $_.storeId; storeName = $_.storeName} }
}

if ($ListOnly) { return $stores }

$dryParsed = Convert-DryRunFlag $DryRun
$useDryRun = if ($null -ne $dryParsed) { $dryParsed } else { $true }

Write-Step '===== P0.7 渠道 GMV 拆解 POC START ====='

$scriptMap = @{
  gmv_split = (Join-Path $PSScriptRoot 'scrape-gmv-split-page.js')
}

foreach ($store in $stores) {
  $sid = $store.storeId
  Write-Step "==== STORE $sid ($($store.storeName)) ===="

  $url = "https://seller-uk.tiktok.com/compass/shop-data-analysis?shop_region=GB"
  $openArgs = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $url -Config $cfg
  Invoke-Ziniao $openArgs | Out-Null
  Start-Sleep -Milliseconds 28000

  $oneLiner = ConvertTo-ScrapeOneLine (Get-Content $scriptMap.gmv_split -Raw -Encoding UTF8)
  $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $oneLiner)
  $payload = Get-ScrapePayload $execOut

  $dbg = Join-Path $script:logsDir ("gmv-split-debug-{0}-{1}.json" -f $sid, $script:runStamp)
  $dbgObj = @{
    storeId = $sid
    storeName = $store.storeName
    url = $url
    module = 'gmv_split'
    scrapeOk = [bool]($payload -and $payload.ok)
    payload = $payload
  }
  $dbgObj | ConvertTo-Json -Depth 8 | Out-File -FilePath $dbg -Encoding utf8

  if ($payload -and $payload.ok) {
    Write-Step "GMV 拆解抓取成功"
  } else {
    Write-Step "GMV 拆解抓取失败: $($payload.error)"
  }
}

Write-Step '===== P0.7 渠道 GMV 拆解 POC END ====='