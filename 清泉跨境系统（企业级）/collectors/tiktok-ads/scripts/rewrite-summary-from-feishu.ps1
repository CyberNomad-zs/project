# Rewrite Feishu summary rows only (no scrape, no campaign re-write).
# Reads existing campaign detail rows for a bizDate from the ads daily table,
# rebuilds analysis with daily-analysis.ps1, optionally deletes old summary rows,
# then appends fresh 【店铺汇总】/【全店汇总】/【日报分析】.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\rewrite-summary-from-feishu.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\rewrite-summary-from-feishu.ps1 -BizDate 2026-08-11
#   powershell -ExecutionPolicy Bypass -File .\scripts\rewrite-summary-from-feishu.ps1 -BizDate 2026-08-11 -DryRun true
#   powershell -ExecutionPolicy Bypass -File .\scripts\rewrite-summary-from-feishu.ps1 -BizDate 2026-08-11 -DeleteOldSummary false
#
# Default bizDate = yesterday (same as ads daily).

param(
  [string]$ConfigPath = "",
  [string]$BizDate = "",
  [string]$DryRun = "false",
  [string]$DeleteOldSummary = "true"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }

$analysisLib = Join-Path $PSScriptRoot 'daily-analysis.ps1'
if (-not (Test-Path $analysisLib)) { throw "Missing $analysisLib" }
. $analysisLib

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $cfg.feishu) { throw "config.feishu missing" }

function Convert-Flag([string]$raw, [bool]$default) {
  if ($null -eq $raw -or $raw.Trim() -eq '') { return $default }
  switch -Regex ($raw.Trim().ToLowerInvariant()) {
    '^(1|true|yes|y|on)$' { return $true }
    '^(0|false|no|n|off)$' { return $false }
    default { return $default }
  }
}

