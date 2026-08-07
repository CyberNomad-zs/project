#!/usr/bin/env bash
set -euo pipefail
ROOT="${QINGQUAN_ROOT:-/opt/qingquan}"
cd "$ROOT"

echo "== docker cp job =="
docker cp "$ROOT/backend/app/jobs/tk_sellfox_sync.py" qingquan-api-1:/app/app/jobs/tk_sellfox_sync.py

echo "== coverage NOW =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan <<'SQL'
SELECT shop_external_id,
       count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>'') AS with_sku
  FROM tk.fact_tiktok_product
 GROUP BY 1 ORDER BY 1;
SELECT count(*) FILTER (
         WHERE seller_sku ~* '(^|\|)(Black|White|Pink|Gray|Grey|Green|Purple)(\||$)'
       ) AS still_colorish
  FROM tk.fact_tiktok_product;
SQL

echo "== run products sync days=90 =="
set -a
# shellcheck disable=SC1091
. "$ROOT/.env"
set +a
docker exec \
  -e PYTHONPATH=/app \
  -e SELLFOX_BASE_URL="${SELLFOX_BASE_URL}" \
  -e SELLFOX_CLIENT_ID="${SELLFOX_CLIENT_ID}" \
  -e SELLFOX_CLIENT_SECRET="${SELLFOX_CLIENT_SECRET}" \
  -e DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://qingquan:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-qingquan}}" \
  -w /app \
  qingquan-api-1 \
  python -m app.jobs.tk_sellfox_sync --only products --days 90

echo "== coverage AFTER =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan <<'SQL'
SELECT shop_external_id,
       count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>'') AS with_sku
  FROM tk.fact_tiktok_product
 GROUP BY 1 ORDER BY 1;
SELECT shop_name, product_id, left(seller_sku,70) AS seller_sku, stock_qty
  FROM tk.fact_tiktok_product
 WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>''
 ORDER BY updated_at DESC NULLS LAST
 LIMIT 12;
SELECT status, stats FROM tk.sellfox_sync_run ORDER BY started_at DESC LIMIT 1;
SQL
echo DONE
