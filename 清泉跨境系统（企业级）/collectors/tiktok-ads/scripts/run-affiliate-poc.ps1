# TikTok affiliate center (经营计划 P3.0/P3.1) — 联盟中心·表现
# 默认只写 logs/affiliate-*-debug-*.json；P3.1 schema+ingest 已就绪，仍默认 -SkipIngest。
# 显式 -SkipIngest:$false 时 performance 模块上报：
#   tiktok_affiliate_daily（店级 KPI）+ tiktok_affiliate_creator（达人行，creator_id=handle）
# 全店策略：三店含 Pop（欧盟），不应用 opsExclude 特殊排除。
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-affiliate-poc.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-affiliate-poc.ps1 -Modules affiliate_nav_discover
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-affiliate-poc.ps1 -Modules affiliate_enter_center,affiliate_probe,affiliate_performance
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-affiliate-poc.ps1 -StoreIds 27501502216807
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-affiliate-poc.ps1 -SkipIngest:$false
#
# Requires: Ziniao + Bridge. URLs: config.affiliateUrl / affiliateNavStartUrl（探路后填真链）。
# enter_center 点击后会缓存深链，同店后续 probe/performance 优先用缓存 URL（不再回 landing）。
# 前置：backend/migrations/022_tk_affiliate_daily.sql 已 apply。

