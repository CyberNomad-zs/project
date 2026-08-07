#!/usr/bin/env bash
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /opt/qingquan/.env
set +a

USER="${ADMIN_USERNAME:-admin}"
PASS="${ADMIN_PASSWORD:-}"
if [ -z "$PASS" ]; then
  echo "no admin pass" >&2
  exit 1
fi

TOK=$(
  curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'
)
if [ -z "$TOK" ]; then
  echo "login fail" >&2
  exit 1
fi

curl -sS "http://127.0.0.1:8000/api/v1/tk/shop-daily?lookback_days=1&page_size=3" \
  -H "Authorization: Bearer ${TOK}" -o /tmp/sd.json

python3 -c '
import json
body=json.load(open("/tmp/sd.json"))
fr=body.get("freshness") or {}
print("biz_date", body.get("biz_date"))
print("freshness_ok", fr.get("ok"), "stale", fr.get("stale"))
print("shop", fr.get("shop_daily_max"), "ads", fr.get("ads_max"), "content", fr.get("content_max"), "traffic", fr.get("traffic_max"))
print("boss", fr.get("boss_decision_count"), "open", fr.get("open_anomaly_count"))
print("summary_boss", (body.get("summary") or {}).get("boss_decision_count"))
assert "freshness" in body
assert isinstance(fr.get("stale"), list)
print("SHOP_DAILY_SMOKE_OK")
'

curl -sS "http://127.0.0.1:8000/api/v1/tk/anomaly-tasks?open_only=true&page_size=2" \
  -H "Authorization: Bearer ${TOK}" -o /tmp/an.json

python3 -c '
import json
body=json.load(open("/tmp/an.json"))
items=body.get("items") or []
print("anomaly_total", body.get("total"), "sample", len(items))
if items:
    t=items[0]
    print("level", t.get("level_code"), "boss", t.get("needs_boss_decision"), "cur", t.get("current_value"))
    print("has_desc", bool(t.get("description")), "streak", t.get("streak_count"))
print("ANOMALY_SMOKE_OK")
'

js=$(ls /opt/qingquan/web/dist/assets/index-*.js | head -1)
css=$(ls /opt/qingquan/web/dist/assets/index-*.css | head -1)
echo "js=$js"
echo "css=$css"
for m in "待老板决策" "数据新鲜度" "lvl-red" "freshness-banner"; do
  if grep -q "$m" "$js" "$css" 2>/dev/null; then
    echo "DIST_HAS $m"
  else
    echo "DIST_MISS $m"
  fi
done
