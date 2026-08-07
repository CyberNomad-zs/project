#!/usr/bin/env bash
set -euo pipefail
echo "=== health ==="
curl -sS http://127.0.0.1:8000/health || true
echo
echo "=== openapi tk paths ==="
curl -sS http://127.0.0.1:8000/openapi.json -o /tmp/openapi.json
python3 - <<'PY'
import json
p = json.load(open("/tmp/openapi.json")).get("paths", {})
for k in sorted(p):
    if "/tk/" in k:
        print(k)
PY
echo "=== pg tk tables ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -Atc \
  "SELECT tablename FROM pg_tables WHERE schemaname='tk' ORDER BY 1;"
echo "=== anomaly columns sample ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -Atc \
  "SELECT column_name FROM information_schema.columns WHERE table_schema='tk' AND table_name='fact_tk_anomaly_task' AND column_name IN ('level_code','description','object_type','current_value') ORDER BY 1;"
echo "=== counts ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT 'content' AS t, count(*)::text, coalesce(min(biz_date)::text,'-'), coalesce(max(biz_date)::text,'-') FROM tk.fact_tiktok_content_daily
   UNION ALL SELECT 'traffic', count(*)::text, coalesce(min(biz_date)::text,'-'), coalesce(max(biz_date)::text,'-') FROM tk.fact_tiktok_product_traffic_daily
   UNION ALL SELECT 'shop_daily', count(*)::text, coalesce(min(biz_date)::text,'-'), coalesce(max(biz_date)::text,'-') FROM tk.fact_tiktok_shop_daily
   UNION ALL SELECT 'ads', count(*)::text, coalesce(min(biz_date)::text,'-'), coalesce(max(biz_date)::text,'-') FROM tk.fact_ads_campaign_daily;" \
  || echo "count-fail"
echo "=== content anomalies ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT anomaly_code, status, count(*) FROM tk.fact_tk_anomaly_task WHERE object_type='content' OR anomaly_code LIKE 'content%' GROUP BY 1,2 ORDER BY 1,2;" \
  || true
echo "=== object_type constraint ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -Atc \
  "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='tk.fact_tk_anomaly_task'::regclass AND contype='c' AND pg_get_constraintdef(oid) ILIKE '%object_type%';" \
  || true
echo "=== dim content codes ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -Atc \
  "SELECT code FROM tk.dim_tk_anomaly_type WHERE code LIKE 'content%' ORDER BY 1;" \
  || true
echo "=== env TK lines ==="
grep -nE 'FEISHU_BITABLE_TABLE_TK|CONTENT' /opt/qingquan/.env | cat -A | sed 's/=.*/=***/'
echo "=== docker api created ==="
docker inspect qingquan-api-1 --format '{{.Created}} {{.Config.Image}}' 2>/dev/null || true
echo "=== web App.vue content tab? ==="
grep -n 'tk-content\|内容分析' /opt/qingquan/web/src/App.vue | head -20 || echo 'no App.vue match'
echo "=== dist js content tab? ==="
if ls /opt/qingquan/web/dist/assets/*.js >/dev/null 2>&1; then
  grep -l 'tk-content\|内容分析' /opt/qingquan/web/dist/assets/*.js 2>/dev/null | head -5 || echo 'dist-no-match'
else
  echo 'no-dist-assets'
fi
echo "=== local vs container main.py size ==="
wc -c /opt/qingquan/backend/app/main.py /opt/qingquan/backend/app/api/tk_ops.py
docker exec qingquan-api-1 wc -c /app/app/main.py /app/app/api/tk_ops.py 2>/dev/null || true
echo "=== migrations 015 present? ==="
ls -la /opt/qingquan/backend/migrations/015*.sql 2>&1 || true
