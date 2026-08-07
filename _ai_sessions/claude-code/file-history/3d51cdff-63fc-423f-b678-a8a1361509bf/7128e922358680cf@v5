# One-click install: Node.js LTS + ziniao-cli (+ optional API Key init)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-deps.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-deps.ps1 -ApiKey "YOUR_KEY"
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-deps.ps1 -SkipNode
#   powershell -ExecutionPolicy Bypass -File .\scripts\install-deps.ps1 -DoctorOnly
#
# Does NOT install the Ziniao desktop browser.

param(
  [string]$ApiKey = '',
  [string]$Profile = 'default',
  [switch]$SkipNode,
  [switch]$SkipCli,
  [switch]$DoctorOnly,
  [switch]$NoKeychain,
  # Default: China mirrors (npmmirror). Use -UseOfficialMirror for nodejs.org / registry.npmjs.org
  [switch]$UseOfficialMirror
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent

function Write-Step([string]$msg) {
  Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg)
}
function Write-Ok([string]$msg) { Write-Host ("  OK  {0}" -f $msg) -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host ("  WARN {0}" -f $msg) -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host ("  FAIL {0}" -f $msg) -ForegroundColor Red }

function Update-SessionPath {
  $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $user = [Environment]::GetEnvironmentVariable('Path', 'User')
  $env:Path = @($machine, $user) -join ';'
  $npmGlobal = Join-Path $env:APPDATA 'npm'
  if ((Test-Path $npmGlobal) -and ($env:Path -notlike "*$npmGlobal*")) {
    $env:Path = "$npmGlobal;$env:Path"
  }
  $nodeDir = 'C:\Program Files\nodejs'
  if ((Test-Path $nodeDir) -and ($env:Path -notlike "*$nodeDir*")) {
    $env:Path = "$nodeDir;$env:Path"
  }
}