function Write-Step([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Write-Host $line
}

function Get-BizDateDefault {
  return (Get-Date).Date.AddDays(-1).ToString('yyyy-MM-dd')
}

function Get-FeishuToken($appId, $appSecret) {
  $body = @{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json
  $r = Invoke-RestMethod -Method POST -Uri 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' `
    -ContentType 'application/json; charset=utf-8' -Body $body
  if ($r.code -ne 0) { throw "Feishu token failed: $($r.msg)" }
  return $r.tenant_access_token
}

function Get-FieldText($v) {
  if ($null -eq $v) { return '' }
  if ($v -is [string]) { return $v }
  if ($v -is [ValueType]) { return [string]$v }
  # text segments: [{ text, type }]
  if ($v -is [System.Collections.IEnumerable] -and -not ($v -is [string])) {
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($seg in $v) {
      if ($null -eq $seg) { continue }
      if ($seg -is [string]) { [void]$parts.Add($seg); continue }
      if ($seg.PSObject.Properties['text']) { [void]$parts.Add([string]$seg.text); continue }
      if ($seg.PSObject.Properties['name']) { [void]$parts.Add([string]$seg.name); continue }
    }
    return ($parts -join '')
  }
  if ($v.PSObject.Properties['text']) { return [string]$v.text }
  return [string]$v
}

function Get-FieldNumber($v) {
  if ($null -eq $v -or $v -eq '') { return 0.0 }
  try { return [double]$v } catch { return 0.0 }
}

function Convert-DateFieldToYmd($v) {
  if ($null -eq $v -or $v -eq '') { return '' }
  # ms timestamp
  try {
    $n = [double]$v
    if ($n -gt 1e11) {
      return [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$n).ToLocalTime().ToString('yyyy-MM-dd')
    }
    if ($n -gt 1e9) {
      return [DateTimeOffset]::FromUnixTimeSeconds([int64]$n).ToLocalTime().ToString('yyyy-MM-dd')
    }
  } catch {}
  $s = Get-FieldText $v
  if ($s -match '(\d{4})[/-](\d{1,2})[/-](\d{1,2})') {
    return ('{0:D4}-{1:D2}-{2:D2}' -f [int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
  }
  return $s
}

function Get-FeishuFieldMap($token, $feishu) {
  $fieldsUrl = "https://open.feishu.cn/open-apis/bitable/v1/apps/$($feishu.appToken)/tables/$($feishu.tableId)/fields?page_size=100"
  $fieldList = Invoke-RestMethod -Method GET -Uri $fieldsUrl -Headers @{ Authorization = "Bearer $token" }
  if ($fieldList.code -ne 0) { throw "list fields failed: $($fieldList.msg)" }
  $names = @($fieldList.data.items | ForEach-Object { $_.field_name })
  function Pick-Name([string[]]$aliases) {
    foreach ($a in $aliases) { if ($names -contains $a) { return $a } }
    return $null
  }
  $utf8 = [System.Text.Encoding]::UTF8
  $fn = @{
    date     = Pick-Name @($utf8.GetString([byte[]](0xE6,0x97,0xA5,0xE6,0x9C,0x9F)))
    store    = Pick-Name @($utf8.GetString([byte[]](0xE5,0xBA,0x97,0xE9,0x93,0xBA)))
    storeId  = Pick-Name @($utf8.GetString([byte[]](0xE5,0xBA,0x97,0xE9,0x93,0xBA,0x49,0x44)))
    campaign = Pick-Name @(
      $utf8.GetString([byte[]](0xE5,0x93,0x81,0xE5,0x90,0x8D)),
      $utf8.GetString([byte[]](0xE5,0xB9,0xBF,0xE5,0x91,0x8A,0xE7,0xB3,0xBB,0xE5,0x88,0x97,0xE5,0x90,0x8D,0xE7,0xA7,0xB0))
    )
    spend    = Pick-Name @(
      $utf8.GetString([byte[]](0xE5,0xB9,0xBF,0xE5,0x91,0x8A,0xE8,0x8A,0xB1,0xE8,0xB4,0xB9)),
      $utf8.GetString([byte[]](0xE6,0x88,0x90,0xE6,0x9C,0xAC))
    )
    orders   = Pick-Name @($utf8.GetString([byte[]](0xE9,0x94,0x80,0xE9,0x87,0x8F)))
    roi      = Pick-Name @('ROI')
    revenue  = Pick-Name @(
      $utf8.GetString([byte[]](0xE9,0x94,0x80,0xE5,0x94,0xAE,0xE9,0xA2,0x9D)),
      $utf8.GetString([byte[]](0xE6,0x80,0xBB,0xE6,0x94,0xB6,0xE5,0x85,0xA5))
    )
  }
  if (-not $fn.date -or -not $fn.store -or -not $fn.campaign) {
    throw ("Feishu fields incomplete. Have: {0}" -f ($names -join ', '))
  }
  return $fn
}

function Get-AllFeishuRecords($token, $feishu) {
  $items = @()
  $pageToken = $null
  do {
    $url = "https://open.feishu.cn/open-apis/bitable/v1/apps/$($feishu.appToken)/tables/$($feishu.tableId)/records?page_size=500"
    if ($pageToken) { $url += ("&page_token={0}" -f [uri]::EscapeDataString($pageToken)) }
    $resp = Invoke-RestMethod -Method GET -Uri $url -Headers @{ Authorization = "Bearer $token" }
    if ($resp.code -ne 0) { throw "list records failed: $($resp.msg)" }
    $batch = @($resp.data.items)
    if ($batch.Count -gt 0) { $items += $batch }
    $hasMore = [bool]$resp.data.has_more
    $pageToken = $resp.data.page_token
  } while ($hasMore -and $pageToken)
  return ,$items
}

function Get-SummaryLabelPrefixes {
  # byte-built UTF-8 so file encoding never breaks matching
  # prefixes: full-store rollup / store rollup / daily analysis (with leading U+3010)
  $u = [System.Text.Encoding]::UTF8
  return @(
    $u.GetString([byte[]](0xE3,0x80,0x90,0xE5,0x85,0xA8,0xE5,0xBA,0x97,0xE6,0xB1,0x87,0xE6,0x80,0xBB)),
    $u.GetString([byte[]](0xE3,0x80,0x90,0xE5,0xBA,0x97,0xE9,0x93,0xBA,0xE6,0xB1,0x87,0xE6,0x80,0xBB)),
    $u.GetString([byte[]](0xE3,0x80,0x90,0xE6,0x97,0xA5,0xE6,0x8A,0xA5,0xE5,0x88,0x86,0xE6,0x9E,0x90))
  )
}

function Test-IsSummaryCampaign([string]$campaign) {
  if ([string]::IsNullOrWhiteSpace($campaign)) { return $false }
  $c = $campaign.Trim()
  foreach ($p in (Get-SummaryLabelPrefixes)) {
    if ($c.StartsWith($p)) { return $true }
  }
  return $false
}

function Write-Utf8File([string]$path, [string]$text) {
  $enc = New-Object System.Text.UTF8Encoding $true
  [System.IO.File]::WriteAllText($path, $text, $enc)
}

function Write-FeishuRowsLocal($token, $feishu, $fn, $rows, [bool]$dryRun) {
  if ($dryRun) {
    Write-Step ("  [dry-run] would write {0} summary rows" -f $rows.Count)
    return @{ written = 0; dryRun = $true }
  }
  if ($rows.Count -eq 0) { return @{ written = 0; dryRun = $false } }
  $url = "https://open.feishu.cn/open-apis/bitable/v1/apps/$($feishu.appToken)/tables/$($feishu.tableId)/records/batch_create"
  $records = @()
  foreach ($row in $rows) {
    $fields = @{}
    if ($fn.date) {
      $dt = [DateTime]::ParseExact($row.date, 'yyyy-MM-dd', $null)
      $fields[$fn.date] = [DateTimeOffset]::new($dt).ToUnixTimeMilliseconds()
    }
    if ($fn.store) { $fields[$fn.store] = $row.store }
    if ($fn.storeId -and $row.storeId) { $fields[$fn.storeId] = $row.storeId }
    if ($fn.campaign) { $fields[$fn.campaign] = $row.campaign }
    if ($fn.spend) { $fields[$fn.spend] = [double]$row.spend }
    if ($fn.orders) { $fields[$fn.orders] = [double]$row.orders }
    if ($fn.roi) { $fields[$fn.roi] = [double]$row.roi }
    if ($fn.revenue) { $fields[$fn.revenue] = [double]$row.revenue }
    $records += @{ fields = $fields }
  }
  # batch_create max 500; summary is tiny
  $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes((@{ records = $records } | ConvertTo-Json -Depth 8 -Compress))
  $resp = Invoke-RestMethod -Method POST -Uri $url -Headers @{ Authorization = "Bearer $token" } `
    -ContentType 'application/json; charset=utf-8' -Body $bodyBytes
  if ($resp.code -ne 0) { throw ("Feishu write failed: code={0} msg={1}" -f $resp.code, $resp.msg) }
  return @{ written = $records.Count; dryRun = $false }
}

function Remove-FeishuRecords($token, $feishu, [string[]]$recordIds, [bool]$dryRun) {
  if (-not $recordIds -or $recordIds.Count -eq 0) { return 0 }
  if ($dryRun) {
    Write-Step ("  [dry-run] would delete {0} old summary record(s)" -f $recordIds.Count)
    return 0
  }
  $url = "https://open.feishu.cn/open-apis/bitable/v1/apps/$($feishu.appToken)/tables/$($feishu.tableId)/records/batch_delete"
  $deleted = 0
  for ($i = 0; $i -lt $recordIds.Count; $i += 500) {
    $chunk = @($recordIds[$i..([Math]::Min($i + 499, $recordIds.Count - 1))])
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes((@{ records = $chunk } | ConvertTo-Json -Compress))
    $resp = Invoke-RestMethod -Method POST -Uri $url -Headers @{ Authorization = "Bearer $token" } `
      -ContentType 'application/json; charset=utf-8' -Body $bodyBytes
    if ($resp.code -ne 0) { throw ("Feishu delete failed: code={0} msg={1}" -f $resp.code, $resp.msg) }
    $deleted += $chunk.Count
  }
  return $deleted
}

# --- main ---
$useDryRun = Convert-Flag $DryRun $false
$doDelete = Convert-Flag $DeleteOldSummary $true
if (-not $BizDate) { $BizDate = Get-BizDateDefault }
if ($BizDate -notmatch '^\d{4}-\d{2}-\d{2}$') { throw "BizDate must be yyyy-MM-dd, got: $BizDate" }

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = Join-Path $logDir ("rewrite-summary-{0}.log" -f $stamp)
function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Add-Content -Path $logFile -Value $line -Encoding UTF8
  Write-Host $line
}

Log "===== rewrite summary START ====="
Log ("config={0}" -f $ConfigPath)
Log ("bizDate={0} dryRun={1} deleteOldSummary={2}" -f $BizDate, $useDryRun, $doDelete)
Log ("table={0}/{1}" -f $cfg.feishu.appToken, $cfg.feishu.tableId)

$token = Get-FeishuToken $cfg.feishu.appId $cfg.feishu.appSecret
$fn = Get-FeishuFieldMap $token $cfg.feishu
Log ("fields date={0} store={1} campaign={2} spend={3} orders={4} roi={5} revenue={6}" -f `
  $fn.date, $fn.store, $fn.campaign, $fn.spend, $fn.orders, $fn.roi, $fn.revenue)

Log "list all records..."
$all = Get-AllFeishuRecords $token $cfg.feishu
Log ("total records in table: {0}" -f $all.Count)

$detailRows = New-Object System.Collections.Generic.List[object]
$oldSummaryIds = New-Object System.Collections.Generic.List[string]
$dateMatchCount = 0

foreach ($rec in $all) {
  $fields = $rec.fields
  if (-not $fields) { continue }
  $ymd = Convert-DateFieldToYmd $fields.($fn.date)
  if ($ymd -ne $BizDate) { continue }
  $dateMatchCount++
  $campaign = Get-FieldText $fields.($fn.campaign)
  $store = Get-FieldText $fields.($fn.store)
  $storeId = ''
  if ($fn.storeId) { $storeId = Get-FieldText $fields.($fn.storeId) }

  if (Test-IsSummaryCampaign $campaign) {
    if ($rec.record_id) { [void]$oldSummaryIds.Add([string]$rec.record_id) }
    continue
  }
  if (-not $campaign -or -not $store) { continue }

  [void]$detailRows.Add([pscustomobject]@{
    recordId = [string]$rec.record_id
    date     = $BizDate
    store    = $store
    storeId  = $storeId
    campaign = $campaign
    spend    = Get-FieldNumber $fields.($fn.spend)
    orders   = Get-FieldNumber $fields.($fn.orders)
    roi      = Get-FieldNumber $fields.($fn.roi)
    revenue  = Get-FieldNumber $fields.($fn.revenue)
  })
}

Log ("rows with date={0}: {1} (detail raw={2}, old summary={3})" -f `
  $BizDate, $dateMatchCount, $detailRows.Count, $oldSummaryIds.Count)

if ($detailRows.Count -eq 0) {
  Log "FATAL: no campaign detail rows for this date. Abort (nothing written)."
  exit 2
}

# Dedup re-run duplicates: store + campaign → keep max spend+revenue
$dedup = @{}
foreach ($r in $detailRows) {
  $key = "{0}`t{1}" -f $r.store, $r.campaign
  if (-not $dedup.ContainsKey($key)) {
    $dedup[$key] = $r
    continue
  }
  $prev = $dedup[$key]
  $scoreNew = [double]$r.spend + [double]$r.revenue
  $scoreOld = [double]$prev.spend + [double]$prev.revenue
  if ($scoreNew -ge $scoreOld) { $dedup[$key] = $r }
}
$campaignRows = @($dedup.Values)
Log ("detail after dedup(store+campaign): {0} (dropped {1} dups)" -f `
  $campaignRows.Count, ($detailRows.Count - $campaignRows.Count))

$byStore = $campaignRows | Group-Object store | Sort-Object Name
foreach ($g in $byStore) {
  $sp = [Math]::Round((($g.Group | Measure-Object spend -Sum).Sum), 2)
  $rv = [Math]::Round((($g.Group | Measure-Object revenue -Sum).Sum), 2)
  Log ("  store={0} campaigns={1} spend={2} revenue={3}" -f $g.Name, $g.Count, $sp, $rv)
}

$runSummary = @($byStore | ForEach-Object {
  [pscustomobject]@{ ok = $true; displayName = $_.Name; error = $null }
})
$lowRoi = 3.0
if ($cfg.analysis -and $null -ne $cfg.analysis.lowRoiThreshold) {
  $lowRoi = [double]$cfg.analysis.lowRoiThreshold
}

Log "build analysis..."
$analysis = Build-DailyAnalysis -CampaignRows $campaignRows -RunSummary $runSummary -BizDate $BizDate -LowRoiThreshold $lowRoi
Log ("analysis totalCampaigns={0} spend={1} orders={2} revenue={3} roi={4} stores={5}" -f `
  $analysis.totalCampaigns, $analysis.totalSpend, $analysis.totalOrders, $analysis.totalRevenue, $analysis.overallRoi, $analysis.storeRollups.Count)

if ($analysis.totalCampaigns -le 0) {
  Log "FATAL: analysis still empty after fix — abort."
  exit 3
}

# Local report files (folder/name via UTF-8 bytes — avoid .ps1 source encoding pitfalls)
$u8 = [System.Text.Encoding]::UTF8
$nameReportDir = $u8.GetString([byte[]](0xE6,0x97,0xA5,0xE6,0x8A,0xA5)) # ri-bao
$nameDailyPrefix = $u8.GetString([byte[]](0xE6,0x97,0xA5,0xE6,0x8A,0xA5,0x2D)) # ri-bao-
$nameBriefPrefix = $u8.GetString([byte[]](0xE7,0xAE,0x80,0xE6,0x8A,0xA5,0x2D)) # jian-bao-
$nameLatestMd = $u8.GetString([byte[]](0xE6,0x9C,0x80,0xE6,0x96,0xB0,0xE6,0x97,0xA5,0xE6,0x8A,0xA5,0x2E,0x6D,0x64))
$nameLatestBrief = $u8.GetString([byte[]](0xE6,0x9C,0x80,0xE6,0x96,0xB0,0xE7,0xAE,0x80,0xE6,0x8A,0xA5,0x2E,0x74,0x78,0x74))
$reportDir = Join-Path $root $nameReportDir
if (-not (Test-Path -LiteralPath $reportDir)) {
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
}
$mdPath = Join-Path $reportDir ("{0}{1}.md" -f $nameDailyPrefix, $BizDate)
$briefPath = Join-Path $reportDir ("{0}{1}.txt" -f $nameBriefPrefix, $BizDate)
$jsonPath = Join-Path $reportDir ("{0}{1}.json" -f $nameDailyPrefix, $BizDate)
Write-Utf8File $mdPath ([string]$analysis.markdown)
Write-Utf8File $briefPath ([string]$analysis.briefText)
$jsonObj = [pscustomobject]@{
  bizDate        = $analysis.bizDate
  totalSpend     = $analysis.totalSpend
  totalOrders    = $analysis.totalOrders
  totalRevenue   = $analysis.totalRevenue
  totalCampaigns = $analysis.totalCampaigns
  overallRoi     = $analysis.overallRoi
  highlights     = $analysis.highlights
  risks          = $analysis.risks
  storeRollups   = $analysis.storeRollups
  source         = 'rewrite-summary-from-feishu'
}
Write-Utf8File $jsonPath ($jsonObj | ConvertTo-Json -Depth 6)
Copy-Item -LiteralPath $mdPath -Destination (Join-Path $reportDir $nameLatestMd) -Force
Copy-Item -LiteralPath $briefPath -Destination (Join-Path $reportDir $nameLatestBrief) -Force
Log ("local reports: {0}" -f $reportDir)
Write-Host ""
Write-Host $analysis.briefText
Write-Host ""

$sumRows = New-SummaryFeishuRows -Analysis $analysis -BizDate $BizDate
Log ("summary rows to write: {0}" -f $sumRows.Count)
foreach ($s in $sumRows) {
  $cShort = $s.campaign
  if ($cShort.Length -gt 60) { $cShort = $cShort.Substring(0, 60) + '...' }
  Log ("  -> store={0} campaign={1} spend={2} orders={3} rev={4} roi={5}" -f `
    $s.store, $cShort, $s.spend, $s.orders, $s.revenue, $s.roi)
}

if ($doDelete -and $oldSummaryIds.Count -gt 0) {
  Log ("delete old summary records: {0}" -f $oldSummaryIds.Count)
  $delN = Remove-FeishuRecords $token $cfg.feishu @($oldSummaryIds) $useDryRun
  Log ("deleted={0}" -f $delN)
} else {
  Log ("skip delete (deleteOldSummary={0}, oldCount={1})" -f $doDelete, $oldSummaryIds.Count)
}

$wr = Write-FeishuRowsLocal $token $cfg.feishu $fn $sumRows $useDryRun
Log ("summary written={0} dryRun={1}" -f $wr.written, $wr.dryRun)
Log ("log={0}" -f $logFile)
Log "===== rewrite summary END ====="

if ($useDryRun) { exit 0 }
if ($wr.written -lt 1) { exit 4 }
exit 0
