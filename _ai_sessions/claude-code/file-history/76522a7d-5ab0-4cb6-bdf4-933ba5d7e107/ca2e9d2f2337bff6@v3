# P2.1b: direct visit video-details URL + long wait + tab clicks + deep probe
# Confirmed path from click POC: /compass/video-analytics/video-details
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-video-details-deep.ps1

param(
  [string]$StoreId = "27501502216807",
  [string]$DetailUrl = "https://seller-uk.tiktok.com/compass/video-analytics/video-details?shop_region=GB"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path $PSScriptRoot -Parent
$logsDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$LabelAll = -join [char[]](0x5168, 0x90E8)  # 全部
$LabelBound = (-join [char[]](0x5DF2, 0x7ED1, 0x5B9A, 0x7684, 0x8D26, 0x53F7))  # 已绑定的账号
$LabelAffiliate = (-join [char[]](0x8054, 0x76DF, 0x8D26, 0x53F7))  # 联盟账号
$LabelNeed = (-join [char[]](0x9700, 0x8981, 0x5173, 0x6CE8))  # 需要关注

function Write-Step([string]$msg) { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) }
function ConvertTo-ProcessArgument([string]$s) {
  if ($null -eq $s) { return '""' }
  if ($s -match '[\s"]') { return '"' + ($s -replace '"', '\"') + '"' }
  return $s
}
function Initialize-ZiniaoCli {
  if ($script:ZiniaoNode) { return }
  $node = (Get-Command node -ErrorAction SilentlyContinue).Source
  if (-not $node) { throw "node not found" }
  $runJs = Join-Path $env:APPDATA "npm\node_modules\@ziniao-open\cli\scripts\run.js"
  if (-not (Test-Path $runJs)) { throw "ziniao-cli run.js not found" }
  $script:ZiniaoNode = $node
  $script:ZiniaoRunJs = $runJs
}
function Invoke-Ziniao([string[]]$CliArgs) {
  Initialize-ZiniaoCli
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  $allArgs = @($script:ZiniaoRunJs) + @($CliArgs)
  $argLine = ($allArgs | ForEach-Object { ConvertTo-ProcessArgument ([string]$_) }) -join " "
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
  return (($js -replace "(?m)^\s*//.*$", "" -replace "\r?\n", " " -replace "\s+", " ").Trim())
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
  $m = [regex]::Matches($execOut, "\{(?:[^{}]|(?<o>\{)|(?<-o>\}))+(?(o)(?!))\}")
  if ($m.Count -gt 0) {
    try { return ($m[$m.Count - 1].Value | ConvertFrom-Json) } catch { }
  }
  return $null
}
function Write-Utf8File([string]$Path, [string]$Content) {
  [System.IO.File]::WriteAllText($Path, [string]$Content, [System.Text.UTF8Encoding]::new($false))
}
function Invoke-PageExec([string]$sid, [string]$one) {
  return Invoke-Ziniao @("page", "exec", "--store-id", $sid, "--script", $one, "--timeout", "90000")
}
function Invoke-ClickNav([string]$sid, [string]$label) {
  $js = Get-Content (Join-Path $PSScriptRoot "_click-compass-nav.js") -Raw -Encoding UTF8
  $escaped = $label.Replace("\", "\\").Replace("'", "\'")
  $js = [regex]::Replace($js, "var DEFAULT_LABEL = '[^']*';", ("var DEFAULT_LABEL = '{0}';" -f $escaped))
  $one = ConvertTo-ScrapeOneLine $js
  Write-Step ("  click [{0}]" -f $label)
  $payload = Get-ScrapePayload (Invoke-PageExec $sid $one)
  Write-Step ("  click ok={0}" -f $(if ($payload) { $payload.ok } else { $false }))
  return $payload
}

$ziniaoWinLib = Join-Path $PSScriptRoot 'ziniao-window.ps1'
if (Test-Path $ziniaoWinLib) { . $ziniaoWinLib }

$sid = $StoreId
$checkJs = ConvertTo-ScrapeOneLine (Get-Content (Join-Path $PSScriptRoot "_check-page-url.js") -Raw -Encoding UTF8)
$probeJs = ConvertTo-ScrapeOneLine (Get-Content (Join-Path $PSScriptRoot "_probe-video-details-page.js") -Raw -Encoding UTF8)
$listJs = ConvertTo-ScrapeOneLine (Get-Content (Join-Path $PSScriptRoot "scrape-video-list-page.js") -Raw -Encoding UTF8)

Write-Step "===== video-details deep START ====="
Write-Step ("store={0} url={1}" -f $sid, $DetailUrl)

# open via parent first (more stable than cold open on detail)
$parent = "https://seller-uk.tiktok.com/compass/video-analytics?shop_region=GB"
if (Get-Command New-ZiniaoStoreOpenArgs -ErrorAction SilentlyContinue) {
  Write-Host (Invoke-Ziniao (New-ZiniaoStoreOpenArgs -StoreId $sid -Url $parent -WindowRatio 'full'))
} else {
  Write-Host (Invoke-Ziniao @("store", "open", "--id", $sid, "--url", $parent, "--window-ratio", "full"))
}
Start-Sleep -Seconds 32
if (Get-Command Invoke-ZiniaoStoreMaximize -ErrorAction SilentlyContinue) {
  Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step} | Out-Null
}
for ($t = 1; $t -le 4; $t++) {
  $null = Invoke-Ziniao @("page", "visit", "--store-id", $sid, "--url", $DetailUrl, "--wait-until", "load", "--timeout", "120000")
  Start-Sleep -Seconds 12
  $chk = Get-ScrapePayload (Invoke-PageExec $sid $checkJs)
  $href = if ($chk) { [string]$chk.href } else { "" }
  $bl = if ($chk -and $chk.bodyLen) { [int]$chk.bodyLen } else { 0 }
  Write-Step ("  gate try {0}: href={1} bodyLen={2}" -f $t, $href, $bl)
  if ($href -match "video-details" -and $bl -gt 400) { break }
  if ($href -match "video-details") { Start-Sleep -Seconds 25 } else { Start-Sleep -Seconds 10 }
}

