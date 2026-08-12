#!/usr/bin/env bash
# Deploy tk_sellfox_sync (child SKU) and run products-only sync.
set -euo pipefail
ROOT="${QINGQUAN_ROOT:-/opt/qingquan}"
cd "$ROOT"

echo "== docker cp job =="
docker cp "$ROOT/backend/app/jobs/tk_sellfox_sync.py" qingquan-api-1:/app/app/jobs/tk_sellfox_sync.py

echo "== import check =="
docker exec -w /app -e PYTHONPATH=/app qingquan-api-1 \
  python -c 'from app.jobs.tk_sellfox_sync import _parse_child_skus; print(_parse_child_skus([{"msku":"A","skuId":"1","quantity":"2","priceIncludeVat":"1.2","currency":"GBP"}]))'

echo "== product coverage BEFORE =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
"SELECT shop_external_id,
        count(*) AS n,
        count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>'') AS with_sku
   FROM tk.fact_tiktok_product
  GROUP BY 1 ORDER BY 1;"

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

echo "== product coverage AFTER =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
"SELECT shop_external_id,
        count(*) AS n,
        count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>'') AS with_sku
   FROM tk.fact_tiktok_product
  GROUP BY 1 ORDER BY 1;"

echo "== sample rows =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
"SELECT shop_name, product_id, left(seller_sku,60) AS seller_sku, stock_qty, price
   FROM tk.fact_tiktok_product
  WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>''
  ORDER BY updated_at DESC NULLS LAST
  LIMIT 15;"

echo "== last sync run =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
"SELECT status, stats, error_message, started_at, finished_at
   FROM tk.sellfox_sync_run
  ORDER BY started_at DESC LIMIT 1;"

echo DONE
