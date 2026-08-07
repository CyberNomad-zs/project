#!/usr/bin/env bash
set -euo pipefail
echo "=== service ==="
systemctl is-active temu-sellfox
systemctl show temu-sellfox -p ActiveState -p SubState -p MainPID --no-pager
echo "=== config ==="
sudo -u temu node <<'NODE'
const d = require('/opt/temu-monitor/sellfox.config.json');
console.log(JSON.stringify({
  intervalMinutes: d.intervalMinutes,
  alerts: d.alerts,
  hookCount: (d.feishuWebhooks || []).length,
  hookTail: (d.feishuWebhooks || []).map((u) => String(u).slice(-12)),
  stores: (d.stores || []).filter((s) => s.enabled !== false).map((s) => s.name + ':' + s.shopId),
}, null, 2));
NODE
echo "=== journal last 30 ==="
journalctl -u temu-sellfox -n 30 --no-pager
echo "=== state ==="
sudo -u temu node <<'NODE'
const s = require('/opt/temu-monitor/data/sellfox-state.json');
for (const [id, st] of Object.entries(s.stores || {})) {
  const ts = (st.latest && st.latest.ts) || (st.snapshot && st.snapshot.ts);
  console.log(id, st.name, 'onSale=' + (st.latest && st.latest.onSaleCount), 'ts=' + (ts ? new Date(ts).toISOString() : '-'));
}
NODE
