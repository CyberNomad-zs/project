$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
. ".\scripts\qingquan-client.ps1"
$dbgPath = ".\logs\scrape-debug-last.json"
if (-not (Test-Path $dbgPath)) { throw "missing $dbgPath — run multi-store first" }
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $dbgPath))
if ($bytes.Length -ge 3 -and $bytes[0]-eq 0xEF -and $bytes[1]-eq 0xBB -and $bytes[2]-eq 0xBF) {
  $raw = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length-3)
} else {
  $raw = [System.Text.Encoding]::UTF8.GetString($bytes)
}
$d = $raw | ConvertFrom-Json
$pay = $d.payload
if (-not $pay -or -not $pay.rows) { throw "debug payload has no rows" }

$bizDate = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
if ($d.bizDate) { $bizDate = [string]$d.bizDate }

$rows = @()
foreach ($r in @($pay.rows)) {
  $rows += [pscustomobject]@{
    date = $bizDate
    store = [string]$d.displayName
    storeId = [string]$d.storeId
    campaign = [string]$r.campaign
    spend = $r.spend
    orders = $r.orders
    roi = $r.roi
    revenue = $r.revenue
    dailyBudget = $r.dailyBudget
    targetRoi = $r.targetRoi
    netCost = $r.netCost
    avgOrderCost = $r.avgOrderCost
    deliveryStatus = [string]$r.deliveryStatus
    planStatus = [string]$r.planStatus
    currency = "USD"
    sourceUrl = [string]$pay.url
    status = "success"
  }
}

# 优先读本机 stores.config.json（生产 baseUrl + 正确 apiKey）
$cfgPath = ".\config\stores.config.json"
if (-not (Test-Path $cfgPath)) { throw "missing $cfgPath" }
$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $cfg.qingquan) { throw "qingquan block missing in config" }

$items = ConvertTo-QingquanIngestItems -Rows $rows -CollectedAt ((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss+00:00")) -Currency "USD"
Write-Host ("items={0} store={1} bizDate={2} baseUrl={3}" -f $items.Count, $d.storeId, $bizDate, $cfg.qingquan.baseUrl)
$r = Send-QingquanIngest -Config $cfg -Items $items
Write-Host ("ok={0} accepted={1} dup={2} failed={3} http={4}" -f $r.ok, $r.accepted, $r.duplicated, $r.failed, $r.httpCode)
if ($r.error) { Write-Host "err=$($r.error)" }
if ($r.resp) { $r.resp | ConvertTo-Json -Compress -Depth 4 }