param(
  [string]$ConfigPath = "",
  [switch]$ListOnly,
  [string]$DryRun = "",
  [string]$DateMode = "",
  [string]$Modules = "affiliate_enter_center,affiliate_probe,affiliate_performance",
  [string]$StoreIds = "",
  [switch]$SkipIngest = $true
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$qingquanLib = Join-Path $PSScriptRoot 'qingquan-client.ps1'
if (Test-Path $qingquanLib) { . $qingquanLib }
$ziniaoWinLib = Join-Path $PSScriptRoot 'ziniao-window.ps1'
if (-not (Test-Path $ziniaoWinLib)) { throw "Missing $ziniaoWinLib" }
. $ziniaoWinLib

$script:logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $script:logsDir | Out-Null
$script:runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:runLogFile = Join-Path $script:logsDir ("affiliate-poc-run-{0}.log" -f $script:runStamp)

function Write-RunLog([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  try { Add-Content -LiteralPath $script:runLogFile -Value $line -Encoding UTF8 } catch { }
}
function Write-Step([string]$msg) {
  Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg)
  Write-RunLog $msg
}

function Write-Utf8File([string]$Path, [string]$Content) {
  if ([string]::IsNullOrWhiteSpace($Path)) { throw "Write-Utf8File: Path is empty" }
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $text = if ($null -eq $Content) { '' } else { [string]$Content }
  [System.IO.File]::WriteAllText($Path, $text, [System.Text.UTF8Encoding]::new($false))
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
  return (($js -replace '(?m)^\s*//.*$', '' -replace '\r?\n', ' ' -replace '\s+', ' ').Trim())
}
function Get-ScrapePayload([string]$execOut) {
  if ([string]::IsNullOrWhiteSpace($execOut)) { return $null }
  try {
    $j = $execOut | ConvertFrom-Json
    if ($j.data -and $j.data.data -and $j.data.data.result) {
      return ([string]$j.data.data.result | ConvertFrom-Json)
    }
    if ($null -ne $j.ok) { return $j }
  } catch { }
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
function Get-DisplayName($store, $map) {
  $n = [string]$store.storeName
  if ($map -and $map.PSObject.Properties.Name -contains $n) { return [string]$map.$n }
  return $n
}
function Test-BridgeAlive {
  try {
    $null = Invoke-WebRequest -Uri 'http://127.0.0.1:9481' -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    return $true
  } catch {
    $msg = [string]$_.Exception.Message
    if ($msg -match '401|403|Unauthorized|Forbidden') { return $true }
    return $false
  }
}

function Invoke-EnsurePageReady {
  param(
    [string]$StoreId,
    [string]$TargetUrl,
    [string]$UrlCheckOneLiner,
    [int]$MaxTries = 3
  )
  for ($t = 1; $t -le $MaxTries; $t++) {
    if (-not (Test-BridgeAlive)) {
      Write-Step ("  bridge down try {0}/{1}, wait 15s..." -f $t, $MaxTries)
      Start-Sleep -Seconds 15
      if (-not (Test-BridgeAlive)) {
        if ($t -eq $MaxTries) { return @{ ok = $false; error = 'bridge unreachable' } }
        continue
      }
    }
    try {
      $null = Invoke-Ziniao @('page', 'visit', '--store-id', $StoreId, '--url', $TargetUrl, '--wait-until', 'load', '--timeout', '120000')
    } catch {
      Write-Step ("  visit error try {0}: {1}" -f $t, $_)
      Start-Sleep -Seconds 8
      continue
    }
    Start-Sleep -Seconds 10
    $chkOut = ''
    try {
      $chkOut = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', $UrlCheckOneLiner, '--timeout', '30000')
    } catch {
      Write-Step ("  url-check exec fail try {0}: {1}" -f $t, $_)
      Start-Sleep -Seconds 10
      continue
    }
    $chk = Get-ScrapePayload $chkOut
    $href = ''
    if ($chk -and $chk.href) { $href = [string]$chk.href }
    $blank = $false
    if ($chk -and $chk.blank) { $blank = [bool]$chk.blank }
    if (-not $href -or $href -match 'about:blank' -or $blank) {
      Write-Step ("  page not ready try {0}/{1}: href={2}" -f $t, $MaxTries, $href)
      Start-Sleep -Seconds 12
      continue
    }
    $bodyLen = 0
    if ($chk -and $chk.bodyLen) { $bodyLen = [int]$chk.bodyLen }
    # affiliate SPA often thin until hydrate
    if ($bodyLen -gt 0 -and $bodyLen -lt 400 -and $t -lt $MaxTries) {
      Write-Step ("  thin body bodyLen={0}, wait hydrate try {1}/{2}..." -f $bodyLen, $t, $MaxTries)
      Start-Sleep -Seconds 20
      continue
    }
    return @{ ok = $true; href = $href; bodyLen = $bodyLen }
  }
  return @{ ok = $false; error = 'page not ready after retries' }
}

function Get-ConfigUrlByPlatform($block, [string]$plat) {
  if (-not $block) { return $null }
  if ($block.byPlatform -and $plat) {
    foreach ($p in $block.byPlatform.PSObject.Properties) {
      if ($plat -eq [string]$p.Name -or $plat -like ("*{0}*" -f $p.Name)) {
        $v = [string]$p.Value
        if (-not [string]::IsNullOrWhiteSpace($v)) { return $v }
      }
    }
  }
  if ($block.default -and -not [string]::IsNullOrWhiteSpace([string]$block.default)) {
    return [string]$block.default
  }
  return $null
}

function Get-ModuleUrl($store, $cfg, $moduleKey) {
  $plat = ''
  if ($store.platformName) { $plat = [string]$store.platformName }
  elseif ($store.platform) { $plat = [string]$store.platform }

  # 2026-08-06 Deal: landing click -> affiliate.tiktok.com/insights/transaction-analysis
  $isEu = $plat -match 'EU|Europe|欧盟'
  $homeUk = 'https://seller-uk.tiktok.com/homepage'
  $homeEu = 'https://seller.eu.tiktokshopglobalselling.com/homepage'
  $landUk = 'https://seller-uk.tiktok.com/affiliate/landing'
  $landEu = 'https://seller.eu.tiktokshopglobalselling.com/affiliate/landing'
  $perfUk = 'https://affiliate.tiktok.com/insights/transaction-analysis?shop_region=GB'
  $perfEu = 'https://affiliate.tiktokshopglobalselling.com/insights/transaction-analysis'

  $mapKey = $null
  if ($moduleKey -eq 'affiliate_performance') { $mapKey = 'affiliateUrl' }
  elseif ($moduleKey -eq 'affiliate_probe') { $mapKey = 'affiliateUrl' }
  elseif ($moduleKey -eq 'affiliate_nav_discover') { $mapKey = 'affiliateNavStartUrl' }
  elseif ($moduleKey -eq 'affiliate_enter_center') { $mapKey = 'affiliateLandingUrl' }

  if ($mapKey -and $cfg.$mapKey) {
    $fromCfg = Get-ConfigUrlByPlatform $cfg.$mapKey $plat
    if ($fromCfg) { return $fromCfg }
  }

  # enter_center fallback: old affiliateUrl pointing at landing
  if ($moduleKey -eq 'affiliate_enter_center' -and $cfg.affiliateUrl) {
    $cand = Get-ConfigUrlByPlatform $cfg.affiliateUrl $plat
    if ($cand -and $cand -match 'affiliate/landing') { return $cand }
  }

  if ($cfg.urls -and $cfg.urls.$moduleKey) {
    return [string]$cfg.urls.$moduleKey
  }

  if ($moduleKey -eq 'affiliate_nav_discover') {
    $home = Get-ConfigUrlByPlatform $cfg.shopDailyUrl $plat
    if ($home) { return $home }
    if ($isEu) { return $homeEu }
    return $homeUk
  }
  if ($moduleKey -eq 'affiliate_enter_center') {
    if ($isEu) { return $landEu }
    return $landUk
  }
  if ($moduleKey -eq 'affiliate_probe' -or $moduleKey -eq 'affiliate_performance') {
    if ($isEu) { return $perfEu }
    return $perfUk
  }
  return $null
}

$modList = @($Modules.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$scriptMap = @{
  affiliate_performance  = (Join-Path $root 'scripts\scrape-affiliate-performance-page.js')
  affiliate_probe        = (Join-Path $root 'scripts\_probe-affiliate-page.js')
  affiliate_nav_discover = (Join-Path $root 'scripts\_discover-affiliate-nav.js')
  affiliate_enter_center = (Join-Path $root 'scripts\_click-affiliate-cta.js')
}
$urlCheckScript = Join-Path $root 'scripts\_check-page-url.js'
if (-not (Test-Path $urlCheckScript)) { throw "Missing url check script: $urlCheckScript" }
foreach ($m in $modList) {
  if (-not $scriptMap.ContainsKey($m)) {
    throw "Unknown module: $m (use affiliate_nav_discover,affiliate_enter_center,affiliate_probe,affiliate_performance)"
  }
  if (-not (Test-Path $scriptMap[$m])) { throw "Missing scrape script: $($scriptMap[$m])" }
}

# P3.0 默认三店（含 Pop）；-StoreIds 可覆盖；config.filter.includeStoreIds 优先于默认
# 注意：用 [string[]] 强类型，避免 PS 5.1 下偶发把 @() 收成 $null
[string[]]$defaultPocStoreIds = [string[]]@('27501502216807', '27328767468273', '27758103898326')
[string[]]$cliStoreIds = @()
if (-not [string]::IsNullOrWhiteSpace($StoreIds)) {
  [string[]]$cliStoreIds = @($StoreIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

Write-Step '===== affiliate-poc multi-store START (P3.0 gate) ====='
Write-Step ("config={0} modules={1} SkipIngest={2}" -f $ConfigPath, ($modList -join ','), [bool]$SkipIngest)
Write-Step 'NOTE: POC does NOT create PG fact tables. Debug JSON only. All TikTok stores including Pop.'
Initialize-ZiniaoCli
$listOut = Invoke-Ziniao @('store', 'list')
$storesObj = $listOut | ConvertFrom-Json
$all = @()
if ($storesObj.data) {
  if ($storesObj.data.items) { $all = @($storesObj.data.items) }
  elseif ($storesObj.data -is [System.Array]) { $all = @($storesObj.data) }
  elseif ($storesObj.data.list) { $all = @($storesObj.data.list) }
  elseif ($storesObj.data.stores) { $all = @($storesObj.data.stores) }
}
$norm = @()
foreach ($s in $all) {
  $sid = ''; if ($s.storeId) { $sid = [string]$s.storeId } elseif ($s.id) { $sid = [string]$s.id }
  $sname = ''; if ($s.storeName) { $sname = [string]$s.storeName } elseif ($s.name) { $sname = [string]$s.name }
  $plat = ''; if ($s.platformName) { $plat = [string]$s.platformName } elseif ($s.platform) { $plat = [string]$s.platform }
  if (-not $sid) { continue }
  $norm += [pscustomobject]@{
    storeId = $sid; storeName = $sname; platform = $plat; platformName = $plat
    ip = $(if ($s.ip) { [string]$s.ip } else { '' })
  }
}
$selected = @($norm)
if ($cfg.filter) {
  if ($cfg.filter.platformContains -and @($cfg.filter.platformContains).Count -gt 0) {
    $selected = @($selected | Where-Object {
      $p = $_.platform; $ok = $false
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
}

# 店范围：CLI > filter.includeStoreIds（非空）> P3 默认三店
# JSON 空数组 @() 在 PS 里有时被当成 “有值”，必须用 Count -gt 0
[string[]]$inc = @()
$scopeSrc = 'empty'
if ($null -ne $cliStoreIds -and @($cliStoreIds).Count -gt 0) {
  $inc = [string[]]@($cliStoreIds | ForEach-Object { [string]$_ })
  $scopeSrc = '-StoreIds'
} else {
  $cfgInc = @()
  if ($cfg.filter -and $null -ne $cfg.filter.includeStoreIds) {
    $cfgInc = @($cfg.filter.includeStoreIds | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }
  if ($cfgInc.Count -gt 0) {
    $inc = [string[]]$cfgInc
    $scopeSrc = 'filter.includeStoreIds'
  } else {
    $inc = [string[]]@('27501502216807', '27328767468273', '27758103898326')
    $scopeSrc = 'P3-default-3'
  }
}
Write-Step ("store scope src={0} n={1} ids={2}" -f $scopeSrc, $inc.Count, ($inc -join ','))
Write-Step ("candidates after filter n={0} ids={1}" -f $selected.Count, (($selected | ForEach-Object { $_.storeId }) -join ','))
$incSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
foreach ($id in $inc) { [void]$incSet.Add([string]$id) }
$selected = @($selected | Where-Object { $incSet.Contains([string]$_.storeId) })

# 全店策略：不应用 opsExclude* 特殊排除

Write-Step ("stores selected: {0}" -f $selected.Count)
foreach ($s in $selected) { Write-Step ("  - {0} | {1} | {2}" -f $s.storeId, $s.storeName, $s.platform) }
if ($ListOnly) { Write-Step 'ListOnly done'; return }
if ($selected.Count -eq 0) { throw 'No stores matched (check Ziniao list / IP / StoreIds)' }

$dryParsed = Convert-DryRunFlag $DryRun
$useDryRun = if ($null -ne $dryParsed) { [bool]$dryParsed } else {
  if ($cfg.options -and $null -ne $cfg.options.dryRun) { [bool]$cfg.options.dryRun } else { $true }
}
$waitOpen = 28000; $waitVisit = 35000; $retries = 3
if ($cfg.options.waitAfterOpenMs) { $waitOpen = [Math]::Max(15000, [int]$cfg.options.waitAfterOpenMs) }
if ($cfg.options.waitAfterVisitMs) { $waitVisit = [Math]::Max(15000, [int]$cfg.options.waitAfterVisitMs) }
if ($cfg.options.scrapeRetries) { $retries = [Math]::Max(2, [int]$cfg.options.scrapeRetries) }

$effectiveDateMode = 'yesterday'
if (-not [string]::IsNullOrWhiteSpace($DateMode)) {
  $effectiveDateMode = $DateMode.Trim().ToLowerInvariant()
} elseif ($cfg.options -and $cfg.options.dateMode) {
  $effectiveDateMode = [string]$cfg.options.dateMode
}
if ($effectiveDateMode -notin @('today', 'yesterday')) {
  throw "Invalid dateMode '$effectiveDateMode' (use today|yesterday)"
}
$bizDate = if ($effectiveDateMode -eq 'today') {
  (Get-Date).Date.ToString('yyyy-MM-dd')
} else {
  (Get-Date).Date.AddDays(-1).ToString('yyyy-MM-dd')
}
Write-Step ("dryRun={0} dateMode={1} biz_date={2} (page window may be 近N天 — see payload.window)" -f $useDryRun, $effectiveDateMode, $bizDate)

$oneLiners = @{}
foreach ($m in $modList) {
  $oneLiners[$m] = ConvertTo-ScrapeOneLine (Get-Content $scriptMap[$m] -Raw -Encoding UTF8)
}
$urlCheckOneLiner = ConvertTo-ScrapeOneLine (Get-Content $urlCheckScript -Raw -Encoding UTF8)

$summary = @()
foreach ($store in $selected) {
  $sid = $store.storeId
  $sname = $store.storeName
  $display = Get-DisplayName $store $cfg.storeNameMap
  Write-Step ("==== STORE {0} ({1}) => {2} ====" -f $sname, $sid, $display)

  # 本店 enter_center 点击后发现的深链；后续 probe/performance 优先用它，避免回 landing
  $script:storeDiscoveredAffiliateUrl = $null

  $firstUrl = Get-ModuleUrl $store $cfg $modList[0]
  try {
    if (-not (Test-BridgeAlive)) {
      Write-Step '  bridge not up yet, wait 20s...'
      Start-Sleep -Seconds 20
    }
    Write-Step '  open store...'
    $openArgs = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $firstUrl -Config $cfg
    Write-Host (Invoke-Ziniao $openArgs)
    Start-Sleep -Milliseconds $waitOpen
    Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null

    foreach ($mod in $modList) {
      $item = [ordered]@{
        storeId = $sid; storeName = $sname; displayName = $display; module = $mod
        ok = $false; url = $null; error = $null; debugPath = $null
        creatorIdCount = $null; kpiHitCount = $null; landedHref = $null
        discoveredUrl = $null
      }
      $modUrl = Get-ModuleUrl $store $cfg $mod
      $useCachedDeep = $false
      if ($mod -in @('affiliate_probe', 'affiliate_performance') -and $script:storeDiscoveredAffiliateUrl) {
        $modUrl = [string]$script:storeDiscoveredAffiliateUrl
        $useCachedDeep = $true
      }
      $item.url = $modUrl
      Write-Step ("  -- module {0} url={1}{2}" -f $mod, $modUrl, $(if ($useCachedDeep) { ' (from enter_center)' } else { '' }))
      try {
        # enter_center 之后若已在深链页，performance/probe 不再强制 revisit landing；
        # 但若当前 href 还不是目标，仍 gate 一次。
        $skipVisit = $false
        if ($useCachedDeep) {
          try {
            $curOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $urlCheckOneLiner, '--timeout', '30000')
            $cur = Get-ScrapePayload $curOut
            $curHref = ''
            if ($cur -and $cur.href) { $curHref = [string]$cur.href }
            if ($curHref -and $modUrl -and ($curHref -eq $modUrl -or $curHref.StartsWith(($modUrl -split '\?')[0]))) {
              $skipVisit = $true
              $ready = @{ ok = $true; href = $curHref; bodyLen = $(if ($cur.bodyLen) { [int]$cur.bodyLen } else { 0 }) }
              Write-Step ("  already on deep url href={0} bodyLen={1}" -f $curHref, $ready.bodyLen)
            }
          } catch { $skipVisit = $false }
        }
        if (-not $skipVisit) {
          $ready = Invoke-EnsurePageReady -StoreId $sid -TargetUrl $modUrl -UrlCheckOneLiner $urlCheckOneLiner -MaxTries 3
        }
        if (-not $ready.ok) {
          throw ("page gate failed: {0}" -f $ready.error)
        }
        Write-Step ("  page ready href={0} bodyLen={1}" -f $ready.href, $ready.bodyLen)
        $item.landedHref = $ready.href
        Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null
        $extraWait = [Math]::Max(25000, [Math]::Min($waitVisit, 45000))
        Start-Sleep -Milliseconds $extraWait
        $payload = $null
        $lastErr = $null
        for ($attempt = 1; $attempt -le $retries; $attempt++) {
          if (-not (Test-BridgeAlive)) {
            $lastErr = 'bridge unreachable mid-scrape'
            Write-Step ("  {0}, wait 15s..." -f $lastErr)
            Start-Sleep -Seconds 15
            if ($attempt -lt $retries) {
              if (-not $useCachedDeep) {
                $null = Invoke-EnsurePageReady -StoreId $sid -TargetUrl $modUrl -UrlCheckOneLiner $urlCheckOneLiner -MaxTries 2
              }
              continue
            }
            break
          }
          Write-Step ("  scrape {0} attempt {1}/{2}..." -f $mod, $attempt, $retries)
          $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $oneLiners[$mod], '--timeout', '60000')
          if ([string]::IsNullOrWhiteSpace($execOut)) {
            $lastErr = 'empty page exec'
          } else {
            $payload = Get-ScrapePayload $execOut
            $payloadUrl = ''
            if ($payload -and $payload.url) { $payloadUrl = [string]$payload.url }
            elseif ($payload -and $payload.afterUrl) { $payloadUrl = [string]$payload.afterUrl }
            if ($payloadUrl -match 'about:blank' -or ($payload -and $payload.error -match 'about:blank')) {
              $lastErr = 'page is about:blank — revisit'
              $payload = $null
            } elseif ($payload -and $payload.ok) {
              $lastErr = $null
              break
            } else {
              $lastErr = $null
              if ($payload -and $payload.error) { $lastErr = [string]$payload.error }
              else { $lastErr = 'scrape fail' }
            }
            try {
              $rawPath = Join-Path $script:logsDir ("{0}-exec-raw-{1}-a{2}.txt" -f $mod, $sid, $attempt)
              Write-Utf8File -Path $rawPath -Content ([string]$execOut)
            } catch { Write-Step ("  warn write exec-raw: {0}" -f $_) }
          }
          Write-Step ("  attempt fail: {0}" -f $lastErr)
          if ($attempt -lt $retries) {
            Start-Sleep -Seconds 12
            if ($lastErr -match 'about:blank|bridge') {
              Write-Step '  re-gate page after blank/bridge'
              $null = Invoke-EnsurePageReady -StoreId $sid -TargetUrl $modUrl -UrlCheckOneLiner $urlCheckOneLiner -MaxTries 2
              Start-Sleep -Seconds 20
            } elseif ($lastErr -match 'no affiliate|not ready|SPA|no affiliate CTA') {
              Write-Step '  extra 30s for affiliate SPA render'
              Start-Sleep -Seconds 30
            } else {
              if (-not $useCachedDeep) {
                $null = Invoke-EnsurePageReady -StoreId $sid -TargetUrl $modUrl -UrlCheckOneLiner $urlCheckOneLiner -MaxTries 2
              }
              Start-Sleep -Seconds 15
            }
          }
        }

        # enter_center: after click, poll URL until leave landing or timeout
        if ($mod -eq 'affiliate_enter_center' -and $payload -and $payload.ok) {
          $clickedHref = ''
          if ($payload.clickedHref) { $clickedHref = [string]$payload.clickedHref }
          $clickedText = ''
          if ($payload.clickedText) { $clickedText = [string]$payload.clickedText }
          Write-Step ("  clicked text={0} href={1}" -f $clickedText, $clickedHref)

          if ($clickedHref -match '^https?://' -and $clickedHref -notmatch '/affiliate/landing') {
            Write-Step ("  visit clickedHref deep: {0}" -f $clickedHref)
            $visitOk = $true
            try {
              $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $clickedHref, '--wait-until', 'load', '--timeout', '120000')
            } catch {
              $visitOk = $false
              Write-Step ("  visit clickedHref warn: {0}" -f $_)
            }
            Start-Sleep -Seconds 18
          } else {
            Start-Sleep -Seconds 12
          }

          $finalHref = ''
          for ($w = 1; $w -le 8; $w++) {
            $chkOut2 = ''
            try {
              $chkOut2 = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $urlCheckOneLiner, '--timeout', '30000')
            } catch {
              $chkOut2 = ''
            }
            if (-not [string]::IsNullOrWhiteSpace($chkOut2)) {
              $chk2 = Get-ScrapePayload $chkOut2
              if ($chk2 -and $chk2.href) { $finalHref = [string]$chk2.href }
            }
            Write-Step ("  post-click url poll {0}/8 href={1}" -f $w, $finalHref)
            # success = left seller landing AND not blank
            if ($finalHref -and $finalHref -notmatch 'about:blank' -and $finalHref -notmatch '/affiliate/landing') {
              break
            }
            # still on seller landing: re-click "合作数据分析"
            if ($w -eq 3 -or $w -eq 6) {
              Write-Step '  still on landing, re-click 合作数据分析'
              $forceScript = 'window.__QQ_AFF_CLICK_LABEL__="合作数据分析";' + $oneLiners[$mod]
              try {
                $null = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $forceScript, '--timeout', '60000')
              } catch {
                Write-Step ("  re-click warn: {0}" -f $_)
              }
            }
            Start-Sleep -Seconds 8
          }

          # EU/global often lands on affiliate platform homepage — drill to 表现
          if ($finalHref -match 'affiliate\.(tiktok|tiktokshopglobalselling)\.com' -and $finalHref -notmatch 'transaction-analysis|insights/') {
            Write-Step '  on affiliate home — try navigate to performance (transaction-analysis)'
            $perfTried = $false
            # 1) click 表现 / 数据分析 inside affiliate center
            $clickPerf = @'
(function(){function clean(t){return String(t==null?'':t).replace(/\s+/g,' ').trim()}function clickEl(el){if(!el)return false;try{el.scrollIntoView({block:'center'})}catch(e){}try{el.click();return true}catch(e2){return false}}var labels=['表现','Performance','合作数据分析','数据分析'];var nodes=document.querySelectorAll('a,button,div,span,li,[role="button"],[role="link"]');var best=null,bestS=-1;for(var i=0;i<Math.min(nodes.length,900);i++){var el=nodes[i];var tx=clean(el.innerText||el.textContent);if(!tx||tx.length>24)continue;var s=-1;if(tx==='表现'||tx==='Performance')s=30;else if(/合作数据分析/.test(tx))s=25;else if(tx==='数据分析'||tx==='Analytics')s=18;if(s>bestS){bestS=s;best=el}}if(!best)return JSON.stringify({ok:false,error:'no perf nav'});var p=best;for(var d=0;d<4&&p;d++){if(p.tagName==='A'&&(p.href||p.getAttribute('href'))){best=p;break}p=p.parentElement}var ok=clickEl(best);return JSON.stringify({ok:ok,clicked:clean(best.innerText||'').slice(0,40),href:best.href||best.getAttribute('href')||null,afterUrl:location.href})}())
'@
            try {
              $cpOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', (ConvertTo-ScrapeOneLine $clickPerf), '--timeout', '60000')
              $cp = Get-ScrapePayload $cpOut
              Write-Step ("  click perf nav: ok={0} text={1}" -f $(if ($cp) { $cp.ok } else { '?' }), $(if ($cp -and $cp.clicked) { $cp.clicked } else { '' }))
              Start-Sleep -Seconds 14
              $perfTried = $true
            } catch {
              Write-Step ("  click perf nav warn: {0}" -f $_)
            }
            # 2) direct visit constructed insights URL (keep shop_id/region)
            try {
              $u = [Uri]$finalHref
              $qs = $u.Query
              if (-not $qs) { $qs = '' }
              $hostPerf = $u.Host
              $perfUrl = "https://{0}/insights/transaction-analysis{1}" -f $hostPerf, $qs
              Write-Step ("  visit constructed perf url: {0}" -f $perfUrl)
              $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $perfUrl, '--wait-until', 'load', '--timeout', '120000')
              Start-Sleep -Seconds 16
              $perfTried = $true
            } catch {
              Write-Step ("  visit perf url warn: {0}" -f $_)
            }
            if ($perfTried) {
              try {
                $chkOut3 = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $urlCheckOneLiner, '--timeout', '30000')
                $chk3 = Get-ScrapePayload $chkOut3
                if ($chk3 -and $chk3.href) { $finalHref = [string]$chk3.href }
                Write-Step ("  after perf drill href={0}" -f $finalHref)
              } catch { }
            }
          }

          if ($finalHref -and $finalHref -notmatch 'about:blank') {
            $item.landedHref = $finalHref
            if ($finalHref -notmatch '/affiliate/landing') {
              $script:storeDiscoveredAffiliateUrl = $finalHref
              $item.discoveredUrl = $finalHref
              Write-Step ("  DISCOVERED deep affiliate url: {0}" -f $finalHref)
            } elseif ($clickedHref -match '^https?://' -and $clickedHref -notmatch '/affiliate/landing') {
              $script:storeDiscoveredAffiliateUrl = $clickedHref
              $item.discoveredUrl = $clickedHref
              Write-Step ("  DISCOVERED from clickedHref: {0}" -f $clickedHref)
            } else {
              Write-Step ("  still on portal after click: {0} (deep URL unknown)" -f $finalHref)
            }
          } elseif ($clickedHref -match '^https?://') {
            $script:storeDiscoveredAffiliateUrl = $clickedHref
            $item.discoveredUrl = $clickedHref
            Write-Step ("  fallback discovered clickedHref: {0}" -f $clickedHref)
          }
        }

        $dbg = Join-Path $script:logsDir ("{0}-debug-{1}-{2}.json" -f $mod, $sid, $script:runStamp)
        $dbgObj = @{
          storeId = $sid
          displayName = $display
          platform = [string]$store.platform
          url = $modUrl
          landedHref = $item.landedHref
          discoveredUrl = $item.discoveredUrl
          bizDate = $bizDate
          module = $mod
          scrapeOk = [bool]($payload -and $payload.ok)
          payload = $payload
          lastError = $lastErr
        }
        try {
          $json = $dbgObj | ConvertTo-Json -Depth 14 -Compress:$false
          Write-Utf8File -Path $dbg -Content $json
          $item.debugPath = $dbg
          Write-Step ("  debug: {0}" -f $dbg)
        } catch {
          Write-Step ("  warn write debug: {0}" -f $_)
        }

        if ($lastErr -or -not $payload -or -not $payload.ok) {
          if ($lastErr) { throw $lastErr }
          throw 'no payload'
        }

        if ($payload -and $null -ne $payload.creatorIdCount) {
          $item.creatorIdCount = [int]$payload.creatorIdCount
          Write-Step ("  creatorIdCount={0}" -f $item.creatorIdCount)
        } elseif ($payload -and $payload.creators) {
          $cidN = @($payload.creators | Where-Object { $_.creatorId -or $_.creator_id }).Count
          $item.creatorIdCount = $cidN
          Write-Step ("  creatorIdCount={0}" -f $cidN)
        }
        if ($payload -and $payload.kpis) {
          $kh = 0
          foreach ($p in $payload.kpis.PSObject.Properties) {
            if ($null -ne $p.Value -and "$($p.Value)" -ne '') { $kh++ }
          }
          $item.kpiHitCount = $kh
          Write-Step ("  kpiHitCount={0}" -f $kh)
        }
        if ($payload -and $payload.links) {
          Write-Step ("  discover links={0}" -f @($payload.links).Count)
        }
        if ($payload -and $payload.candidates) {
          Write-Step ("  cta candidates={0}" -f @($payload.candidates).Count)
        }

        if (-not $SkipIngest) {
          if ($mod -eq 'affiliate_performance' -and (Get-Command Send-QingquanIngest -ErrorAction SilentlyContinue) -and $cfg.qingquan -and $cfg.qingquan.enabled) {
            $collectedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00')
            $pageCur = 'GBP'
            if ($payload -and $payload.currency) { $pageCur = [string]$payload.currency }
            elseif ($cfg.currency -and $cfg.currency.pageDefault) { $pageCur = [string]$cfg.currency.pageDefault }
            $srcUrl = $modUrl
            if ($payload -and $payload.url) { $srcUrl = [string]$payload.url }

            $dailyItems = ConvertTo-QingquanAffiliateDailyIngestItems -Payload $payload -CollectedAt $collectedAt `
              -StoreId $sid -StoreName $display -BizDate $bizDate -Currency $pageCur -SourceUrl $srcUrl
            $dailyN = @($dailyItems).Count
            if ($dailyN -le 0) {
              Write-Step '  qingquan: no affiliate_daily row (empty payload/kpis)'
            } elseif ($useDryRun) {
              Write-Step ("  qingquan dryRun: would report tiktok_affiliate_daily x{0}" -f $dailyN)
            } else {
              $qqD = Send-QingquanIngest -Config $cfg -Items $dailyItems -Source 'tiktok_affiliate_daily'
              Write-Step ("  qingquan affiliate_daily accepted={0} dup={1} ok={2}" -f $qqD.accepted, $qqD.duplicated, $qqD.ok)
              if ($qqD.error) { $item.error = [string]$qqD.error }
            }

            $creatorItems = ConvertTo-QingquanAffiliateCreatorIngestItems -Payload $payload -CollectedAt $collectedAt `
              -StoreId $sid -StoreName $display -BizDate $bizDate -Currency $pageCur -SourceUrl $srcUrl
            $creatorN = @($creatorItems).Count
            if ($creatorN -le 0) {
              Write-Step '  qingquan: no affiliate_creator rows (empty creators[] / no handle)'
            } elseif ($useDryRun) {
              Write-Step ("  qingquan dryRun: would report tiktok_affiliate_creator x{0}" -f $creatorN)
            } else {
              $qqC = Send-QingquanIngest -Config $cfg -Items $creatorItems -Source 'tiktok_affiliate_creator'
              Write-Step ("  qingquan affiliate_creator accepted={0} dup={1} ok={2}" -f $qqC.accepted, $qqC.duplicated, $qqC.ok)
              if ($qqC.error) {
                if ($item.error) { $item.error = ("{0}; {1}" -f $item.error, $qqC.error) }
                else { $item.error = [string]$qqC.error }
              }
            }
          } elseif ($mod -eq 'affiliate_performance') {
            Write-Step '  skip qingquan: qingquan disabled or client not loaded'
          } else {
            Write-Step ("  skip qingquan for module {0} (only affiliate_performance reports)" -f $mod)
          }
        } else {
          Write-Step '  skip qingquan (POC default SkipIngest)'
        }
        $item.ok = $true
      } catch {
        $item.error = [string]$_
        Write-Step ("  FAIL {0}: {1}" -f $mod, $item.error)
      }
      $summary += [pscustomobject]$item
    }
  } catch {
    Write-Step ("  STORE FAIL {0}: {1}" -f $sname, $_)
  } finally {
    if ($cfg.options -and $null -ne $cfg.options.closeAfter -and -not [bool]$cfg.options.closeAfter) {
      Write-Step '  leave store open'
    } else {
      try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
    }
  }
  if ($cfg.options.delayBetweenStoresMs) { Start-Sleep -Milliseconds ([int]$cfg.options.delayBetweenStoresMs) }
}

Write-Step '======== AFFILIATE-POC SUMMARY ========'
$summary | Format-Table storeName, module, ok, creatorIdCount, kpiHitCount, error -AutoSize
$okN = @($summary | Where-Object { $_.ok }).Count
Write-Step ("OK {0}/{1}" -f $okN, $summary.Count)
$sumPath = Join-Path $script:logsDir ("affiliate-poc-summary-{0}.json" -f $script:runStamp)
Write-Utf8File -Path $sumPath -Content (($summary | ConvertTo-Json -Depth 8))
Write-Step ("summary: {0}" -f $sumPath)
Write-Step 'Next: fill docs/TK-P3-达人表现POC结论.md from debug JSON; do NOT create empty fact tables until gate passes.'
Write-Step '===== affiliate-poc multi-store END ====='
