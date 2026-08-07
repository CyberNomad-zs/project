# Backfill product seller_sku by searching product_id on manage page.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\fill-product-skus.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\fill-product-skus.ps1 -CsvPath .\logs\missing-product-sku.csv

param(
  [string]$ConfigPath = "",
  [string]$CsvPath = "",
  [int]$DetailWaitMs = 2800,
  [string]$OnlyStoreId = "",
  [string]$DryRun = ""
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $root 'config\stores.config.json' }
if (-not $CsvPath) { $CsvPath = Join-Path $root 'logs\missing-product-sku.csv' }
if (-not (Test-Path $ConfigPath)) { throw "Missing config: $ConfigPath" }
if (-not (Test-Path $CsvPath)) { throw "Missing CSV: $CsvPath" }

$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$qingquanLib = Join-Path $PSScriptRoot 'qingquan-client.ps1'
if (Test-Path $qingquanLib) { . $qingquanLib }
$ziniaoWinLib = Join-Path $PSScriptRoot 'ziniao-window.ps1'
if (-not (Test-Path $ziniaoWinLib)) { throw "Missing $ziniaoWinLib" }
. $ziniaoWinLib

$script:logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $script:logsDir | Out-Null
$script:runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$script:runLogFile = Join-Path $script:logsDir ("fill-product-sku-{0}.log" -f $script:runStamp)

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
  if ($stderr -and $stderr.Trim()) { Write-RunLog ("ziniao stderr: {0}" -f $stderr.Trim()) }
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
function Wait-ZiniaoBridgeReady([int]$MaxSec = 60) {
  $deadline = (Get-Date).AddSeconds($MaxSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $tnc = Test-NetConnection -ComputerName '127.0.0.1' -Port 9481 -WarningAction SilentlyContinue
      if ($tnc -and $tnc.TcpTestSucceeded) { return $true }
    } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}
function Get-ProductsUrl($store, $cfg) {
  $plat = ''
  if ($store.platformName) { $plat = [string]$store.platformName }
  elseif ($store.platform) { $plat = [string]$store.platform }
  if ($cfg.productUrl -and $cfg.productUrl.byPlatform -and $plat) {
    foreach ($p in $cfg.productUrl.byPlatform.PSObject.Properties) {
      if ($plat -eq [string]$p.Name -or $plat -like ("*{0}*" -f $p.Name)) {
        return [string]$p.Value
      }
    }
  }
  if ($cfg.productUrl -and $cfg.productUrl.default) { return [string]$cfg.productUrl.default }
  if ($cfg.urls -and $cfg.urls.products) { return [string]$cfg.urls.products }
  return 'https://seller-uk.tiktok.com/product/manage?shop_region=GB'
}
function Get-DisplayName($store, $map) {
  $n = [string]$store.storeName
  if ($map -and $map.PSObject.Properties.Name -contains $n) { return [string]$map.$n }
  return $n
}