function Test-Cmd([string]$name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Get-CmdVersion([string]$name, [string[]]$verArgs = @('--version')) {
  try {
    $c = Get-Command $name -ErrorAction Stop
    $out = & $c.Source @verArgs 2>&1 | Out-String
    return ($out -replace '\r?\n', ' ').Trim()
  } catch {
    return $null
  }
}

function ConvertTo-ArgLine([string[]]$argList) {
  ($argList | ForEach-Object {
    $a = [string]$_
    if ($a -match '[\s"]') {
      '"' + ($a.Replace('"', '\"')) + '"'
    } else {
      $a
    }
  }) -join ' '
}

function Invoke-Native {
  param(
    [Parameter(Mandatory = $true)][string]$File,
    # Do NOT name this $Args — collides with PowerShell automatic $args and becomes empty
    [Parameter(Mandatory = $false)][string[]]$CmdArgs = @(),
    [int]$TimeoutSec = 600
  )
  $argLine = ConvertTo-ArgLine $CmdArgs
  Write-Step ("run: {0} {1}" -f $File, $argLine)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $File
  $psi.Arguments = $argLine
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  if (-not $p.WaitForExit($TimeoutSec * 1000)) {
    try { $p.Kill() } catch {}
    throw "timeout after ${TimeoutSec}s: $File"
  }
  if ($stdout) { Write-Host $stdout }
  if ($stderr) { Write-Host $stderr }
  return $p.ExitCode
}

function Get-NpmRegistry {
  if ($UseOfficialMirror) { return 'https://registry.npmjs.org' }
  return 'https://registry.npmmirror.com'
}

function Get-NodeMirrorBase {
  if ($UseOfficialMirror) { return 'https://nodejs.org/dist' }
  return 'https://cdn.npmmirror.com/binaries/node'
}

function Get-LatestNodeLtsVersion {
  # Prefer npmmirror index; fallback nodejs.org
  $urls = @(
    'https://cdn.npmmirror.com/binaries/node/index.json',
    'https://npmmirror.com/mirrors/node/index.json',
    'https://nodejs.org/dist/index.json'
  )
  if ($UseOfficialMirror) {
    $urls = @('https://nodejs.org/dist/index.json') + $urls
  }
  foreach ($u in $urls) {
    try {
      Write-Step ("fetch Node version index: {0}" -f $u)
      $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 30
      $list = $resp.Content | ConvertFrom-Json
      foreach ($item in $list) {
        $lts = $item.lts
        $isLts = $false
        if ($lts -is [bool]) { $isLts = $lts }
        elseif ($lts -and "$lts" -ne 'False' -and "$lts" -ne '') { $isLts = $true }
        if ($isLts -and $item.version) {
          return ([string]$item.version).TrimStart('v')
        }
      }
    } catch {
      Write-Warn ("index failed: {0}" -f $_)
    }
  }
  # hard fallback known recent LTS
  return '22.17.0'
}

function Install-NodeFromMirror {
  $ver = Get-LatestNodeLtsVersion
  $base = Get-NodeMirrorBase
  $msiName = "node-v$ver-x64.msi"
  $url = "$base/v$ver/$msiName"
  $tmpDir = Join-Path $env:TEMP 'tk-node-install'
  New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
  $msiPath = Join-Path $tmpDir $msiName

  Write-Step ("download Node LTS v{0} from mirror..." -f $ver)
  Write-Host ("  URL: {0}" -f $url)
  try {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
    # WebClient: no blue progress bar; more reliable on PS 5.1 + cmd host
    $wc = New-Object System.Net.WebClient
    try {
      $wc.Headers.Add('User-Agent', 'TK-Ad-Monitor-install-deps')
      $wc.DownloadFile($url, $msiPath)
    } finally {
      $wc.Dispose()
    }
  } catch {
    Write-Fail ("download failed: {0}" -f $_)
    return $false
  }
  if (-not (Test-Path $msiPath) -or ((Get-Item $msiPath).Length -lt 1MB)) {
    Write-Fail 'downloaded MSI missing or too small'
    return $false
  }
  Write-Ok ("MSI saved: {0} ({1:N1} MB)" -f $msiPath, ((Get-Item $msiPath).Length / 1MB))

  Write-Step 'silent install Node MSI (may prompt UAC)...'
  # Quote MSI path; avoid ADDLOCAL=ALL (some Node builds reject it → msiexec 1639)
  $msiArgs = @('/i', $msiPath, '/qn', '/norestart')
  $code = 1
  try {
    $code = Invoke-Native -File 'msiexec.exe' -CmdArgs $msiArgs -TimeoutSec 900
  } catch {
    Write-Fail "$_"
  }
  Update-SessionPath
  Start-Sleep -Seconds 2
  Update-SessionPath
  if (Test-Cmd 'node') {
    Write-Ok ("Node installed via mirror: {0}" -f (Get-CmdVersion 'node'))
    return $true
  }
  $pf = Join-Path ${env:ProgramFiles} 'nodejs\node.exe'
  if (Test-Path $pf) {
    $env:Path = ("{0};{1}" -f (Split-Path $pf -Parent), $env:Path)
    Write-Ok ("Node found at {0}" -f $pf)
    return $true
  }
  Write-Fail ("msiexec exit={0}; node still not found" -f $code)
  return $false
}

function Install-NodeLts {
  Update-SessionPath
  if (Test-Cmd 'node') {
    Write-Ok ("Node already installed: {0}" -f (Get-CmdVersion 'node'))
    return $true
  }

  # 1) China mirror MSI first (faster in CN)
  if (-not $UseOfficialMirror) {
    Write-Step 'prefer China mirror for Node (npmmirror)'
    if (Install-NodeFromMirror) { return $true }
    Write-Warn 'mirror install failed; try winget fallback'
  }

  # 2) winget fallback
  if (Test-Cmd 'winget') {
    Write-Step 'install Node.js LTS via winget (may prompt UAC)...'
    $code = 1
    try {
      $code = Invoke-Native -File 'winget' -CmdArgs @(
        'install', '-e', '--id', 'OpenJS.NodeJS.LTS',
        '--accept-package-agreements', '--accept-source-agreements',
        '--disable-interactivity'
      ) -TimeoutSec 900
    } catch {
      Write-Fail "$_"
    }
    Update-SessionPath
    Start-Sleep -Seconds 2
    Update-SessionPath
    if (Test-Cmd 'node') {
      Write-Ok ("Node installed: {0}" -f (Get-CmdVersion 'node'))
      return $true
    }
  } else {
    Write-Warn 'winget not found'
  }

  # 3) official/mirror retry if user forced official and winget failed
  if ($UseOfficialMirror) {
    if (Install-NodeFromMirror) { return $true }
  }

  $candidates = @(
    'C:\Program Files\nodejs\node.exe',
    (Join-Path ${env:ProgramFiles} 'nodejs\node.exe')
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) {
      $dir = Split-Path $c -Parent
      $env:Path = "$dir;$env:Path"
      Write-Ok ("Node found at {0}" -f $c)
      return $true
    }
  }

  Write-Fail 'Node install failed. Manual: https://nodejs.org/ or https://npmmirror.com/mirrors/node/'
  return $false
}

