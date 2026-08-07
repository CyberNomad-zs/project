# TikTok orders multi-store scrape (P2a) via ziniao-cli
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-orders.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-orders.ps1 -ListOnly
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-orders.ps1 -DryRun true
#
# Requires: Ziniao client + Bridge; config\stores.config.json
# Does NOT write Feishu by default (orders Feishu table optional later) — only Qingquan ingest.

param(
  [string]$ConfigPath = "",
  [switch]$ListOnly,
  [string]$DryRun = ""
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
$scrapeJsPath = Join-Path $root 'scripts\scrape-orders-page.js'
$clickNextJsPath = Join-Path $root 'scripts\orders-click-next.js'
$detailJsPath = Join-Path $root 'scripts\scrape-order-detail-page.js'
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }
if (-not (Test-Path $scrapeJsPath)) { throw "Missing $scrapeJsPath" }

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$scrapeJs = Get-Content $scrapeJsPath -Raw -Encoding UTF8
$clickNextJs = ''
if (Test-Path $clickNextJsPath) {
  $clickNextJs = Get-Content $clickNextJsPath -Raw -Encoding UTF8
}
$detailJs = ''
if (Test-Path $detailJsPath) {
  $detailJs = Get-Content $detailJsPath -Raw -Encoding UTF8
}
$qingquanLib = Join-Path $PSScriptRoot 'qingquan-client.ps1'
if (Test-Path $qingquanLib) { . $qingquanLib }
$ziniaoWinLib = Join-Path $PSScriptRoot 'ziniao-window.ps1'
if (-not (Test-Path $ziniaoWinLib)) { throw "Missing $ziniaoWinLib" }
. $ziniaoWinLib

$script:logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $script:logsDir | Out-Null
$script:runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:runLogFile = Join-Path $script:logsDir ("orders-run-{0}.log" -f $script:runStamp)

function Write-RunLog([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  try { Add-Content -LiteralPath $script:runLogFile -Value $line -Encoding UTF8 } catch { }
}
function Write-Step([string]$msg) {
  Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg)
  Write-RunLog $msg
}

function ConvertTo-ProcessArgument([string]$s) {
  if ($null -eq $s) { return '""' }
  if ($s -match '[\s"]') { return '"' + ($s -replace '"', '\"') + '"' }
  return $s
}

function Initialize-ZiniaoCli {
  if ($script:ZiniaoNode) { return }
  $node = (Get-Command node -ErrorAction SilentlyContinue).Source
  if (-not $node) { throw 'node not found' }
  $runJs = Join-Path $env:APPDATA 'npm\node_modules\@ziniao-open\cli\scripts\run.js'
  if (-not (Test-Path $runJs)) {
    $cmd = Get-Command ziniao -ErrorAction SilentlyContinue
    if ($cmd) { $runJs = $cmd.Source }
  }
  if (-not (Test-Path $runJs)) { throw 'ziniao-cli run.js not found' }
  $script:ZiniaoNode = $node
  $script:ZiniaoRunJs = $runJs
}

function Invoke-Ziniao([string[]]$CliArgs) {
  Initialize-ZiniaoCli
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  $allArgs = @($script:ZiniaoRunJs) + @($CliArgs)
  $argLine = ($allArgs | ForEach-Object { ConvertTo-ProcessArgument ([string]$_) }) -join ' '
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $script:ZiniaoNode
  $psi.Arguments = $argLine
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $psi.StandardOutputEncoding = $utf8
  $psi.StandardErrorEncoding = $utf8
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($stderr) { Write-Host $stderr }
  return $stdout
}

function ConvertTo-ScrapeOneLine([string]$js) {
  $one = ($js -replace '(?m)^\s*//.*$', '' -replace '\r?\n', ' ' -replace '\s+', ' ').Trim()
  return $one
}

