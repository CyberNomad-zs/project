#!/usr/bin/env bash
set -euo pipefail
cd /tmp
rm -rf /tmp/temu-sellfox
mkdir -p /tmp/temu-sellfox
unzip -o /tmp/temu-sellfox-linux.zip -d /tmp/temu-sellfox
sed -i 's/\r$//' /tmp/temu-sellfox/deploy/install-sellfox-linux.sh || true
chmod +x /tmp/temu-sellfox/deploy/install-sellfox-linux.sh
sudo apt-get update -qq
sudo apt-get install -y -qq rsync unzip
sudo bash /tmp/temu-sellfox/deploy/install-sellfox-linux.sh /opt/temu-monitor
sudo cp /tmp/sellfox.config.json /opt/temu-monitor/sellfox.config.json
sudo chown temu:temu /opt/temu-monitor/sellfox.config.json
sudo chmod 600 /opt/temu-monitor/sellfox.config.json
echo "=== files ==="
ls -la /opt/temu-monitor
ls -la /opt/temu-monitor/src/sellfox
echo "=== config keys (masked) ==="
sudo -u temu node -e '
const d=require("/opt/temu-monitor/sellfox.config.json");
console.log({
  enabled:d.enabled,
  clientId: d.clientId? String(d.clientId).slice(0,3)+"***":null,
  secret: !!d.clientSecret,
  hooks:(d.feishuWebhooks||[]).length,
  stores:(d.stores||[]).map(s=>s.name+":"+s.shopId),
  alerts:d.alerts,
  interval:d.intervalMinutes
});
'
echo "=== probe ==="
cd /opt/temu-monitor
sudo -u temu node src/sellfox/cli.js probe
echo "=== once (first baseline if empty) ==="
sudo -u temu node src/sellfox/cli.js once
echo "=== start service ==="
sudo systemctl enable --now temu-sellfox
sleep 2
sudo systemctl status temu-sellfox --no-pager -l || true
echo "=== recent journal ==="
sudo journalctl -u temu-sellfox -n 30 --no-pager || true