function Install-ZiniaoCli {
  Update-SessionPath
  if (-not (Test-Cmd 'node') -or -not (Test-Cmd 'npm')) {
    Write-Fail 'node/npm missing; cannot install ziniao-cli'
    return $false
  }

  $registry = Get-NpmRegistry
  Write-Step ("npm install -g @ziniao-open/cli (registry={0})" -f $registry)
  $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction SilentlyContinue }
  if (-not $npmCmd) {
    Write-Fail 'npm not found'
    return $false
  }

  $exe = if ($npmCmd.Source -like '*.cmd') {
    $npmCmd.Source
  } else {
    $cmdBeside = Join-Path (Split-Path $npmCmd.Source -Parent) 'npm.cmd'
    if (Test-Path $cmdBeside) { $cmdBeside } else { $npmCmd.Source }
  }

  # Persist user-level registry for faster future installs in China
  try {
    $null = Invoke-Native -File $exe -CmdArgs @('config', 'set', 'registry', $registry) -TimeoutSec 60
    Write-Ok ("npm registry => {0}" -f $registry)
  } catch {
    Write-Warn ("set registry failed: {0}" -f $_)
  }

  $code = Invoke-Native -File $exe -CmdArgs @(
    'install', '-g', '@ziniao-open/cli',
    '--registry', $registry
  ) -TimeoutSec 600
  Update-SessionPath

  if (Test-Cmd 'ziniao-cli') {
    Write-Ok ("ziniao-cli installed: {0}" -f (Get-CmdVersion 'ziniao-cli' @('-v')))
    return $true
  }

  try {
    $prefix = (& $exe @('prefix', '-g') 2>$null | Out-String).Trim()
    $runJs = Join-Path $prefix 'node_modules\@ziniao-open\cli\scripts\run.js'
    if (Test-Path $runJs) {
      Write-Ok ("ziniao-cli package present: {0}" -f $runJs)
      Write-Warn 'ziniao-cli not on PATH yet; multi-store script can still call node+run.js'
      return $true
    }
  } catch {}

  Write-Fail "npm install exit=$code but ziniao-cli not found"
  return $false
}
function Initialize-ZiniaoApiKey([string]$key, [string]$profileName, [bool]$plain) {
  if ([string]::IsNullOrWhiteSpace($key)) { return $true }
  Update-SessionPath

  $runJs = Join-Path $env:APPDATA 'npm\node_modules\@ziniao-open\cli\scripts\run.js'
  if (-not (Test-Path $runJs)) { $runJs = $null }

  Write-Step ("init ziniao profile '{0}' with provided API Key..." -f $profileName)
  $initArgs = @('config', 'init', '--api-key-stdin', '--member', '--profile', $profileName)
  if ($plain) { $initArgs += '--no-keychain' }

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  if ($runJs) {
    $psi.FileName = (Get-Command node).Source
    $psi.Arguments = ConvertTo-ArgLine (@($runJs) + $initArgs)
  } else {
    $psi.FileName = (Get-Command ziniao-cli).Source
    $psi.Arguments = ConvertTo-ArgLine $initArgs
  }
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $p.StandardInput.WriteLine($key.Trim())
  $p.StandardInput.Close()
  $out = $p.StandardOutput.ReadToEnd()
  $err = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($out) { Write-Host $out }
  if ($err) { Write-Host $err }
  if ($p.ExitCode -eq 0) {
    Write-Ok 'API Key configured'
    return $true
  }
  Write-Fail ("config init exit={0}. Manual: ziniao-cli config init --member" -f $p.ExitCode)
  return $false
}

