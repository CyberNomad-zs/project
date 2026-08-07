# Shared Ziniao store-window helpers: --window-ratio + Win32 maximize + page resize.
# Dot-source from run-*.ps1 after open / visit so Compass tables get full viewport.
#
#   . (Join-Path $PSScriptRoot 'ziniao-window.ps1')
#   $openArgs = New-ZiniaoStoreOpenArgs -StoreId $sid -Url $url -Config $cfg
#   Invoke-Ziniao $openArgs
#   Invoke-ZiniaoStoreMaximize -StoreId $sid -InvokeZiniao ${function:Invoke-Ziniao} -WriteStep ${function:Write-Step}
#
# NOTE: Win32 C# lives in ziniao-winmax.cs (Add-Type -Path).
# Do NOT inline C# here-strings in this UTF-8 file: Windows PowerShell 5.1
# reads no-BOM UTF-8 as system ANSI and breaks @' '@ when non-ASCII comments exist.

function Get-ZiniaoWindowRatio($cfg) {
  $ratio = 'full'
  if ($cfg -and $cfg.options -and $cfg.options.PSObject.Properties.Name -contains 'windowRatio' -and $cfg.options.windowRatio) {
    $ratio = [string]$cfg.options.windowRatio
  }
  return $ratio
}

function Test-ZiniaoMaximizeEnabled($cfg) {
  # default ON; set options.maximizeWindow=false to disable
  if ($cfg -and $cfg.options -and $null -ne $cfg.options.maximizeWindow) {
    return [bool]$cfg.options.maximizeWindow
  }
  return $true
}

function New-ZiniaoStoreOpenArgs {
  param(
    [Parameter(Mandatory = $true)][string]$StoreId,
    [Parameter(Mandatory = $true)][string]$Url,
    $Config = $null,
    [string]$WindowRatio = ''
  )
  $argsList = [System.Collections.Generic.List[string]]::new()
  $argsList.AddRange([string[]]@('store', 'open', '--id', $StoreId, '--url', $Url))
  $ratio = $WindowRatio
  if (-not $ratio) { $ratio = Get-ZiniaoWindowRatio $Config }
  if ($ratio -and $ratio -ne 'default' -and $ratio -ne 'none') {
    $argsList.Add('--window-ratio')
    $argsList.Add($ratio)
  }
  return @($argsList.ToArray())
}

function Initialize-ZiniaoWinMaxType {
  if ('ZiniaoWinMax' -as [type]) { return }
  $csPath = Join-Path $PSScriptRoot 'ziniao-winmax.cs'
  if (-not (Test-Path -LiteralPath $csPath)) {
    throw ("ziniao-winmax.cs not found: {0}" -f $csPath)
  }
  Add-Type -Path $csPath -ErrorAction Stop
}

function Maximize-ZiniaoBrowserWindows {
  # Ziniao store windows often open small; Win32 SW_MAXIMIZE beats --window-ratio alone.
  Initialize-ZiniaoWinMaxType
  return [ZiniaoWinMax]::MaximizeMatching()
}

function Get-ZiniaoPageMaximizeScript {
  return @(
    '(function(){try{'
    'if(window.moveTo)try{window.moveTo(0,0);}catch(e0){}'
    'if(window.resizeTo)try{window.resizeTo(screen.availWidth||screen.width,screen.availHeight||screen.height);}catch(e1){}'
    'try{document.documentElement.style.zoom="1";}catch(e2){}'
    'return JSON.stringify({ok:true,w:window.outerWidth||0,h:window.outerHeight||0,sw:screen.availWidth||0,sh:screen.availHeight||0});'
    '}catch(e){return JSON.stringify({ok:false,error:String(e&&e.message||e)});}})();'
  ) -join ''
}

function Invoke-ZiniaoStoreMaximize {
  param(
    [string]$StoreId = '',
    [scriptblock]$InvokeZiniao = $null,
    [scriptblock]$WriteStep = $null,
    $Config = $null,
    [switch]$SkipPageExec,
    [int]$PageExecTimeoutMs = 15000
  )
  if (-not (Test-ZiniaoMaximizeEnabled $Config)) {
    if ($WriteStep) { & $WriteStep '  maximize skipped (options.maximizeWindow=false)' }
    return @{ win32 = 0; page = $null; skipped = $true }
  }

  $n = 0
  try {
    $n = Maximize-ZiniaoBrowserWindows
    if ($WriteStep) { & $WriteStep ("  maximize Win32 hit={0}" -f $n) }
  } catch {
    if ($WriteStep) { & $WriteStep ("  WARN maximize Win32: {0}" -f $_) }
  }

  $pagePayload = $null
  if (-not $SkipPageExec -and $StoreId -and $InvokeZiniao) {
    try {
      $maxJs = Get-ZiniaoPageMaximizeScript
      $out = & $InvokeZiniao @('page', 'exec', '--store-id', $StoreId, '--script', $maxJs, '--timeout', ([string]$PageExecTimeoutMs))
      if ($WriteStep -and $out) {
        $one = ([string]$out) -replace '\s+', ' '
        if ($one.Length -gt 220) { $one = $one.Substring(0, 220) + '...' }
        & $WriteStep ("  maximize page: {0}" -f $one)
      }
      $pagePayload = $out
    } catch {
      if ($WriteStep) { & $WriteStep ("  WARN maximize page exec: {0}" -f $_) }
    }
  }

  return @{ win32 = $n; page = $pagePayload; skipped = $false }
}