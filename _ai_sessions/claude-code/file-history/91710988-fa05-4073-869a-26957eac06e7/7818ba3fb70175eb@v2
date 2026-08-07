# One-shot probe: product SKU expand UI + order detail link shape
param(
  [string]$StoreId = '27328767468273',
  [string]$ProductUrl = 'https://seller-uk.tiktok.com/product/manage',
  [string]$OrderUrl = 'https://seller-uk.tiktok.com/order?selected_sort=6&tab=all'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$probeSku = Get-Content (Join-Path $PSScriptRoot '_probe-sku-expand.js') -Raw -Encoding UTF8

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
    if ($null -ne $j.ok -or $null -ne $j.url) { return $j }
  } catch {}
  $m = [regex]::Matches($execOut, '\{(?:[^{}]|(?<o>\{)|(?<-o>\}))+(?(o)(?!))\}')
  if ($m.Count -gt 0) {
    try { return ($m[$m.Count - 1].Value | ConvertFrom-Json) } catch {}
  }
  return $null
}

Write-Host 'open store...'
$null = Invoke-Ziniao @('store', 'open', '--id', $StoreId, '--url', $ProductUrl, '--wait-until', 'domcontentloaded', '--timeout', '90000')
Start-Sleep -Seconds 12
Write-Host 'probe product page...'
$one = ConvertTo-ScrapeOneLine $probeSku
$out1 = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', $one, '--timeout', '60000')
$p1 = Get-ScrapePayload $out1
$p1Path = Join-Path $logs ("sku-expand-probe-product-{0}-{1}.json" -f $StoreId, $stamp)
($p1 | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $p1Path -Encoding UTF8
Write-Host ("product probe -> {0}" -f $p1Path)

# try click first expand-like control then re-probe
$clickExpand = @'
(function(){
  function clean(t){return String(t||'').replace(/\s+/g,' ').trim()}
  var nodes = Array.prototype.slice.call(document.querySelectorAll('button,a,span,div'));
  for (var i=0;i<nodes.length;i++){
    var el=nodes[i];
    var tx=clean(el.textContent);
    if (!tx || tx.length>24) continue;
    if (/\d+\s*个\s*SKU\s*展开|SKU\s*展开/i.test(tx)) {
      try { el.click(); return JSON.stringify({ok:true, clicked:tx, tag:el.tagName, cls:String(el.className||'').slice(0,80)}); }
      catch(e){ return JSON.stringify({ok:false,error:String(e&&e.message||e), text:tx}); }
    }
  }
  return JSON.stringify({ok:false,error:'no expand control'});
})();
'@
$outClick = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', (ConvertTo-ScrapeOneLine $clickExpand), '--timeout', '30000')
$clickPayload = Get-ScrapePayload $outClick
($clickPayload | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $logs ("sku-expand-click-{0}-{1}.json" -f $StoreId, $stamp)) -Encoding UTF8
Start-Sleep -Seconds 2
$out2 = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', $one, '--timeout', '60000')
$p2 = Get-ScrapePayload $out2
($p2 | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath (Join-Path $logs ("sku-expand-after-click-{0}-{1}.json" -f $StoreId, $stamp)) -Encoding UTF8

Write-Host 'visit orders...'
$null = Invoke-Ziniao @('page', 'visit', '--store-id', $StoreId, '--url', $OrderUrl, '--wait-until', 'domcontentloaded', '--timeout', '90000')
Start-Sleep -Seconds 10

$orderProbe = @'
(function(){
  function clean(t){return String(t==null?'':t).replace(/\s+/g,' ').trim()}
  var out={url:location.href,title:document.title||'',orderLinks:[],rowSamples:[],detailCandidates:[]};
  var as=document.querySelectorAll('a[href]');
  for(var i=0;i<as.length && out.orderLinks.length<30;i++){
    var h=as[i].href||'';
    if(/order/i.test(h)) out.orderLinks.push({href:h.slice(0,180),text:clean(as[i].textContent).slice(0,40)});
  }
  var trs=document.querySelectorAll('table tr');
  for(var r=0;r<Math.min(trs.length,6);r++){
    var tds=trs[r].querySelectorAll('td,th');
    var cells=[], hrefs=[];
    for(var c=0;c<Math.min(tds.length,10);c++){
      cells.push(clean(tds[c].textContent).slice(0,60));
      var a=tds[c].querySelector('a[href]');
      if(a) hrefs.push((a.href||'').slice(0,160));
    }
    // clickable product cell?
    var clickables=[];
    var btns=trs[r].querySelectorAll('button,a,[role=button],.cursor-pointer');
    for(var b=0;b<Math.min(btns.length,6);b++){
      clickables.push({tag:btns[b].tagName,text:clean(btns[b].textContent).slice(0,30),cls:String(btns[b].className||'').slice(0,60)});
    }
    out.rowSamples.push({cells:cells,hrefs:hrefs,clickables:clickables});
  }
  // any drawer / detail markers
  var body=clean((document.body&&document.body.innerText)||'').slice(0,2000);
  out.bodyHasSku=/SKU/i.test(body);
  out.bodyPreview=body.slice(0,500);
  return JSON.stringify(out);
})();
'@
$out3 = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', (ConvertTo-ScrapeOneLine $orderProbe), '--timeout', '60000')
$p3 = Get-ScrapePayload $out3
$p3Path = Join-Path $logs ("sku-order-probe-{0}-{1}.json" -f $StoreId, $stamp)
($p3 | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $p3Path -Encoding UTF8
Write-Host ("order probe -> {0}" -f $p3Path)

# click first product cell "N 件商品" to open detail drawer if any
$clickOrderItem = @'
(function(){
  function clean(t){return String(t||'').replace(/\s+/g,' ').trim()}
  var nodes=Array.prototype.slice.call(document.querySelectorAll('td,a,button,div,span'));
  for(var i=0;i<nodes.length;i++){
    var el=nodes[i];
    var tx=clean(el.textContent);
    if(/^\d+\s*件商品$/.test(tx) || /^\d+\s*item/i.test(tx)){
      try{
        el.click();
        return JSON.stringify({ok:true,clicked:tx,tag:el.tagName,cls:String(el.className||'').slice(0,80)});
      }catch(e){return JSON.stringify({ok:false,error:String(e&&e.message||e)});}
    }
  }
  // fallback: click order id link
  var a=document.querySelector('a[href*="order"]');
  if(a){ try{a.click(); return JSON.stringify({ok:true,clicked:'order-link',href:(a.href||'').slice(0,160)});}catch(e){} }
  return JSON.stringify({ok:false,error:'no product cell'});
})();
'@
$out4 = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', (ConvertTo-ScrapeOneLine $clickOrderItem), '--timeout', '30000')
$clickOrd = Get-ScrapePayload $out4
($clickOrd | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $logs ("sku-order-click-{0}-{1}.json" -f $StoreId, $stamp)) -Encoding UTF8
Start-Sleep -Seconds 3

$detailProbe = @'
(function(){
  function clean(t){return String(t==null?'':t).replace(/\s+/g,' ').trim()}
  var out={url:location.href,title:document.title||'',skuHits:[],lines:[],dialogs:[]};
  var body=clean((document.body&&document.body.innerText)||'');
  out.bodyLen=body.length;
  var re=/(?:商家\s*)?SKU\s*[:：]?\s*([A-Za-z0-9_\-]{3,40})/gi; var m;
  while((m=re.exec(body)) && out.skuHits.length<30){ out.skuHits.push(m[1]); }
  // common drawer/modal
  var mods=document.querySelectorAll('[role=dialog],.arco-drawer,.arco-modal,.semi-sidesheet,.tiktok-drawer,aside,[class*="drawer"],[class*="Drawer"]');
  for(var i=0;i<Math.min(mods.length,5);i++){
    var t=clean(mods[i].textContent).slice(0,800);
    out.dialogs.push({cls:String(mods[i].className||'').slice(0,80),text:t});
  }
  // try parse product blocks
  var blocks=body.split(/(?=ID\s*[:：]\s*\d{10,}|SKU\s*[:：])/i);
  for(var b=0;b<Math.min(blocks.length,12);b++){
    var s=clean(blocks[b]).slice(0,300);
    if(/SKU|ID\s*[:：]/i.test(s)) out.lines.push(s);
  }
  out.bodyPreview=body.slice(0,1000);
  return JSON.stringify(out);
})();
'@
$out5 = Invoke-Ziniao @('page', 'exec', '--store-id', $StoreId, '--script', (ConvertTo-ScrapeOneLine $detailProbe), '--timeout', '60000')
$p5 = Get-ScrapePayload $out5
($p5 | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath (Join-Path $logs ("sku-order-detail-{0}-{1}.json" -f $StoreId, $stamp)) -Encoding UTF8
Write-Host ("detail probe -> logs/sku-order-detail-{0}-{1}.json" -f $StoreId, $stamp)

try { $null = Invoke-Ziniao @('store', 'close', '--id', $StoreId) } catch {}
Write-Host 'DONE'
