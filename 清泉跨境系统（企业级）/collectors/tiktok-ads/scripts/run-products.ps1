# TikTok products multi-store scrape (P2b) via ziniao-cli
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-products.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-products.ps1 -ListOnly
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-products.ps1 -DryRun true
#
# Requires: Ziniao client + Bridge; config\stores.config.json
# Does NOT write Feishu by default — only Qingquan ingest.
#
# 2026-08-04 页面门禁：
#   - open 后 warm 必须落在 /product/manage（订单/健康/财务/首页不算就绪）
#   - 落错页：visit + 侧栏「商品」菜单纠偏（有限次）
#   - scrape/ingest 前再校验 URL；订单页禁止上传

param(
  [string]$ConfigPath = "",
  [switch]$ListOnly,
  [string]$DryRun = ""
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
$scrapeJsPath = Join-Path $root 'scripts\scrape-products-page.js'
$clickNextJsPath = Join-Path $root 'scripts\products-click-next.js'
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }
if (-not (Test-Path $scrapeJsPath)) { throw "Missing $scrapeJsPath" }
$clickNextJs = ''
if (Test-Path $clickNextJsPath) { $clickNextJs = Get-Content $clickNextJsPath -Raw -Encoding UTF8 }

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$scrapeJs = Get-Content $scrapeJsPath -Raw -Encoding UTF8
$qingquanLib = Join-Path $PSScriptRoot 'qingquan-client.ps1'
if (Test-Path $qingquanLib) { . $qingquanLib }
$ziniaoWinLib = Join-Path $PSScriptRoot 'ziniao-window.ps1'
if (-not (Test-Path $ziniaoWinLib)) { throw "Missing $ziniaoWinLib" }
. $ziniaoWinLib

$script:logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $script:logsDir | Out-Null
$script:runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:runLogFile = Join-Path $script:logsDir ("products-run-{0}.log" -f $script:runStamp)

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
  # 合并 stderr：Bridge 错误有时只在 stderr 的 JSON 里，stdout 为空
  if ([string]::IsNullOrWhiteSpace($stdout) -and $stderr -and ($stderr -match '\{')) {
    return $stderr
  }
  if ($stdout -and $stderr -and ($stderr -match '无法连接紫鸟浏览器 Bridge') -and ($stdout -notmatch '无法连接')) {
    return ($stdout + "`n" + $stderr)
  }
  return $stdout
}

function ConvertTo-ScrapeOneLine([string]$js) {
  $one = ($js -replace '(?m)^\s*//.*$', '' -replace '\r?\n', ' ' -replace '\s+', ' ').Trim()
  return $one
}

function Get-ProductsUrl($store, $cfg) {
  $plat = ''
  if ($store.platformName) { $plat = [string]$store.platformName }
  elseif ($store.platform) { $plat = [string]$store.platform }
  if ($cfg.productUrl -and $cfg.productUrl.byPlatform -and $plat) {
    foreach ($p in $cfg.productUrl.byPlatform.PSObject.Properties) {
      if ($plat -eq [string]$p.Name -or $plat -like ("*{0}*" -f $p.Name) -or ([string]$p.Name -like ("*{0}*" -f $plat))) {
        return [string]$p.Value
      }
    }
  }
  if ($cfg.productUrl -and $cfg.productUrl.default) { return [string]$cfg.productUrl.default }
  # 禁止回退到订单 URL（历史误写 urls.orders 会把商品模块开到订单页）
  if ($cfg.urls -and $cfg.urls.products) { return [string]$cfg.urls.products }
  return 'https://seller-uk.tiktok.com/product/manage'
}

function Test-IsProductManageUrl([string]$href) {
  if ([string]::IsNullOrWhiteSpace($href)) { return $false }
  if ($href -eq 'about:blank') { return $false }
  # 商品管理主路径（英区/欧盟/全局卖家域名）
  if ($href -match '(?i)/product/manage') { return $true }
  if ($href -match '(?i)/product/(list|manage|all)') { return $true }
  return $false
}

function Test-IsForbiddenNonProductUrl([string]$href) {
  if ([string]::IsNullOrWhiteSpace($href)) { return $false }
  # 明确非商品业务页：禁止 warm 就绪 / 禁止 ingest
  if ($href -match '(?i)/order(\?|/|$)|[?&]tab=all') { return $true }
  if ($href -match '(?i)/health-center|/finance/|/homepage|/ads-creation|/compass|/creator') { return $true }
  return $false
}

