# Temu monitor daemon. Started by GUI "守护常驻" or scheduled task 'TemuMonitor'.
# Runs 'node src/cli.js start' (15-min polling). Auto-restarts 30s after any crash.
#
# UX (2026-07-31):
#  - Console shows LIVE node logs (no more blank black window).
#  - Same lines also go to logs\monitor-YYYYMMDD.out.log / .err.log
#  - logger.js still dual-writes data\monitor.log + logs\monitor-YYYYMMDD.log
#  - Refuses to start a second daemon / second `cli.js start` (avoids .userdata lock fight)
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
try { $OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$root = $PSScriptRoot
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { $node = 'node.exe' }
Set-Location $root
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null

function Write-Daemon([string]$msg) {
  $line = '[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $msg
  Write-Host $line
  try {
    $day = Get-Date -Format 'yyyyMMdd'
    $log = Join-Path $logDir ("daemon-" + $day + ".log")
    $line | Out-File -Append -Encoding utf8 $log
  } catch {}
}

function Get-MonitorNodePids {
  # Other node processes running `cli.js start` (not this shell)
  $list = @()
  try {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
      $cl = [string]$p.CommandLine
      if ($cl -match 'cli\.js' -and $cl -match '\bstart\b') {
        $list += [int]$p.ProcessId
      }
    }
  } catch {}
  return $list
}

function Get-OtherDaemonPids {
  # Other powershell hosting run-forever.ps1
  $list = @()
  $myPid = $PID
  try {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
      if ([int]$p.ProcessId -eq $myPid) { continue }
      $cl = [string]$p.CommandLine
      # Must match -File run-forever, not a one-liner that merely mentions the name
      if ($cl -match '-File\s+\S*run-forever\.ps1' -or $cl -match '-File\s+"\S*run-forever\.ps1"') {
        $list += [int]$p.ProcessId
      }
    }
  } catch {}
  return $list
}

Write-Host ''
Write-Host '============================================================'
Write-Host '  Temu Traffic Monitor  -  daemon (run-forever)'
Write-Host '  Live logs will appear BELOW. Keep this window open.'
Write-Host '  Close window / Ctrl+C = stop daemon.'
Write-Host '  Crash -> auto restart in 30s.'
Write-Host '============================================================'
Write-Host ('  Work dir : ' + $root)
Write-Host ('  Node     : ' + $node)
Write-Host ('  Log dir  : ' + $logDir)
Write-Host ('  Also see : logs\monitor-YYYYMMDD.log  (and data\monitor.log)')
Write-Host '============================================================'
Write-Host ''

# --- single instance ---
$others = Get-OtherDaemonPids
if ($others.Count -gt 0) {
  Write-Daemon ("ABORT: another run-forever already running (PID " + ($others -join ', ') + ").")
  Write-Host '  Do not open 守护常驻 twice. Use one daemon only.'
  Write-Host '  Or stop the old one in Task Manager (powershell run-forever / node cli.js start).'
  Write-Host ''
  Write-Host '  Press Enter to close...'
  try { Read-Host | Out-Null } catch {}
  exit 2
}

$nodeRunning = Get-MonitorNodePids
if ($nodeRunning.Count -gt 0) {
  Write-Daemon ("ABORT: node cli.js start already running (PID " + ($nodeRunning -join ', ') + ").")
  Write-Host '  Likely "流量常驻 · 前台" or another daemon is active.'
  Write-Host '  Two instances share .userdata -> browser closed mid-scan.'
  Write-Host '  Stop the other window first, then re-open 守护常驻.'
  Write-Host ''
  Write-Host '  Press Enter to close...'
  try { Read-Host | Out-Null } catch {}
  exit 3
}

Write-Daemon 'daemon ready; launching node src/cli.js start'

while ($true) {
  $day = Get-Date -Format 'yyyyMMdd'
  $out = Join-Path $logDir ("monitor-" + $day + ".out.log")
  $err = Join-Path $logDir ("monitor-" + $day + ".err.log")

  Write-Daemon '=== start: node src/cli.js start ==='
  Write-Host ('  (tee -> ' + $out + ')')
  Write-Host ''

  # clear stale Chrome single-instance locks from any previous abnormal exit
  Remove-Item (Join-Path $root '.userdata\SingletonLock'), (Join-Path $root '.userdata\SingletonCookie'), (Join-Path $root '.userdata\lockfile') -Force -ErrorAction SilentlyContinue

  # Re-check right before spawn (race with a just-opened 前台常驻)
  $race = Get-MonitorNodePids
  if ($race.Count -gt 0) {
    Write-Daemon ("skip spawn: node start already up (PID " + ($race -join ', ') + '); wait 60s')
    Start-Sleep -Seconds 60
    continue
  }

  # Run node attached: live console + append to out/err.
  # (Old design used Start-Process -RedirectStandardOutput which made the window look dead.)
  $exitCode = 0
  try {
    # Native exe: merge stderr into success stream via 2>&1, line-buffer through pipeline
    & $node 'src\cli.js' 'start' 2>&1 | ForEach-Object {
      $text = $_ | Out-String
      $text = $text.TrimEnd("`r", "`n")
      if ($null -eq $text) { return }
      # ErrorRecord from native stderr still prints useful message
      if ($_ -is [System.Management.Automation.ErrorRecord]) {
        $msg = $_.Exception.Message
        if (-not $msg) { $msg = "$_" }
        Write-Host $msg
        try { Add-Content -Path $err -Value $msg -Encoding utf8 } catch {}
        # logger lines also go stderr for ERROR level — keep a copy in out for one-file tail
        try { Add-Content -Path $out -Value $msg -Encoding utf8 } catch {}
      } else {
        Write-Host $text
        try { Add-Content -Path $out -Value $text -Encoding utf8 } catch {}
      }
    }
    if ($null -ne $LASTEXITCODE) { $exitCode = $LASTEXITCODE } else { $exitCode = 0 }
  } catch {
    $exitCode = 1
    Write-Daemon ("node spawn error: " + $_.Exception.Message)
  }

  Write-Host ''
  Write-Daemon ("=== node exited (code=$exitCode), restart in 30s ===")
  Write-Host '  (Close this window now if you want to STOP the daemon.)'
  Start-Sleep -Seconds 30
}
