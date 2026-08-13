# 本机一键：SSH 上生产机配置飞书 T1/T2 并触发同步
# 密钥：keys/qingquan_sg_ed25519   用户：ubuntu@43.156.50.38
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-server-tk-feishu-sync.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-server-tk-feishu-sync.ps1 -TunnelSync
#       # -TunnelSync：若服务器 worker 未部署 tk 同步，则开 15432 隧道用本机代码读服务器 PG 写飞书

param(
  [string]$HostName = "43.156.50.38",
  [string]$User = "ubuntu",
  [string]$KeyPath = "",
  [switch]$TunnelSync,
  [int]$LookbackDays = 60
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $KeyPath) {
  $KeyPath = Join-Path $Root 'keys\qingquan_sg_ed25519'
}
if (-not (Test-Path $KeyPath)) { throw "missing key: $KeyPath" }

$remoteScript = Join-Path $Root 'scripts\server-tk-feishu-sync.sh'
if (-not (Test-Path $remoteScript)) { throw "missing $remoteScript" }

$sshBase = @(
  '-i', $KeyPath,
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=30',
  '-o', 'IdentitiesOnly=yes',
  '-o', 'ServerAliveInterval=10',
  "${User}@${HostName}"
)

Write-Host "=== 1) SSH check ${User}@${HostName} ==="
& ssh @sshBase "echo OK; hostname; date"
if ($LASTEXITCODE -ne 0) {
  throw "SSH failed (exit $LASTEXITCODE). 若 Connection timed out：检查本机网络/安全组是否放行 22。"
}

Write-Host "=== 2) Upload server-tk-feishu-sync.sh ==="
& scp -i $KeyPath -o IdentitiesOnly=yes -o ConnectTimeout=30 `
  $remoteScript "${User}@${HostName}:/tmp/server-tk-feishu-sync.sh"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

Write-Host "=== 3) Run on server (sudo if needed for /opt/qingquan) ==="
$remoteCmd = @'
set -e
chmod +x /tmp/server-tk-feishu-sync.sh
if [ -w /opt/qingquan/.env ] 2>/dev/null; then
  bash /tmp/server-tk-feishu-sync.sh
elif sudo test -f /opt/qingquan/.env; then
  sudo QINGQUAN_DIR=/opt/qingquan bash /tmp/server-tk-feishu-sync.sh
else
  echo "Cannot find /opt/qingquan/.env — listing candidates:"
  ls -la /opt 2>/dev/null || true
  sudo find /home /opt /var -maxdepth 3 -name '.env' 2>/dev/null | head
  exit 1
fi
'@
& ssh @sshBase $remoteCmd
$serverRc = $LASTEXITCODE
Write-Host "server script exit=$serverRc"

if ($TunnelSync) {
  Write-Host "=== 4) Tunnel sync with local code (read server PG → Feishu) ==="
  # Start tunnel in background
  $tunnelArgs = @(
    '-i', $KeyPath,
    '-o', 'BatchMode=yes',
    '-o', 'IdentitiesOnly=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=10',
    '-N', '-L', '15432:127.0.0.1:5432',
    "${User}@${HostName}"
  )
  $tp = Start-Process -FilePath ssh -ArgumentList $tunnelArgs -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 3
  if ($tp.HasExited) { throw "SSH tunnel failed to start" }
  try {
    # Pull DB URL pieces from server .env (password only over ssh)
    $dbLine = & ssh @sshBase "sudo grep -E '^DATABASE_URL=' /opt/qingquan/.env | head -1"
    if (-not $dbLine) { throw "no DATABASE_URL on server" }
    # Rewrite host to tunnel
    $url = $dbLine -replace '^DATABASE_URL=', '' -replace '^"', '' -replace '"$', ''
    $url = $url -replace 'postgresql\+asyncpg://', 'postgresql+asyncpg://'
    $url = $url -replace 'postgresql://', 'postgresql+asyncpg://'
    # replace host:port after @ with 127.0.0.1:15432
    if ($url -match '@([^/]+)/') {
      $url = $url -replace '@([^/]+)/', '@127.0.0.1:15432/'
    }
    $env:DATABASE_URL = $url
    Write-Host "DATABASE_URL host -> 127.0.0.1:15432 (password hidden)"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts\sync-tk-feishu-from-db.ps1') -LookbackDays $LookbackDays
  } finally {
    Stop-Process -Id $tp.Id -Force -ErrorAction SilentlyContinue
  }
}

Write-Host ""
Write-Host "验收飞书（清泉组织 Base · 2026-08-10）："
Write-Host "  T1 https://dn86p8pyqr.feishu.cn/base/LzTAbQsThaPOzis2lFvciDMlnyh?table=tblrpFX6gWaf7KPX"
Write-Host "  T2 https://dn86p8pyqr.feishu.cn/base/LzTAbQsThaPOzis2lFvciDMlnyh?table=tblgLifLVW91v5Bk"
Write-Host "  异常 https://dn86p8pyqr.feishu.cn/base/LzTAbQsThaPOzis2lFvciDMlnyh?table=tblO1uGlWccuaiZF"