function Get-PageHrefSnapshot([string]$sid) {
  $warmJs = 'JSON.stringify({ok:true,href:String(location.href||""),tables:document.querySelectorAll("table").length,tlen:((document.body&&document.body.innerText)||"").length,title:String(document.title||"")})'
  [void](Wait-ZiniaoBridgeReady -MaxSec 15)
  $warm = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $warmJs, '--timeout', '30000')
  if (Test-ZiniaoBridgeError $warm) {
    return [pscustomobject]@{ ok = $false; bridgeError = $true; href = ''; tables = 0; tlen = 0; title = ''; raw = $warm }
  }
  $p = Get-ScrapePayload $warm
  $href = ''; $tables = 0; $tlen = 0; $title = ''
  if ($p) {
    if ($p.href) { $href = [string]$p.href }
    if ($null -ne $p.tables) { $tables = [int]$p.tables }
    if ($null -ne $p.tlen) { $tlen = [int]$p.tlen }
    if ($p.title) { $title = [string]$p.title }
  }
  return [pscustomobject]@{
    ok = $true; bridgeError = $false
    href = $href; tables = $tables; tlen = $tlen; title = $title; raw = $warm
  }
}

function Invoke-ProductPageRecover([string]$sid, [string]$productUrl, [int]$attempt = 1) {
  # 纠偏策略（有限次，避免把 Bridge 打挂）：
  #  1) page visit 商品 URL（load，比 networkidle 轻）
  #  2) 仍不对 → 点左侧「商品/Products」菜单
  #  3) 再 visit 一次
  Write-Step ("  recover product page attempt {0}: visit {1}" -f $attempt, $productUrl)
  [void](Wait-ZiniaoBridgeReady -MaxSec 25)
  $visitOut = Invoke-Ziniao @(
    'page', 'visit', '--store-id', $sid, '--url', $productUrl,
    '--wait-until', 'load', '--timeout', '90000'
  )
  if (Test-ZiniaoBridgeError $visitOut) {
    Write-Step '  recover visit: Bridge error — wait 15s'
    Start-Sleep -Seconds 15
    [void](Wait-ZiniaoBridgeReady -MaxSec 40)
  } else {
    Write-Step '  recover visit issued'
  }
  Start-Sleep -Seconds 8
  $snap = Get-PageHrefSnapshot $sid
  if ($snap.ok -and (Test-IsProductManageUrl $snap.href)) {
    Write-Step ("  recover OK via visit href={0}" -f $snap.href)
    return $snap
  }
  Write-Step ("  after visit still href={0} — try menu click" -f $(if ($snap.href) { $snap.href } else { '(empty)' }))

  # 菜单点击：商品 / Products / 商品管理（不依赖稳定 selector）
  $menuJs = @'
(function(){
  function visible(el){
    if(!el) return false;
    var r=el.getBoundingClientRect();
    if(r.width<2||r.height<2) return false;
    var st=window.getComputedStyle(el);
    return st && st.visibility!=='hidden' && st.display!=='none';
  }
  var re=/^(商品管理|商品列表|全部商品|Products?|Product\s*list|Manage\s*products?)$/i;
  var reSoft=/(商品管理|商品列表|全部商品|Product\s*manage|Manage\s*products)/i;
  var nodes=Array.prototype.slice.call(document.querySelectorAll('a,button,[role="menuitem"],[role="link"],span,div'));
  var cand=[];
  for(var i=0;i<nodes.length;i++){
    var t=(nodes[i].innerText||nodes[i].textContent||'').replace(/\s+/g,' ').trim();
    if(!t||t.length>40) continue;
    if(!visible(nodes[i])) continue;
    if(re.test(t) || reSoft.test(t)){
      var score=re.test(t)?100:50;
      if(/manage|管理|列表|list/i.test(t)) score+=20;
      cand.push({el:nodes[i],t:t,score:score});
    }
  }
  cand.sort(function(a,b){return b.score-a.score;});
  if(!cand.length){
    return JSON.stringify({ok:false,error:'no product menu item',href:String(location.href||'')});
  }
  var hit=cand[0];
  try { hit.el.click(); } catch(e) {
    try { hit.el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); } catch(e2) {}
  }
  return JSON.stringify({ok:true,clicked:hit.t,href:String(location.href||'')});
})()
'@
  $menuOne = ConvertTo-ScrapeOneLine $menuJs
  $menuOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $menuOne, '--timeout', '30000')
  $menuPayload = Get-ScrapePayload $menuOut
  if ($menuPayload -and $menuPayload.ok) {
    Write-Step ("  menu clicked: {0}" -f $menuPayload.clicked)
  } else {
    Write-Step ("  menu click soft-fail: {0}" -f $(if ($menuPayload -and $menuPayload.error) { $menuPayload.error } else { 'unknown' }))
  }
  Start-Sleep -Seconds 6
  # 菜单点完再 visit 一次，确保落到 manage
  $null = Invoke-Ziniao @(
    'page', 'visit', '--store-id', $sid, '--url', $productUrl,
    '--wait-until', 'load', '--timeout', '90000'
  )
  Start-Sleep -Seconds 8
  $snap2 = Get-PageHrefSnapshot $sid
  if ($snap2.ok -and (Test-IsProductManageUrl $snap2.href)) {
    Write-Step ("  recover OK via menu+visit href={0}" -f $snap2.href)
  } else {
    Write-Step ("  recover STILL BAD href={0}" -f $(if ($snap2.href) { $snap2.href } else { '(empty)' }))
  }
  return $snap2
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