function Get-OrdersUrl($store, $cfg) {
  $plat = ''
  if ($store.platformName) { $plat = [string]$store.platformName }
  elseif ($store.platform) { $plat = [string]$store.platform }
  if ($cfg.orderUrl -and $cfg.orderUrl.byPlatform -and $plat) {
    foreach ($p in $cfg.orderUrl.byPlatform.PSObject.Properties) {
      if ($plat -eq [string]$p.Name -or $plat -like ("*{0}*" -f $p.Name) -or ([string]$p.Name -like ("*{0}*" -f $plat))) {
        return [string]$p.Value
      }
    }
  }
  if ($cfg.orderUrl -and $cfg.orderUrl.default) { return [string]$cfg.orderUrl.default }
  if ($cfg.urls -and $cfg.urls.orders) { return [string]$cfg.urls.orders }
  return 'https://seller-uk.tiktok.com/order?selected_sort=6&tab=all'
}

function Get-OrderDetailBaseUrl([string]$orderListUrl) {
  # https://seller-uk.tiktok.com/order?... -> https://seller-uk.tiktok.com/order/detail
  try {
    $u = [uri]$orderListUrl
    $origin = "{0}://{1}" -f $u.Scheme, $u.Host
    return ($origin.TrimEnd('/') + '/order/detail')
  } catch {
    return 'https://seller-uk.tiktok.com/order/detail'
  }
}

function Get-OrderRegionQuery([string]$orderListUrl) {
  if ($orderListUrl -match 'shop_region=([A-Za-z]{2})') { return $Matches[1] }
  if ($orderListUrl -match 'seller-uk') { return 'GB' }
  if ($orderListUrl -match 'seller\.eu') { return '' }
  return 'GB'
}

function Get-DisplayName($store, $map) {
  $n = [string]$store.storeName
  if ($map -and $map.PSObject.Properties.Name -contains $n) { return [string]$map.$n }
  return $n
}

function Get-ScrapePayload([string]$execOut) {
  if ([string]::IsNullOrWhiteSpace($execOut)) { return $null }
  # ziniao wraps result JSON in data.data.result string sometimes
  try {
    $j = $execOut | ConvertFrom-Json
    if ($j.data -and $j.data.data -and $j.data.data.result) {
      $inner = [string]$j.data.data.result
      return ($inner | ConvertFrom-Json)
    }
    if ($j.ok -ne $null -and $j.rows) { return $j }
    if ($j.ok -ne $null) { return $j }
  } catch { }
  # last {...} object in output
  $m = [regex]::Matches($execOut, '\{(?:[^{}]|(?<o>\{)|(?<-o>\}))+(?(o)(?!))\}')
  if ($m.Count -gt 0) {
    try { return ($m[$m.Count - 1].Value | ConvertFrom-Json) } catch { }
  }
  return $null
}

function Convert-DryRunFlag([string]$raw) {
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  switch -Regex ($raw.Trim()) {
    '^(?i:true|1|yes|y|\$true)$'  { return $true }
    '^(?i:false|0|no|n|\$false)$' { return $false }
    default { throw "Invalid -DryRun '$raw'" }
  }
}

Write-Step '===== orders multi-store START ====='
Write-Step ("config={0}" -f $ConfigPath)
Initialize-ZiniaoCli
Write-Step 'list stores...'
$listOut = Invoke-Ziniao @('store', 'list')
$storesObj = $null
try { $storesObj = $listOut | ConvertFrom-Json } catch { throw "store list parse fail: $listOut" }
$all = @()
if ($storesObj.data) {
  if ($storesObj.data.items) { $all = @($storesObj.data.items) }
  elseif ($storesObj.data -is [System.Array]) { $all = @($storesObj.data) }
  elseif ($storesObj.data.list) { $all = @($storesObj.data.list) }
  elseif ($storesObj.data.stores) { $all = @($storesObj.data.stores) }
}
# normalize — ziniao fields: storeId / storeName / platformName / ip
$norm = @()
foreach ($s in $all) {
  $sid = ''
  if ($s.storeId) { $sid = [string]$s.storeId } elseif ($s.id) { $sid = [string]$s.id }
  $sname = ''
  if ($s.storeName) { $sname = [string]$s.storeName } elseif ($s.name) { $sname = [string]$s.name }
  $plat = ''
  if ($s.platformName) { $plat = [string]$s.platformName }
  elseif ($s.platform) { $plat = [string]$s.platform }
  if (-not $sid) { continue }
  $norm += [pscustomobject]@{
    storeId = $sid
    storeName = $sname
    platform = $plat
    platformName = $plat
    ip = $(if ($s.ip) { [string]$s.ip } else { '' })
    raw = $s
  }
}