# Search product_id on manage page, expand SKU, parse seller SKUs from row DOM text.
$searchJsTemplate = @'
(function(){
  var TARGET="__PRODUCT_ID__";
  function clean(t){return String(t==null?"":t).replace(/\s+/g," ").trim();}
  function isNoise(s){
    s=clean(s);
    if(!s) return true;
    if(/\d+\s*个\s*SKU/i.test(s)) return true;
    if(/SKU\s*展开|展开\s*全部|Expand\s+\d+\s+SKU/i.test(s)) return true;
    if(/浏览|销售额|分析|已售出/i.test(s) && s.length>40) return true;
    return false;
  }
  function sanitizeSku(raw){
    var sku=clean(raw);
    if(!sku) return "";
    sku=sku.replace(/(?:--)?浏览次数.*$/i,"");
    sku=sku.replace(/(?:--)?销售额.*$/i,"");
    sku=sku.replace(/已售出.*$/i,"");
    sku=sku.replace(/(?:--)?分析.*$/i,"");
    sku=sku.replace(/(?:--)?在售.*$/i,"");
    sku=sku.replace(/--.*$/,"");
    var m=sku.match(/^([A-Za-z0-9][A-Za-z0-9_\-*]{1,48})/);
    sku=m?m[1]:clean(sku).slice(0,48);
    if(!sku||isNoise(sku)||/展开|全部|批量|浏览|销售|分析|已售出/i.test(sku)) return "";
    if(sku.length<2) return "";
    if(/^(black|white|pink|gray|grey|green|purple|red|blue|yellow)$/i.test(sku)) return "";
    return sku;
  }
  function extractSkus(text){
    var s=clean(text);
    if(!s||isNoise(s)) return [];
    var out=[], seen={};
    var re=/(?:商家\s*|Seller\s*|卖家\s*)?SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9_\-*]{1,48})/gi;
    var m;
    while((m=re.exec(s))){
      var sku=sanitizeSku(m[1]);
      if(!sku||seen[sku]) continue;
      seen[sku]=true; out.push(sku);
    }
    return out;
  }
  function visible(el){
    if(!el) return false;
    var r=el.getBoundingClientRect();
    if(r.width<2||r.height<2) return false;
    var st=window.getComputedStyle(el);
    return st && st.visibility!=="hidden" && st.display!=="none";
  }
  function findSearchInput(){
    var sels=[
      'input[placeholder*="搜索"]','input[placeholder*="Search"]','input[placeholder*="ID"]',
      'input[type="search"]','input[type="text"]'
    ];
    for(var i=0;i<sels.length;i++){
      var list=document.querySelectorAll(sels[i]);
      for(var j=0;j<list.length;j++){
        if(!visible(list[j])) continue;
        var ph=(list[j].getAttribute("placeholder")||"")+(list[j].getAttribute("aria-label")||"");
        if(/搜索|Search|商品|ID|SKU|Product/i.test(ph) || sels[i].indexOf("search")>=0) return list[j];
      }
    }
    // fallback: first visible text input in header area
    var inputs=document.querySelectorAll("input");
    for(var k=0;k<inputs.length;k++){
      if(visible(inputs[k]) && (inputs[k].type==="text"||inputs[k].type==="search"||!inputs[k].type)) return inputs[k];
    }
    return null;
  }
  function setInput(el, val){
    el.focus();
    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,"value");
    if(setter&&setter.set) setter.set.call(el,val); else el.value=val;
    el.dispatchEvent(new Event("input",{bubbles:true}));
    el.dispatchEvent(new Event("change",{bubbles:true}));
    // try react-ish
    try{ el.dispatchEvent(new InputEvent("input",{bubbles:true,data:val,inputType:"insertText"})); }catch(e){}
  }
  function clickSearch(){
    var nodes=document.querySelectorAll("button,a,[role=button],span");
    for(var i=0;i<nodes.length;i++){
      var t=clean(nodes[i].textContent||nodes[i].getAttribute("aria-label")||"");
      if(!t||t.length>12) continue;
      if(/^(搜索|查询|Search|Go)$/i.test(t) || /search/i.test(t)){
        if(visible(nodes[i])){ try{nodes[i].click(); return t;}catch(e){} }
      }
    }
    return "";
  }
  function expandIn(scope){
    var clicked=0;
    var nodes=(scope||document).querySelectorAll("button,a,span,div,[role=button]");
    for(var i=0;i<nodes.length;i++){
      var tx=clean(nodes[i].textContent);
      if(!tx||tx.length>28) continue;
      if(!(/\d+\s*个\s*SKU\s*展开/.test(tx)||/^SKU\s*展开$/i.test(tx)||/Expand\s+\d+\s+SKU/i.test(tx))) continue;
      try{ nodes[i].click(); clicked++; }catch(e){}
      if(clicked>=8) break;
    }
    if(clicked>0){ var until=Date.now()+700; while(Date.now()<until){} }
    return clicked;
  }
  try{
    var href=String(location.href||"");
    if(!/\/product\/manage/i.test(href)){
      return JSON.stringify({ok:false,error:"not_product_manage",href:href,productId:TARGET});
    }
    var input=findSearchInput();
    if(!input){
      return JSON.stringify({ok:false,error:"no_search_input",href:href,productId:TARGET,tlen:((document.body&&document.body.innerText)||"").length});
    }
    setInput(input, TARGET);
    var btn=clickSearch();
    // Enter
    try{
      input.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",code:"Enter",keyCode:13,which:13,bubbles:true}));
      input.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",code:"Enter",keyCode:13,which:13,bubbles:true}));
    }catch(e){}
    var until=Date.now()+1600; while(Date.now()<until){}
    var exp=expandIn(document);
    until=Date.now()+600; while(Date.now()<until){}
    // find row containing product id
    var rows=Array.prototype.slice.call(document.querySelectorAll("tr,div,li,section"));
    var hit=null, hitText="";
    for(var r=0;r<rows.length;r++){
      var t=clean(rows[r].textContent||"");
      if(t.indexOf(TARGET)<0) continue;
      if(t.length<20||t.length>2500) continue;
      hit=rows[r]; hitText=t; break;
    }
    if(!hit){
      // body fallback
      var body=clean((document.body&&document.body.innerText)||"");
      if(body.indexOf(TARGET)<0){
        return JSON.stringify({ok:false,error:"product_not_found",productId:TARGET,href:href,searchBtn:btn,expand:exp});
      }
      hitText=body;
    } else {
      expandIn(hit);
      until=Date.now()+500; while(Date.now()<until){}
      hitText=clean(hit.textContent||"");
    }
    var skus=extractSkus(hitText);
    // also scan nearby after expand
    if(!skus.length && hit){
      var parent=hit.parentElement;
      if(parent) skus=extractSkus(parent.textContent||"");
    }
    var name="";
    var nm=hitText.replace(new RegExp(TARGET,"g")," ").replace(/ID\s*[:：]\s*\d+/gi," ");
    nm=nm.replace(/(?:商家\s*|Seller\s*|卖家\s*)?SKU\s*[:：]\s*[A-Za-z0-9_\-*]+/gi," ");
    nm=nm.replace(/\d+\s*个\s*SKU\s*展开?/gi," ");
    name=clean(nm).slice(0,120);
    var st="";
    var sm=hitText.match(/(在售|已下架|草稿|在线|审核中|Active|Inactive|Draft)/);
    if(sm) st=sm[1];
    var sellerSku=skus.length===1?skus[0]:(skus.length?skus.join("|"):"");
    return JSON.stringify({
      ok:true,
      productId:TARGET,
      productName:name,
      sellerSku:sellerSku,
      sellerSkus:skus,
      status:st,
      searchBtn:btn,
      expand:exp,
      found:hitText.indexOf(TARGET)>=0,
      snippet:hitText.slice(0,220),
      href:href
    });
  }catch(err){
    return JSON.stringify({ok:false,error:String(err&&err.message||err),productId:TARGET});
  }
})()
'@