function Test-ZiniaoBridgeError([string]$out) {
  # 注意：ziniao 成功提示常走 stderr，Invoke-Ziniao 只返回 stdout → 空串≠Bridge 挂
  if ([string]::IsNullOrWhiteSpace($out)) { return $false }
  if ($out -match '无法连接紫鸟浏览器 Bridge|无法连接.*9481') { return $true }
  try {
    $j = $out | ConvertFrom-Json
    if ($j.ok -eq $false -and $j.error) {
      $msg = "$($j.error.message)$($j.error.hint)$($j.error.type)"
      if ($msg -match 'Bridge|9481|无法连接紫鸟') { return $true }
    }
  } catch { }
  return $false
}

function Test-ZiniaoCliFailed([string]$out) {
  if ([string]::IsNullOrWhiteSpace($out)) { return $false }
  if (Test-ZiniaoBridgeError $out) { return $true }
  try {
    $j = $out | ConvertFrom-Json
    if ($j.ok -eq $false) { return $true }
  } catch { }
  return $false
}

function Wait-ZiniaoBridgeReady([int]$MaxSec = 60) {
  $deadline = (Get-Date).AddSeconds($MaxSec)
  while ((Get-Date) -lt $deadline) {
    $portUp = $false
    try {
      $tnc = Test-NetConnection -ComputerName '127.0.0.1' -Port 9481 -WarningAction SilentlyContinue
      if ($tnc -and $tnc.TcpTestSucceeded) { $portUp = $true }
    } catch {
      try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', 9481, $null, $null)
        $portUp = $iar.AsyncWaitHandle.WaitOne(1500, $false) -and $c.Connected
        $c.Close()
      } catch { $portUp = $false }
    }
    if ($portUp) { return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Open-ProductStore([string]$sid, [string]$productUrl, $cfg, [int]$waitOpenMs) {
  # 策略（2026-08-04）：
  #  1) store open --url product/manage + settle（商品 visit 仍可能打挂 Bridge，先尽量不 visit）
  #  2) warm **必须** href 为商品页；订单/健康/财务/首页一律不算就绪
  #  3) 若落错页：有限次 visit + 菜单点击纠偏（最多 2 轮），仍失败则抛错，禁止在订单页 scrape/ingest
  $openArgsLocal = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $productUrl -Config $cfg
  $openOut = Invoke-Ziniao $openArgsLocal
  Write-Host $openOut
  $settle = [Math]::Max($waitOpenMs, 50000)
  Write-Step ("  open done — settle {0}ms then require product/manage URL..." -f $settle)
  Start-Sleep -Milliseconds $settle
  Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null

  $href = ''
  $tables = 0
  $tlen = 0
  $productReady = $false
  $maxWarm = 8
  for ($wi = 1; $wi -le $maxWarm; $wi++) {
    $snap = Get-PageHrefSnapshot $sid
    if ($snap.bridgeError) {
      Write-Step ("  warm {0}/{1}: Bridge busy — wait 12s" -f $wi, $maxWarm)
      Start-Sleep -Seconds 12
      continue
    }
    $href = [string]$snap.href
    $tables = [int]$snap.tables
    $tlen = [int]$snap.tlen
    Write-Step ("  warm {0}/{1} href={2} tables={3} tlen={4}" -f $wi, $maxWarm, $(if ($href) { $href } else { '(empty)' }), $tables, $tlen)

    if (Test-IsForbiddenNonProductUrl $href) {
      Write-Step ("  warm: FORBIDDEN non-product URL (will recover) — {0}" -f $href)
      break
    }
    if (Test-IsProductManageUrl $href) {
      if ($tables -gt 0 -or $tlen -gt 200) {
        $productReady = $true
        break
      }
      Write-Step '  on product URL but thin — wait 12s for table'
      Start-Sleep -Seconds 12
      $snap2 = Get-PageHrefSnapshot $sid
      if ($snap2.ok -and (Test-IsProductManageUrl $snap2.href) -and ($snap2.tables -gt 0 -or $snap2.tlen -gt 80)) {
        $href = [string]$snap2.href
        $tables = [int]$snap2.tables
        $tlen = [int]$snap2.tlen
        $productReady = $true
        break
      }
      # URL 已对，即使表未齐也先记 ready，scrape 自己重试
      $productReady = $true
      break
    }
    if ($href -and $href -ne 'about:blank') {
      Write-Step ("  warm: not product URL yet — {0}" -f $href)
    }
    Start-Sleep -Seconds 8
  }

  # 纠偏：最多 2 轮 visit/菜单；仍失败再 close/reopen + 1 轮
  if (-not $productReady) {
    for ($ri = 1; $ri -le 2; $ri++) {
      $rec = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $ri
      if ($rec.ok -and (Test-IsProductManageUrl $rec.href) -and -not (Test-IsForbiddenNonProductUrl $rec.href)) {
        $href = [string]$rec.href
        $tables = [int]$rec.tables
        $tlen = [int]$rec.tlen
        $productReady = $true
        break
      }
      Start-Sleep -Seconds 5
    }
  }

  if (-not $productReady) {
    Write-Step '  still not on product page — close/reopen once + recover'
    try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
    Start-Sleep -Seconds 5
    Write-Host (Invoke-Ziniao $openArgsLocal)
    Start-Sleep -Milliseconds ([Math]::Max($settle, 55000))
    $rec = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt 3
    if ($rec.ok -and (Test-IsProductManageUrl $rec.href) -and -not (Test-IsForbiddenNonProductUrl $rec.href)) {
      $href = [string]$rec.href
      $tables = [int]$rec.tables
      $tlen = [int]$rec.tlen
      $productReady = $true
    }
  }

  if (-not $productReady) {
    $final = Get-PageHrefSnapshot $sid
    $finalHref = if ($final.href) { $final.href } elseif ($href) { $href } else { '(unknown)' }
    throw ("Open-ProductStore: not on product/manage after recover. href={0}" -f $finalHref)
  }
  if (Test-IsForbiddenNonProductUrl $href) {
    throw ("Open-ProductStore: landed on forbidden URL {0}" -f $href)
  }
  Write-Step ("  product page READY href={0} tables={1} tlen={2}" -f $href, $tables, $tlen)
  return [pscustomobject]@{ href = $href; tables = $tables; tlen = $tlen }
}

function Convert-DryRunFlag([string]$raw) {
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  switch -Regex ($raw.Trim()) {
    '^(?i:true|1|yes|y|\$true)$'  { return $true }
    '^(?i:false|0|no|n|\$false)$' { return $false }
    default { throw "Invalid -DryRun '$raw'" }
  }
}

Write-Step '===== products multi-store START ====='
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

# 非广告排除：欧盟 Pop 等（与 orders/shop-modules 共用；广告仍可采）
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
$productMaxPages = 1
$productPageWaitMs = 5000
if ($cfg.options.waitAfterOpenMs) { $waitOpen = [Math]::Max(20000, [int]$cfg.options.waitAfterOpenMs) }
if ($cfg.options.waitAfterVisitMs) { $waitVisit = [Math]::Max(25000, [int]$cfg.options.waitAfterVisitMs) }
if ($cfg.options.scrapeRetries) { $retries = [Math]::Max(2, [int]$cfg.options.scrapeRetries) }
if ($null -ne $cfg.options.productMaxPages) { $productMaxPages = [Math]::Max(1, [int]$cfg.options.productMaxPages) }
if ($null -ne $cfg.options.productPageWaitMs) { $productPageWaitMs = [Math]::Max(1500, [int]$cfg.options.productPageWaitMs) }
$scrapeOneLine = ConvertTo-ScrapeOneLine $scrapeJs
$clickNextOneLine = ''
if ($clickNextJs) { $clickNextOneLine = ConvertTo-ScrapeOneLine $clickNextJs }
Write-Step ("dryRun={0} scrapeLen={1} productMaxPages={2} pageWaitMs={3}" -f $useDryRun, $scrapeOneLine.Length, $productMaxPages, $productPageWaitMs)

$summary = @()
foreach ($store in $selected) {
  $sid = $store.storeId
  $sname = $store.storeName
  $display = Get-DisplayName $store $cfg.storeNameMap
  $productUrl = Get-ProductsUrl $store $cfg
  $item = [ordered]@{
    storeId = $sid; storeName = $sname; displayName = $display
    ok = $false; rows = 0; qingquanAccepted = 0; qingquanDup = 0; error = $null
  }
  Write-Step ("==== PRODUCTS {0} ({1}) => {2} ====" -f $sname, $sid, $display)
  try {
    Write-Step '  open + settle product page...'
    $opened = Open-ProductStore -sid $sid -productUrl $productUrl -cfg $cfg -waitOpenMs $waitOpen
    Write-Step ("  open result href={0}" -f $(if ($opened -and $opened.href) { $opened.href } else { '?' }))

    $payload = $null
    $rawRows = @()
    $lastErr = $null
    $pagesDone = 0
    $seenIds = @{}
    $pageUrl = ''

    for ($attempt = 1; $attempt -le $retries; $attempt++) {
      # 每次 scrape 前再确认仍在商品页（SPA 可能中途跳走）
      $pre = Get-PageHrefSnapshot $sid
      if ($pre.ok -and (Test-IsForbiddenNonProductUrl $pre.href)) {
        Write-Step ("  pre-scrape: on forbidden URL {0} — recover" -f $pre.href)
        $null = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $attempt
        $pre = Get-PageHrefSnapshot $sid
      }
      if ($pre.ok -and -not (Test-IsProductManageUrl $pre.href)) {
        Write-Step ("  pre-scrape: not product URL {0} — recover" -f $(if ($pre.href) { $pre.href } else { '(empty)' }))
        $null = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $attempt
        $pre = Get-PageHrefSnapshot $sid
      }
      if (-not ($pre.ok -and (Test-IsProductManageUrl $pre.href) -and -not (Test-IsForbiddenNonProductUrl $pre.href))) {
        $lastErr = ("not on product page before scrape. href={0}" -f $(if ($pre.href) { $pre.href } else { '(unknown)' }))
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        if ($attempt -lt $retries) {
          try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
          Start-Sleep -Seconds 4
          Open-ProductStore -sid $sid -productUrl $productUrl -cfg $cfg -waitOpenMs ([Math]::Max($waitOpen, 45000)) | Out-Null
        }
        continue
      }

      Write-Step ("  scrape attempt {0}/{1} (page 1)..." -f $attempt, $retries)
      $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $scrapeOneLine, '--timeout', '90000')
      if (Test-ZiniaoBridgeError $execOut) {
        $lastErr = 'Bridge disconnected on page exec'
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        if ($attempt -lt $retries) {
          Start-Sleep -Seconds 12
          [void](Wait-ZiniaoBridgeReady -MaxSec 40)
          Write-Step '  re-open store after Bridge fail...'
          try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
          Start-Sleep -Seconds 4
          Open-ProductStore -sid $sid -productUrl $productUrl -cfg $cfg -waitOpenMs ([Math]::Max($waitOpen, 45000)) | Out-Null
        }
        continue
      }
      if ([string]::IsNullOrWhiteSpace($execOut)) {
        $lastErr = 'page exec empty stdout'
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        if ($attempt -lt $retries) {
          Start-Sleep -Seconds 15
        }
        continue
      }
      $payload = Get-ScrapePayload $execOut
      $pageUrl = ''
      if ($payload -and $payload.url) { $pageUrl = [string]$payload.url }

      # 硬拒绝：订单/健康等页即使刮到“像商品”的行也不收
      if ($pageUrl -and (Test-IsForbiddenNonProductUrl $pageUrl)) {
        $lastErr = ("scrape on forbidden URL (refuse ingest): {0}" -f $pageUrl)
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        $rawRows = @()
        if ($attempt -lt $retries) {
          $null = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $attempt
        }
        continue
      }
      if ($pageUrl -and -not (Test-IsProductManageUrl $pageUrl)) {
        $lastErr = ("scrape URL is not product/manage: {0}" -f $pageUrl)
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        $rawRows = @()
        if ($attempt -lt $retries) {
          $null = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $attempt
        }
        continue
      }
      if ($payload -and $payload.error -and ("$($payload.error)" -match '(?i)wrong[_ ]?page|not product|order page|forbidden')) {
        $lastErr = [string]$payload.error
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        $rawRows = @()
        if ($attempt -lt $retries) {
          $null = Invoke-ProductPageRecover -sid $sid -productUrl $productUrl -attempt $attempt
        }
        continue
      }

      if ($payload -and $payload.ok -and $payload.rows) {
        $pageRows = @($payload.rows)
        foreach ($r in $pageRows) {
          $prodKey = ''
          if ($r.productId) { $prodKey = [string]$r.productId }
          elseif ($r.product_id) { $prodKey = [string]$r.product_id }
          elseif ($r.sellerSku) { $prodKey = "sku:$([string]$r.sellerSku)" }
          elseif ($r.seller_sku) { $prodKey = "sku:$([string]$r.seller_sku)" }
          if (-not $prodKey -or $seenIds.ContainsKey($prodKey)) { continue }
          $seenIds[$prodKey] = $true
          $rawRows += $r
        }
        if ($rawRows.Count -gt 0) { $lastErr = $null; $pagesDone = 1; break }
        $lastErr = '0 product rows'
        Write-Step '  attempt: 0 product rows after parse'
      } else {
        $lastErr = if ($payload -and $payload.error) { [string]$payload.error } else { 'scrape failed / unparseable exec' }
        Write-Step ("  attempt fail: {0}" -f $lastErr)
        try {
          $rawPath = Join-Path $script:logsDir ("products-exec-raw-{0}-a{1}.txt" -f $sid, $attempt)
          Set-Content -LiteralPath $rawPath -Value $execOut -Encoding UTF8
        } catch { }
        if ($lastErr -match 'about:blank' -or ($payload -and "$($payload.url)" -match 'about:blank')) {
          Write-Step '  about:blank — full reopen'
          try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
          Start-Sleep -Seconds 4
          Open-ProductStore -sid $sid -productUrl $productUrl -cfg $cfg -waitOpenMs ([Math]::Max($waitOpen, 35000)) | Out-Null
          continue
        }
      }
      if ($attempt -lt $retries -and $rawRows.Count -eq 0) {
        Write-Step '  wait 18s and retry scrape'
        Start-Sleep -Seconds 18
      }
    }
    if ($lastErr -or $rawRows.Count -eq 0) { throw $(if ($lastErr) { $lastErr } else { '0 rows' }) }

    Write-Step ("  page 1 unique products={0}" -f $rawRows.Count)

    # 翻页（可选）
    if ($productMaxPages -gt 1 -and $clickNextOneLine) {
      for ($page = 2; $page -le $productMaxPages; $page++) {
        Write-Step ("  click next for page {0}..." -f $page)
        $nextOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $clickNextOneLine, '--timeout', '30000')
        $nextPayload = Get-ScrapePayload $nextOut
        $hasNext = $false
        if ($nextPayload -and $nextPayload.ok -and $nextPayload.clicked) { $hasNext = $true }
        elseif ($nextPayload -and $nextPayload.hasNext -eq $false) {
          Write-Step ("  no more pages: {0}" -f $(if ($nextPayload.error) { $nextPayload.error } else { 'end' }))
          break
        } else {
          if ($nextOut -match '"clicked"\s*:\s*true') { $hasNext = $true }
          else {
            Write-Step '  stop paging: cannot click next'
            break
          }
        }
        if (-not $hasNext) { break }

        Start-Sleep -Milliseconds $productPageWaitMs
        $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $scrapeOneLine, '--timeout', '60000')
        $pagePayload = Get-ScrapePayload $execOut
        if (-not ($pagePayload -and $pagePayload.ok -and $pagePayload.rows)) {
          Write-Step ("  page {0} scrape empty — stop paging" -f $page)
          break
        }
        $added = 0
        foreach ($r in @($pagePayload.rows)) {
          $prodKey = ''
          if ($r.productId) { $prodKey = [string]$r.productId }
          elseif ($r.product_id) { $prodKey = [string]$r.product_id }
          elseif ($r.sellerSku) { $prodKey = "sku:$([string]$r.sellerSku)" }
          if (-not $prodKey -or $seenIds.ContainsKey($prodKey)) { continue }
          $seenIds[$prodKey] = $true
          $rawRows += $r
          $added++
        }
        $pagesDone++
        $payload = $pagePayload
        Write-Step ("  page {0} new={1} unique total={2}" -f $page, $added, $rawRows.Count)
        if ($added -eq 0) { break }
      }
    } elseif ($productMaxPages -gt 1 -and -not $clickNextOneLine) {
      Write-Step '  WARN products-click-next.js missing — only first page'
    }

    $item.rows = $rawRows.Count
    Write-Step ("  scraped {0} product rows source={1} pages={2}" -f $rawRows.Count, $(if ($payload.source) { $payload.source } else { '?' }), $pagesDone)

    # save debug（完整 rows，便于校准）
    $dbg = Join-Path $script:logsDir ("products-debug-{0}-{1}.json" -f $sid, $script:runStamp)
    (@{
      storeId = $sid; displayName = $display; url = $productUrl
      rowCount = $rawRows.Count; pages = $pagesDone
      payloadMeta = @{
        ok = $(if ($payload) { $payload.ok } else { $null })
        source = $(if ($payload) { $payload.source } else { $null })
        headers = $(if ($payload) { $payload.headers } else { $null })
        colMap = $(if ($payload) { $payload.colMap } else { $null })
        currency = $(if ($payload) { $payload.currency } else { $null })
      }
      sampleRows = @($rawRows | Select-Object -First 5)
    } | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $dbg -Encoding UTF8

    $currency = 'GBP'
    if ($payload.currency) { $currency = [string]$payload.currency }
    $srcUrl = $productUrl
    if ($payload.url) { $srcUrl = [string]$payload.url }
    if ($pageUrl) { $srcUrl = $pageUrl }

    # 最终门禁：source_url 必须是商品页，否则整店失败且不上传
    if (Test-IsForbiddenNonProductUrl $srcUrl -or -not (Test-IsProductManageUrl $srcUrl)) {
      throw ("refuse ingest: final page is not product/manage. url={0} rows={1}" -f $srcUrl, $rawRows.Count)
    }

    if ((Get-Command Send-QingquanIngest -ErrorAction SilentlyContinue) -and $cfg.qingquan -and $cfg.qingquan.enabled) {
      if ($useDryRun) {
        Write-Step ("  qingquan dryRun: would report {0} products" -f $rawRows.Count)
      } else {
        $collectedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00')
        $qqItems = ConvertTo-QingquanProductIngestItems -Rows $rawRows -CollectedAt $collectedAt `
          -StoreId $sid -StoreName $display -Currency $currency -SourceUrl $srcUrl
        Write-Step ("  report Qingquan tiktok_products items={0} url={1}..." -f $qqItems.Count, $srcUrl)
        $qq = Send-QingquanIngest -Config $cfg -Items $qqItems -Source 'tiktok_products'
        $item.qingquanAccepted = $qq.accepted
        $item.qingquanDup = $qq.duplicated
        if ($qq.error) { $item.error = [string]$qq.error }
        Write-Step ("  qingquan accepted={0} dup={1} failed={2} ok={3}" -f $qq.accepted, $qq.duplicated, $qq.failed, $qq.ok)
      }
    } else {
      Write-Step '  skip qingquan (disabled or client missing)'
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

Write-Step '======== PRODUCTS SUMMARY ========'
$summary | Format-Table storeName, displayName, ok, rows, qingquanAccepted, qingquanDup, error -AutoSize
$okN = @($summary | Where-Object { $_.ok }).Count
Write-Step ("OK {0}/{1}" -f $okN, $summary.Count)
$sumPath = Join-Path $script:logsDir ("products-summary-{0}.json" -f $script:runStamp)
($summary | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $sumPath -Encoding UTF8
Write-Step ("summary: {0}" -f $sumPath)
Write-Step '===== products multi-store END ====='