$selected = @($norm)
if ($cfg.filter) {
  if ($cfg.filter.platformContains -and @($cfg.filter.platformContains).Count -gt 0) {
    $selected = @($selected | Where-Object {
      $p = $_.platform
      $ok = $false
      foreach ($k in @($cfg.filter.platformContains)) { if ($p -like ("*{0}*" -f $k)) { $ok = $true } }
      $ok
    })
  }
  if ($cfg.filter.requireIp) {
    $selected = @($selected | Where-Object { -not [string]::IsNullOrWhiteSpace($_.ip) })
  }
  if ($cfg.filter.excludeStoreIds) {
    $ex = @($cfg.filter.excludeStoreIds | ForEach-Object { [string]$_ })
    $selected = @($selected | Where-Object { $ex -notcontains $_.storeId })
  }
  if ($cfg.filter.includeStoreIds -and @($cfg.filter.includeStoreIds).Count -gt 0) {
    $inc = @($cfg.filter.includeStoreIds | ForEach-Object { [string]$_ })
    $selected = @($selected | Where-Object { $inc -contains $_.storeId })
  }
}

# 非广告排除：欧盟 Pop 等（广告 dual 仍可采 Pop）
if ($cfg.modules) {
  $oex = @()
  if ($cfg.modules.opsExcludeStoreIds) { $oex += @($cfg.modules.opsExcludeStoreIds | ForEach-Object { [string]$_ }) }
  if ($cfg.modules.ordersExcludeStoreIds) { $oex += @($cfg.modules.ordersExcludeStoreIds | ForEach-Object { [string]$_ }) }
  $oex = @($oex | Select-Object -Unique | Where-Object { $_ })
  if ($oex.Count -gt 0) {
    $before = $selected.Count
    $selected = @($selected | Where-Object { $oex -notcontains $_.storeId })
    if ($before -ne $selected.Count) {
      Write-Step ("opsExcludeStoreIds removed {0} store(s): {1}" -f ($before - $selected.Count), ($oex -join ','))
    }
  }
  $pex = @()
  if ($cfg.modules.opsExcludePlatformContains) { $pex += @($cfg.modules.opsExcludePlatformContains | ForEach-Object { [string]$_ }) }
  if ($cfg.modules.ordersExcludePlatformContains) { $pex += @($cfg.modules.ordersExcludePlatformContains | ForEach-Object { [string]$_ }) }
  $pex = @($pex | Select-Object -Unique | Where-Object { $_ })
  if ($pex.Count -gt 0) {
    $before = $selected.Count
    $selected = @($selected | Where-Object {
      $p = [string]$_.platform
      $hit = $false
      foreach ($k in $pex) { if ($k -and $p -like ("*{0}*" -f $k)) { $hit = $true } }
      -not $hit
    })
    if ($before -ne $selected.Count) {
      Write-Step ("opsExcludePlatformContains removed {0} store(s)" -f ($before - $selected.Count))
    }
  }
}

Write-Step ("stores selected: {0}" -f $selected.Count)
foreach ($s in $selected) {
  Write-Step ("  - {0} | {1} | {2}" -f $s.storeId, $s.storeName, $s.platform)
}
if ($ListOnly) { Write-Step 'ListOnly done'; return }
if ($selected.Count -eq 0) { throw 'No stores matched' }

