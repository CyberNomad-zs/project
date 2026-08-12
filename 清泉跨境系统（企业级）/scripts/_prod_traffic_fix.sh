#!/usr/bin/env bash
set -euo pipefail
cd /opt/qingquan
set -a; . ./.env; set +a
cd deploy
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env build api worker
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
cd /opt/qingquan
for i in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8000/health >/dev/null && break
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health
echo
docker cp /opt/qingquan/scripts/tk_backfill_product_traffic_metrics.py qingquan-api-1:/tmp/tk_backfill_product_traffic_metrics.py
docker cp /opt/qingquan/scripts/tk_daily_quality_check.py qingquan-api-1:/tmp/tk_daily_quality_check.py
echo "==> backfill dry-run"
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/tk_backfill_product_traffic_metrics.py --dry-run | tail -40
echo "==> backfill apply"
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/tk_backfill_product_traffic_metrics.py | tail -15
echo "==> quality"
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/tk_daily_quality_check.py || true
echo "==> traffic nulls after"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT biz_date, count(*) n, count(*) FILTER (WHERE impressions IS NULL) null_imp, count(*) FILTER (WHERE cvr IS NULL) null_cvr FROM tk.fact_tiktok_product_traffic_daily GROUP BY 1 ORDER BY 1 DESC;"
echo DONE