# extra SPA settle
Start-Sleep -Seconds 40

$steps = @()
function Capture([string]$tag) {
  $probe = Get-ScrapePayload (Invoke-PageExec $sid $probeJs)
  $list = Get-ScrapePayload (Invoke-PageExec $sid $listJs)
  $cid = 0; $rows = 0; $bl = 0; $ids = @()
  if ($list) {
    if ($null -ne $list.contentIdCount) { $cid = [int]$list.contentIdCount }
    if ($list.videos) { $rows = @($list.videos).Count }
  }
  if ($probe) {
    if ($probe.bodyLen) { $bl = [int]$probe.bodyLen }
    if ($probe.longIdsInBody) { $ids = @($probe.longIdsInBody) }
  }
  $path = Join-Path $logsDir ("video-details-deep-{0}-{1}-{2}.json" -f $tag, $sid, $stamp)
  Write-Utf8File $path ((@{ tag = $tag; probe = $probe; list = $list } | ConvertTo-Json -Depth 14))
  Write-Step ("  [{0}] bodyLen={1} contentId={2} rows={3} longIds={4} file={5}" -f $tag, $bl, $cid, $rows, $ids.Count, $path)
  $script:steps += [pscustomobject]@{
    tag = $tag; bodyLen = $bl; contentIdCount = $cid; videoRowCount = $rows
    longIdCount = $ids.Count; path = $path
    url = $(if ($list -and $list.url) { [string]$list.url } elseif ($probe) { [string]$probe.url } else { $null })
  }
}

Capture "t0-initial"

foreach ($lab in @($LabelBound, $LabelAll, $LabelAffiliate, $LabelNeed)) {
  $null = Invoke-ClickNav $sid $lab
  Start-Sleep -Seconds 22
  Capture ("tab-" + ($lab -replace "\s+", ""))
}

# scroll attempt via exec
$scrollJs = ConvertTo-ScrapeOneLine @'
(function(){try{window.scrollTo(0,800);var el=document.scrollingElement||document.documentElement;if(el)el.scrollTop=1200;var lists=document.querySelectorAll("[class*=list],[class*=List],[class*=virtual],[class*=table]");for(var i=0;i<lists.length;i++){try{lists[i].scrollTop=600;}catch(e){}}return JSON.stringify({ok:true,scrollY:window.scrollY||0});}catch(e){return JSON.stringify({ok:false,error:String(e&&e.message?e.message:e)});}})();
'@
$null = Invoke-PageExec $sid $scrollJs
Start-Sleep -Seconds 15
Capture "after-scroll"

try { $null = Invoke-Ziniao @("store", "close", "--id", $sid) } catch { }

$sum = Join-Path $logsDir ("video-details-deep-summary-{0}.json" -f $stamp)
Write-Utf8File $sum (($steps | ConvertTo-Json -Depth 6))
Write-Step "======== DEEP SUMMARY ========"
$steps | Format-Table tag, bodyLen, contentIdCount, videoRowCount, longIdCount, url -AutoSize
Write-Step ("summary: {0}" -f $sum)
$best = @($steps | Where-Object { $_.contentIdCount -gt 0 -or $_.longIdCount -gt 0 } | Sort-Object contentIdCount, longIdCount -Descending)
if ($best.Count -gt 0) {
  Write-Step ("SIGNAL: tag={0} contentId={1} longIds={2}" -f $best[0].tag, $best[0].contentIdCount, $best[0].longIdCount)
} else {
  Write-Step "SIGNAL: none — video-details shell only / empty own-shop list"
}
Write-Step "===== video-details deep END ====="