function Invoke-Doctor {
  Update-SessionPath
  Write-Step 'environment check'
  $ok = $true

  if (Test-Cmd 'node') {
    Write-Ok ("node  {0}" -f (Get-CmdVersion 'node'))
  } else {
    Write-Fail 'node missing'
    $ok = $false
  }
  if (Test-Cmd 'npm') {
    Write-Ok ("npm   {0}" -f (Get-CmdVersion 'npm'))
  } else {
    Write-Fail 'npm missing'
    $ok = $false
  }

  $cliOk = $false
  if (Test-Cmd 'ziniao-cli') {
    Write-Ok ("ziniao-cli {0}" -f (Get-CmdVersion 'ziniao-cli' @('-v')))
    $cliOk = $true
  } else {
    $runJs = Join-Path $env:APPDATA 'npm\node_modules\@ziniao-open\cli\scripts\run.js'
    if (Test-Path $runJs) {
      Write-Ok ("ziniao package: {0}" -f $runJs)
      $cliOk = $true
    } else {
      Write-Fail 'ziniao-cli missing'
      $ok = $false
    }
  }

  if ($cliOk) {
    Write-Step 'ziniao-cli doctor...'
    try {
      $doc = ''
      if (Test-Cmd 'ziniao-cli') {
        $doc = & ziniao-cli doctor 2>&1 | Out-String
      } else {
        $runJs = Join-Path $env:APPDATA 'npm\node_modules\@ziniao-open\cli\scripts\run.js'
        $doc = & node $runJs doctor 2>&1 | Out-String
      }
      Write-Host $doc
      Write-Ok 'doctor finished (see output above)'
    } catch {
      Write-Warn "doctor: $_"
    }
  }

  Write-Step 'manual dependency: Ziniao desktop browser'
  Write-Host '  Ziniao desktop client must be installed and logged in separately.'
  Write-Host '  Download/login, keep client online, then run scrape.'
  Write-Host '  Open platform: https://open.ziniao.com/'

  $cfg = Join-Path $root 'config\stores.config.json'
  if (Test-Path $cfg) {
    Write-Ok "project config present: $cfg"
  } else {
    Write-Warn 'config\stores.config.json missing - copy from stores.config.example.json'
  }

  return $ok
}

Write-Host ''
Write-Host '======== TK Ad Monitor - install deps ========' -ForegroundColor Cyan
if ($UseOfficialMirror) {
  Write-Host 'mirror: OFFICIAL (nodejs.org / registry.npmjs.org)'
} else {
  Write-Host 'mirror: CHINA (npmmirror Node dist + registry.npmmirror.com)'
}
Write-Host "root: $root"
Write-Host ''

Update-SessionPath

if ($DoctorOnly) {
  $d = Invoke-Doctor
  if ($d) { exit 0 } else { exit 1 }
}

$allOk = $true

if (-not $SkipNode) {
  if (-not (Install-NodeLts)) { $allOk = $false }
} else {
  Write-Step 'SkipNode: skip Node install'
}

if ($allOk -or (Test-Cmd 'node')) {
  if (-not $SkipCli) {
    if (-not (Install-ZiniaoCli)) { $allOk = $false }
  } else {
    Write-Step 'SkipCli: skip ziniao-cli install'
  }
}

if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
  if (-not (Initialize-ZiniaoApiKey -key $ApiKey -profileName $Profile -plain:([bool]$NoKeychain))) {
    $allOk = $false
  }
} else {
  Write-Step 'API Key: not provided (optional)'
  Write-Host '  If ziniao-cli not configured yet, either:'
  Write-Host '    1) Interactive: ziniao-cli config init --member'
  Write-Host '    2) This script: -ApiKey YOUR_KEY'
  Write-Host '  Get the key from Ziniao Open Platform after creating an app.'
}

Write-Host ''
$docOk = Invoke-Doctor
if (-not $docOk) { $allOk = $false }

Write-Host ''
if ($allOk) {
  Write-Host '======== DONE: core deps ready ========' -ForegroundColor Green
  Write-Host 'Next: open Ziniao client and login, then launcher ListOnly / DryRun'
  exit 0
} else {
  Write-Host '======== DONE with FAIL items above ========' -ForegroundColor Yellow
  exit 1
}