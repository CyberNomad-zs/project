#!/usr/bin/env bash
set -euo pipefail
set -a; . /opt/qingquan/.env; set +a
USER=${ADMIN_USERNAME:-admin}
PASS=${ADMIN_PASSWORD:-}
if [[ -z "$PASS" ]]; then echo "NO_ADMIN_PASSWORD"; exit 1; fi
LOGIN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")
TOK=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("access_token",""))' "$LOGIN")
if [[ -z "$TOK" ]]; then echo "LOGIN_FAIL $LOGIN"; exit 1; fi
echo LOGIN_OK
AUTH="Authorization: Bearer ${TOK}"

echo "=== shop-daily ==="
curl -sS -H "$AUTH" "http://127.0.0.1:8000/api/v1/tk/shop-daily?lookback_days=7" > /tmp/s_shop.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/s_shop.json"))
s=d.get("summary", d)
print("data_source=", s.get("data_source"), "gmv=", s.get("gmv"), "open_anomaly=", s.get("open_anomaly_count"), "total=", d.get("total") or s.get("total"))
PY

echo "=== content ==="
curl -sS -H "$AUTH" "http://127.0.0.1:8000/api/v1/tk/content?lookback_days=1" > /tmp/s_content.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/s_content.json"))
items=d.get("items") or d.get("rows") or []
print("total=", d.get("total"), "items=", len(items), "keys=", list(d)[:12])
if items:
    x=items[0]
    print("sample", {k:x.get(k) for k in ["shop_name","biz_date","content_id","attributed_gmv","impressions","play_count"]})
PY

echo "=== product-traffic ==="
curl -sS -H "$AUTH" "http://127.0.0.1:8000/api/v1/tk/product-traffic?lookback_days=1" > /tmp/s_traffic.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/s_traffic.json"))
items=d.get("items") or d.get("rows") or []
print("total=", d.get("total"), "items=", len(items))
if items:
    x=items[0]
    print("sample", {k:x.get(k) for k in ["shop_name","biz_date","product_id","channel","ctr","cvr","impressions"]})
PY

echo "=== content anomaly dry ==="
curl -sS -H "$AUTH" "http://127.0.0.1:8000/api/v1/tk/content/anomaly-eval" > /tmp/s_ca.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/s_ca.json"))
print({k:d.get(k) for k in list(d)[:25]})
PY

echo "=== anomaly tasks open sample ==="
curl -sS -H "$AUTH" "http://127.0.0.1:8000/api/v1/tk/anomaly-tasks?status=open&limit=5" > /tmp/s_an.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/s_an.json"))
items=d.get("items") or d.get("tasks") or []
print("total=", d.get("total"), "items=", len(items) if isinstance(items,list) else type(items))
if isinstance(items,list) and items:
    x=items[0]
    print("sample", {k:x.get(k) for k in ["anomaly_code","level_code","object_type","status","description","current_value","needs_boss_decision"]})
    codes={}
    for it in items:
        c=it.get("anomaly_code") or "?"
        codes[c]=codes.get(c,0)+1
    print("codes_in_page", codes)
PY

echo "=== public ==="
curl -sS -o /dev/null -w "https_root:%{http_code}\n" https://qingquan.jmzlai.com/ || true
curl -sS -o /dev/null -w "https_health:%{http_code}\n" https://qingquan.jmzlai.com/health || true
JS=$(ls /opt/qingquan/web/dist/assets/index-*.js | head -1)
BN=$(basename "$JS")
curl -sS -o /dev/null -w "https_js:%{http_code}\n" "https://qingquan.jmzlai.com/assets/$BN" || true
if curl -sS "https://qingquan.jmzlai.com/assets/$BN" | grep -q 'tk-content'; then echo PUBLIC_JS_HAS_TK_CONTENT; else echo PUBLIC_JS_MISS_TK_CONTENT; fi
echo SMOKE_DONE
