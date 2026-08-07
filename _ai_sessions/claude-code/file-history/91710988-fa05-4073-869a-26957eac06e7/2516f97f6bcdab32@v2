#!/usr/bin/env bash
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /opt/qingquan/.env
set +a

echo "health:"
curl -sS http://127.0.0.1:8000/health
echo

echo "table:"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='tk' AND table_name='fact_tiktok_order_line' ORDER BY ordinal_position;"

KEY="${INGEST_DEFAULT_API_KEY:?missing INGEST_DEFAULT_API_KEY}"
TS=$(date +%s)
OID=$(printf '57%016d' "$((TS % 10000000000000000))" | cut -c1-18)
SHOP=27328767468273

BODY=$(cat <<EOF
{"items":[{"platform":"tiktok","shop_id":"$SHOP","shop_name":"Gardena","biz_date":"2026-08-05","idempotency_key":"smoke-oline-$TS","payload":{"order_id":"$OID","line_no":1,"line_key":"sku:SMOKE-SKU-1","product_id":"1729000000000001","product_name":"Smoke Product","seller_sku":"SMOKE-SKU-1","sku_id":"88000000000001","quantity":1,"unit_price":1.23,"currency":"GBP"}}]}
EOF
)

echo "POST order_lines oid=$OID"
curl -sS -X POST "http://127.0.0.1:8000/api/v1/ingest/tiktok_order_lines" \
  -H "X-Api-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo

BODY2=$(cat <<EOF
{"items":[{"platform":"tiktok","shop_id":"$SHOP","shop_name":"Gardena","idempotency_key":"smoke-noise-$TS","payload":{"product_id":"name:2 个 SKU展开","product_name":"2 个 SKU展开","currency":"GBP"}}]}
EOF
)

echo "POST noise product"
curl -sS -X POST "http://127.0.0.1:8000/api/v1/ingest/tiktok_products" \
  -H "X-Api-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY2"
echo

docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT seller_sku, product_name, order_id FROM tk.fact_tiktok_order_line WHERE seller_sku='SMOKE-SKU-1' ORDER BY created_at DESC LIMIT 3;"

docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT count(*) AS dirty FROM tk.fact_tiktok_product WHERE product_id LIKE 'name:%SKU%' OR coalesce(product_name,'') LIKE '%SKU展开%';"