$dryParsed = Convert-DryRunFlag $DryRun
$useDryRun = if ($null -ne $dryParsed) { [bool]$dryParsed } else {
  if ($cfg.options -and $null -ne $cfg.options.dryRun) { [bool]$cfg.options.dryRun } else { $true }
}
$waitOpen = 28000
$waitVisit = 35000
$retries = 3
$orderMaxPages = 10
$orderPageWaitMs = 5000
if ($cfg.options.waitAfterOpenMs) { $waitOpen = [Math]::Max(20000, [int]$cfg.options.waitAfterOpenMs) }
if ($cfg.options.waitAfterVisitMs) { $waitVisit = [Math]::Max(25000, [int]$cfg.options.waitAfterVisitMs) }
if ($cfg.options.scrapeRetries) { $retries = [Math]::Max(2, [int]$cfg.options.scrapeRetries) }
if ($null -ne $cfg.options.orderMaxPages) { $orderMaxPages = [Math]::Max(1, [int]$cfg.options.orderMaxPages) }
if ($null -ne $cfg.options.orderPageWaitMs) { $orderPageWaitMs = [Math]::Max(1500, [int]$cfg.options.orderPageWaitMs) }
# 订单详情补 SKU：默认开；options.orderDetailEnabled=false 可关；orderDetailMax 限制本店最多进详情数
$orderDetailEnabled = $true
$orderDetailMax = 40
$orderDetailWaitMs = 3500
if ($cfg.options -and $null -ne $cfg.options.orderDetailEnabled) {
  $orderDetailEnabled = [bool]$cfg.options.orderDetailEnabled
}
if ($cfg.options -and $null -ne $cfg.options.orderDetailMax) {
  $orderDetailMax = [Math]::Max(0, [int]$cfg.options.orderDetailMax)
}
if ($cfg.options -and $null -ne $cfg.options.orderDetailWaitMs) {
  $orderDetailWaitMs = [Math]::Max(1500, [int]$cfg.options.orderDetailWaitMs)
}
if (-not $detailJs) { $orderDetailEnabled = $false }
$scrapeOneLine = ConvertTo-ScrapeOneLine $scrapeJs
$clickNextOneLine = ''
if ($clickNextJs) { $clickNextOneLine = ConvertTo-ScrapeOneLine $clickNextJs }
$detailOneLine = ''
if ($detailJs) { $detailOneLine = ConvertTo-ScrapeOneLine $detailJs }
Write-Step ("dryRun={0} scrapeLen={1} orderMaxPages={2} pageWaitMs={3} detail={4} detailMax={5}" -f `
  $useDryRun, $scrapeOneLine.Length, $orderMaxPages, $orderPageWaitMs, $orderDetailEnabled, $orderDetailMax)

$summary = @()
foreach ($store in $selected) {
  $sid = $store.storeId
  $sname = $store.storeName
  $display = Get-DisplayName $store $cfg.storeNameMap
  $orderUrl = Get-OrdersUrl $store $cfg
  $item = [ordered]@{
    storeId = $sid; storeName = $sname; displayName = $display
    ok = $false; rows = 0; detailOk = 0; detailFail = 0; lineItems = 0
    qingquanAccepted = 0; qingquanDup = 0; lineAccepted = 0; lineDup = 0; error = $null
  }
  Write-Step ("==== ORDERS {0} ({1}) => {2} ====" -f $sname, $sid, $display)
  try {
    Write-Step '  open store...'
    $openArgs = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $orderUrl -Config $cfg
    Write-Host (Invoke-Ziniao $openArgs)
    Start-Sleep -Milliseconds $waitOpen
    Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null
    Write-Step '  visit orders page...'
    $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $orderUrl, '--wait-until', 'networkidle', '--timeout', '90000')
    Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null
    Start-Sleep -Milliseconds $waitVisit

    $payload = $null
    $rawRows = @()
    $lastErr = $null
    $pagesDone = 0
    $seenIds = @{}

    for ($attempt = 1; $attempt -le $retries; $attempt++) {
      Write-Step ("  scrape attempt {0}/{1} (page 1)..." -f $attempt, $retries)
      $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $scrapeOneLine, '--timeout', '60000')
      $payload = Get-ScrapePayload $execOut
      if ($payload -and $payload.ok -and $payload.rows) {
        $pageRows = @($payload.rows)
        foreach ($r in $pageRows) {
          $oid = ''
          if ($r.orderId) { $oid = [string]$r.orderId } elseif ($r.order_id) { $oid = [string]$r.order_id }
          if (-not $oid -or $seenIds.ContainsKey($oid)) { continue }
          $seenIds[$oid] = $true
          $rawRows += $r
        }
        if ($rawRows.Count -gt 0) { $lastErr = $null; $pagesDone = 1; break }
        $lastErr = '0 order rows'
      } else {
        $lastErr = if ($payload -and $payload.error) { [string]$payload.error } else { 'scrape failed' }
        Write-Step ("  attempt fail: {0}" -f $lastErr)
      }
      if ($attempt -lt $retries) {
        Start-Sleep -Seconds 8
        $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $orderUrl, '--wait-until', 'networkidle', '--timeout', '90000')
        Start-Sleep -Seconds 10
      }
    }
    if ($lastErr -or $rawRows.Count -eq 0) { throw $(if ($lastErr) { $lastErr } else { '0 rows' }) }

    Write-Step ("  page 1 rows={0} (unique total={1})" -f $pagesDone, $rawRows.Count)

    # 翻页：点击下一页 → 等待 → 再 scrape，按 orderId 去重
    if ($orderMaxPages -gt 1 -and $clickNextOneLine) {
      for ($page = 2; $page -le $orderMaxPages; $page++) {
        Write-Step ("  click next for page {0}..." -f $page)
        $nextOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $clickNextOneLine, '--timeout', '30000')
        $nextPayload = Get-ScrapePayload $nextOut
        $hasNext = $false
        if ($nextPayload -and $nextPayload.ok -and $nextPayload.clicked) { $hasNext = $true }
        elseif ($nextPayload -and $nextPayload.hasNext -eq $false) {
          Write-Step ("  no more pages (next disabled/missing): {0}" -f $(if ($nextPayload.error) { $nextPayload.error } else { 'end' }))
          break
        } else {
          # 解析失败时也尝试看 raw
          if ($nextOut -match '"clicked"\s*:\s*true') { $hasNext = $true }
          else {
            Write-Step ("  stop paging: cannot click next | {0}" -f $(if ($nextPayload -and $nextPayload.error) { $nextPayload.error } elseif ($nextOut.Length -gt 120) { $nextOut.Substring(0,120) } else { $nextOut }))
            break
          }
        }
        if (-not $hasNext) { break }

        Start-Sleep -Milliseconds $orderPageWaitMs
        $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $scrapeOneLine, '--timeout', '60000')
        $pagePayload = Get-ScrapePayload $execOut
        if (-not ($pagePayload -and $pagePayload.ok -and $pagePayload.rows)) {
          Write-Step ("  page {0} scrape empty/fail — stop paging" -f $page)
          break
        }
        $added = 0
        foreach ($r in @($pagePayload.rows)) {
          $oid = ''
          if ($r.orderId) { $oid = [string]$r.orderId } elseif ($r.order_id) { $oid = [string]$r.order_id }
          if (-not $oid -or $seenIds.ContainsKey($oid)) { continue }
          $seenIds[$oid] = $true
          $rawRows += $r
          $added++
        }
        $pagesDone++
        $payload = $pagePayload
        Write-Step ("  page {0} new={1} unique total={2}" -f $page, $added, $rawRows.Count)
        if ($added -eq 0) {
          Write-Step '  no new order ids — stop paging'
          break
        }
      }
    } elseif ($orderMaxPages -gt 1 -and -not $clickNextOneLine) {
      Write-Step '  WARN orders-click-next.js missing — only first page scraped'
    }

    $item.rows = $rawRows.Count
    Write-Step ("  scraped {0} order rows source={1} pages={2}" -f $rawRows.Count, $(if ($payload.source) { $payload.source } else { '?' }), $pagesDone)

    # save debug
    $dbg = Join-Path $script:logsDir ("orders-debug-{0}-{1}.json" -f $sid, $script:runStamp)
    (@{ storeId = $sid; displayName = $display; url = $orderUrl; payload = $payload } | ConvertTo-Json -Depth 12) |
      Set-Content -LiteralPath $dbg -Encoding UTF8

    $currency = 'USD'
    if ($payload.currency) { $currency = [string]$payload.currency }
    $srcUrl = $orderUrl
    if ($payload.url) { $srcUrl = [string]$payload.url }

    if ((Get-Command Send-QingquanIngest -ErrorAction SilentlyContinue) -and $cfg.qingquan -and $cfg.qingquan.enabled) {
      if ($useDryRun) {
        Write-Step ("  qingquan dryRun: would report {0} orders" -f $rawRows.Count)
      } else {
        $collectedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00')
        $qqItems = ConvertTo-QingquanOrderIngestItems -Rows $rawRows -CollectedAt $collectedAt `
          -StoreId $sid -StoreName $display -Currency $currency -SourceUrl $srcUrl
        Write-Step ("  report Qingquan tiktok_orders items={0}..." -f $qqItems.Count)
        $qq = Send-QingquanIngest -Config $cfg -Items $qqItems -Source 'tiktok_orders'
        $item.qingquanAccepted = $qq.accepted
        $item.qingquanDup = $qq.duplicated
        if ($qq.error) { $item.error = [string]$qq.error }
        Write-Step ("  qingquan accepted={0} dup={1} failed={2} ok={3}" -f $qq.accepted, $qq.duplicated, $qq.failed, $qq.ok)
      }
    } else {
      Write-Step '  skip qingquan (disabled or client missing)'
    }

    # —— 订单详情补 SKU 行（fact_tiktok_order_line）——
    if ($orderDetailEnabled -and $detailOneLine -and $orderDetailMax -gt 0 -and $rawRows.Count -gt 0) {
      $detailBase = Get-OrderDetailBaseUrl $orderUrl
      $region = Get-OrderRegionQuery $orderUrl
      $targets = @($rawRows | Select-Object -First $orderDetailMax)
      Write-Step ("  order detail enrich: {0}/{1} orders base={2}" -f $targets.Count, $rawRows.Count, $detailBase)
      $detailSamples = New-Object System.Collections.ArrayList
      $allLineItems = New-Object System.Collections.ArrayList
      $di = 0
      foreach ($orow in $targets) {
        $di++
        $oid = ''
        if ($orow.orderId) { $oid = [string]$orow.orderId }
        elseif ($orow.order_id) { $oid = [string]$orow.order_id }
        if (-not $oid) { continue }
        $detailUrl = "{0}?order_no={1}" -f $detailBase, $oid
        if ($region) { $detailUrl = "{0}&shop_region={1}" -f $detailUrl, $region }
        Write-Step ("  detail [{0}/{1}] {2}" -f $di, $targets.Count, $oid)
        try {
          $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $detailUrl, '--wait-until', 'domcontentloaded', '--timeout', '60000')
          Start-Sleep -Milliseconds $orderDetailWaitMs
          $dout = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $detailOneLine, '--timeout', '45000')
          $dp = Get-ScrapePayload $dout
          if ($dp -and $dp.ok -and $dp.lines -and @($dp.lines).Count -gt 0) {
            $item.detailOk++
            $lines = @($dp.lines)
            $item.lineItems += $lines.Count
            if ($detailSamples.Count -lt 3) {
              [void]$detailSamples.Add(@{ orderId = $oid; url = $detailUrl; lineCount = $lines.Count; sample = $lines[0] })
            }
            # 回填列表行上的 sellerSku/skuId（首行）方便本地 debug
            $first = $lines[0]
            if ($first.sellerSku -and -not $orow.sellerSku) { try { $orow | Add-Member -NotePropertyName sellerSku -NotePropertyValue ([string]$first.sellerSku) -Force } catch {} }
            if ($first.skuId -and -not $orow.skuId) { try { $orow | Add-Member -NotePropertyName skuId -NotePropertyValue ([string]$first.skuId) -Force } catch {} }
            if ($first.productName -and ("$($orow.productName)" -match '件商品')) {
              try { $orow | Add-Member -NotePropertyName productName -NotePropertyValue ([string]$first.productName) -Force } catch {}
            }
            foreach ($ln in $lines) {
              [void]$allLineItems.Add([pscustomobject]@{
                orderId = $oid
                line = $ln
                detailUrl = $(if ($dp.url) { [string]$dp.url } else { $detailUrl })
                currency = $(if ($dp.currency) { [string]$dp.currency } else { $currency })
              })
            }
          } else {
            $item.detailFail++
            $err = if ($dp -and $dp.error) { [string]$dp.error } else { 'detail scrape empty' }
            Write-Step ("    detail fail: {0}" -f $err)
          }
        } catch {
          $item.detailFail++
          Write-Step ("    detail exception: {0}" -f $_)
        }
      }

      $detDbg = Join-Path $script:logsDir ("orders-detail-debug-{0}-{1}.json" -f $sid, $script:runStamp)
      (@{
        storeId = $sid; displayName = $display
        detailOk = $item.detailOk; detailFail = $item.detailFail; lineItems = $item.lineItems
        samples = @($detailSamples)
      } | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $detDbg -Encoding UTF8

      if ((Get-Command ConvertTo-QingquanOrderLineIngestItems -ErrorAction SilentlyContinue) -and `
          (Get-Command Send-QingquanIngest -ErrorAction SilentlyContinue) -and `
          $cfg.qingquan -and $cfg.qingquan.enabled -and $allLineItems.Count -gt 0) {
        if ($useDryRun) {
          Write-Step ("  qingquan dryRun: would report {0} order lines" -f $allLineItems.Count)
        } else {
          $collectedAt2 = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00')
          $lineEnvelope = New-Object System.Collections.ArrayList
          # 按订单分组转换
          $byOrder = @{}
          foreach ($wrap in $allLineItems) {
            $k = [string]$wrap.orderId
            if (-not $byOrder.ContainsKey($k)) { $byOrder[$k] = @{ lines = New-Object System.Collections.ArrayList; url = [string]$wrap.detailUrl; currency = [string]$wrap.currency } }
            [void]$byOrder[$k].lines.Add($wrap.line)
            if ($wrap.detailUrl) { $byOrder[$k].url = [string]$wrap.detailUrl }
            if ($wrap.currency) { $byOrder[$k].currency = [string]$wrap.currency }
          }
          foreach ($okey in $byOrder.Keys) {
            $pack = $byOrder[$okey]
            $bizHint = ''
            # 从列表行找 biz
            foreach ($rr in $rawRows) {
              $rid = ''
              if ($rr.orderId) { $rid = [string]$rr.orderId } elseif ($rr.order_id) { $rid = [string]$rr.order_id }
              if ($rid -eq $okey) {
                # ConvertTo-QingquanOrderIngestItems 会算 biz；这里尽量从 createTime 留给后端
                break
              }
            }
            $part = ConvertTo-QingquanOrderLineIngestItems -Lines @($pack.lines) -CollectedAt $collectedAt2 `
              -StoreId $sid -OrderId $okey -StoreName $display -Currency $pack.currency -SourceUrl $pack.url -BizDate $bizHint
            foreach ($it in @($part)) { [void]$lineEnvelope.Add($it) }
          }
          Write-Step ("  report Qingquan tiktok_order_lines items={0}..." -f $lineEnvelope.Count)
          $qqL = Send-QingquanIngest -Config $cfg -Items @($lineEnvelope.ToArray()) -Source 'tiktok_order_lines'
          $item.lineAccepted = $qqL.accepted
          $item.lineDup = $qqL.duplicated
          if ($qqL.error -and -not $item.error) { $item.error = [string]$qqL.error }
          Write-Step ("  order_lines accepted={0} dup={1} failed={2} ok={3}" -f $qqL.accepted, $qqL.duplicated, $qqL.failed, $qqL.ok)
        }
      } elseif ($allLineItems.Count -eq 0) {
        Write-Step '  no order line items scraped from details'
      }
    } elseif (-not $orderDetailEnabled) {
      Write-Step '  skip order detail enrich (disabled or script missing)'
    }

    $item.ok = $true
  } catch {
    $item.error = [string]$_
    Write-Step ("  FAIL: {0}" -f $item.error)
  } finally {
    if ($cfg.options -and $null -ne $cfg.options.closeAfter -and -not [bool]$cfg.options.closeAfter) {
      Write-Step '  leave store open'
    } else {
      try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
    }
  }
  $summary += [pscustomobject]$item
  if ($cfg.options.delayBetweenStoresMs) { Start-Sleep -Milliseconds ([int]$cfg.options.delayBetweenStoresMs) }
}

Write-Step '======== ORDERS SUMMARY ========'
$summary | Format-Table storeName, displayName, ok, rows, detailOk, lineItems, qingquanAccepted, lineAccepted, error -AutoSize
$okN = @($summary | Where-Object { $_.ok }).Count
Write-Step ("OK {0}/{1}" -f $okN, $summary.Count)
$sumPath = Join-Path $script:logsDir ("orders-summary-{0}.json" -f $script:runStamp)
($summary | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $sumPath -Encoding UTF8
Write-Step ("summary: {0}" -f $sumPath)
Write-Step '===== orders multi-store END ====='