# load targets
$allRows = @(Import-Csv -LiteralPath $CsvPath)
$allRows = @($allRows | Where-Object {
  $_.shop_external_id -and $_.product_id -and ([string]$_.product_id -match '^\d{15,22}$')
})
if ($OnlyStoreId) {
  $allRows = @($allRows | Where-Object { [string]$_.shop_external_id -eq $OnlyStoreId })
}
Write-Step '===== fill product SKU START ====='
Write-Step ("csv={0} targets={1}" -f $CsvPath, $allRows.Count)
if ($allRows.Count -eq 0) { Write-Step 'nothing to do'; return }

$dry = $false
if ($DryRun -eq 'true' -or $DryRun -eq '1') { $dry = $true }
elseif ($DryRun -eq 'false' -or $DryRun -eq '0') { $dry = $false }
elseif ($cfg.options -and $null -ne $cfg.options.dryRun) { $dry = [bool]$cfg.options.dryRun }

# map store meta from live list
$listOut = Invoke-Ziniao @('store', 'list')
$listPayload = $null
try {
  $lj = $listOut | ConvertFrom-Json
  if ($lj.data -and $lj.data.items) { $listPayload = @($lj.data.items) }
  elseif ($lj.data -and $lj.data.list) { $listPayload = @($lj.data.list) }
  elseif ($lj.items) { $listPayload = @($lj.items) }
} catch { }
$storeById = @{}
foreach ($s in @($listPayload)) {
  $sid = ''
  if ($s.storeId) { $sid = [string]$s.storeId } elseif ($s.id) { $sid = [string]$s.id }
  if ($sid) { $storeById[$sid] = $s }
}

$groups = $allRows | Group-Object shop_external_id
$summary = @()
$buffer = New-Object System.Collections.Generic.List[object]

function Flush-Buffer {
  param([string]$reason)
  if ($buffer.Count -eq 0) { return }
  if ($dry) {
    Write-Step ("  dryRun skip flush n={0} ({1})" -f $buffer.Count, $reason)
    $buffer.Clear()
    return
  }
  if (-not (Get-Command Send-QingquanIngest -ErrorAction SilentlyContinue)) {
    Write-Step '  no Send-QingquanIngest'
    return
  }
  Write-Step ("  flush products n={0} ({1})..." -f $buffer.Count, $reason)
  $items = @($buffer.ToArray())
  $buffer.Clear()
  $resp = $null
  for ($t = 1; $t -le 3; $t++) {
    try {
      $resp = Send-QingquanIngest -Config $cfg.qingquan -Source 'tiktok_products' -Items $items
      break
    } catch {
      Write-Step ("  flush try {0} err: {1}" -f $t, $_)
      Start-Sleep -Seconds (3 * $t)
    }
  }
  if ($resp) {
    Write-Step ("  flush result accepted={0} dup={1} failed={2}" -f $resp.accepted, $resp.duplicate, $resp.failed)
  } else {
    Write-Step '  flush FAILED'
  }
}

foreach ($g in $groups) {
  $sid = [string]$g.Name
  $store = $storeById[$sid]
  if (-not $store) {
    Write-Step ("SKIP store {0}: not in store list" -f $sid)
    $summary += [pscustomobject]@{ storeId = $sid; planned = $g.Count; ok = 0; fail = $g.Count; error = 'not_in_list' }
    continue
  }
  $sname = ''
  if ($store.storeName) { $sname = [string]$store.storeName } elseif ($store.name) { $sname = [string]$store.name }
  $display = Get-DisplayName ([pscustomobject]@{ storeName = $sname }) $cfg.storeNameMap
  $productUrl = Get-ProductsUrl ([pscustomobject]@{
      platformName = $(if ($store.platformName) { $store.platformName } elseif ($store.platform) { $store.platform } else { '' })
      platform = $(if ($store.platform) { $store.platform } else { '' })
    }) $cfg
  $targets = @($g.Group)
  Write-Step ("==== FILL {0} ({1}) n={2} ====" -f $display, $sid, $targets.Count)
  Write-Step '  open store...'
  [void](Wait-ZiniaoBridgeReady -MaxSec 30)
  $openArgs = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $productUrl -Config $cfg
  $null = Invoke-Ziniao $openArgs
  Start-Sleep -Seconds 18
  try {
    Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} -Config $cfg | Out-Null
  } catch { Write-Step ("  maximize soft-fail: {0}" -f $_) }
  # ensure manage url
  $null = Invoke-Ziniao @('page', 'visit', '--store-id', $sid, '--url', $productUrl, '--wait-until', 'load', '--timeout', '90000')
  Start-Sleep -Seconds 6

  $okN = 0; $failN = 0; $withSkuN = 0
  $i = 0
  foreach ($row in $targets) {
    $i++
    $productId = [string]$row.product_id
    Write-Step ("  search [{0}/{1}] {2}" -f $i, $targets.Count, $productId)
    $js = $searchJsTemplate.Replace('__PRODUCT_ID__', $productId)
    $one = ConvertTo-ScrapeOneLine $js
    [void](Wait-ZiniaoBridgeReady -MaxSec 20)
    $execOut = Invoke-Ziniao @('page', 'exec', '--store-id', $sid, '--script', $one, '--timeout', '45000')
    Start-Sleep -Milliseconds $DetailWaitMs
    $payload = Get-ScrapePayload $execOut
    if (-not $payload -or -not $payload.ok) {
      $err = if ($payload -and $payload.error) { [string]$payload.error } else { 'parse_fail' }
      Write-Step ("    fail: {0}" -f $err)
      $failN++
      continue
    }
    $sku = [string]$payload.sellerSku
    $skus = @()
    if ($payload.sellerSkus) { $skus = @($payload.sellerSkus | ForEach-Object { [string]$_ } | Where-Object { $_ }) }
    if (-not $sku -and $skus.Count) { $sku = if ($skus.Count -eq 1) { $skus[0] } else { $skus -join '|' } }
    if ($sku) {
      $withSkuN++
      $okN++
      Write-Step ("    sku={0}" -f $sku)
      $item = [ordered]@{
        shop_id = $sid
        shop_external_id = $sid
        shop_name = $display
        product_id = $productId
        product_name = $(if ($payload.productName) { [string]$payload.productName } elseif ($row.product_name) { [string]$row.product_name } else { $null })
        seller_sku = $sku
        seller_skus = $skus
        status = $(if ($payload.status) { [string]$payload.status } elseif ($row.status) { [string]$row.status } else { $null })
        source_url = $(if ($payload.href) { [string]$payload.href } else { $productUrl })
        collected_at = (Get-Date).ToUniversalTime().ToString('o')
      }
      $buffer.Add([pscustomobject]$item) | Out-Null
      if ($buffer.Count -ge 15) { Flush-Buffer 'batch' }
    } else {
      $okN++  # page ok but no sku text
      Write-Step ("    no_sku found={0} snip={1}" -f $payload.found, ([string]$payload.snippet).Substring(0, [Math]::Min(80, ([string]$payload.snippet).Length)))
    }
  }
  Flush-Buffer 'store-end'
  try { $null = Invoke-Ziniao @('store', 'close', '--id', $sid) } catch { }
  $summary += [pscustomobject]@{
    storeId = $sid; displayName = $display; planned = $targets.Count
    detailOk = $okN; detailFail = $failN; withSku = $withSkuN; error = $null
  }
}

$summaryPath = Join-Path $script:logsDir ("fill-product-sku-summary-{0}.json" -f $script:runStamp)
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Step '======== FILL PRODUCT SKU SUMMARY ========'
Write-Step ("summary: {0}" -f $summaryPath)
$summary | ForEach-Object {
  Write-Step ("  {0} planned={1} ok={2} fail={3} withSku={4}" -f $_.displayName, $_.planned, $_.detailOk, $_.detailFail, $_.withSku)
}
Write-Step '===== fill product SKU END ====='
