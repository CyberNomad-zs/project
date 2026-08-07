#!/usr/bin/env bash
# 在清泉服务器上：应用 018 迁移 + 同步代码进 api 容器 + 跑赛狐 TK 同步
set -euo pipefail
ROOT="${QINGQUAN_ROOT:-/opt/qingquan}"
cd "$ROOT"

echo "== apply migration 018 =="
docker cp "$ROOT/backend/migrations/018_tk_sellfox_facts.sql" qingquan-db-1:/tmp/018_tk_sellfox_facts.sql
docker exec qingquan-db-1 psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -f /tmp/018_tk_sellfox_facts.sql

echo "== sync code into api container =="
docker cp "$ROOT/backend/app/adapters/sellfox" qingquan-api-1:/app/app/adapters/sellfox
docker cp "$ROOT/backend/app/jobs/tk_sellfox_sync.py" qingquan-api-1:/app/app/jobs/tk_sellfox_sync.py
docker cp "$ROOT/backend/app/config.py" qingquan-api-1:/app/app/config.py

echo "== run sellfox sync =="
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
  python -m app.jobs.tk_sellfox_sync --days 30

echo "== counts =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT 'profit_shop' AS t, count(*) FROM tk.fact_sellfox_tk_profit_shop
UNION ALL SELECT 'profit_sku', count(*) FROM tk.fact_sellfox_tk_profit_sku
UNION ALL SELECT 'statement', count(*) FROM tk.fact_sellfox_tk_statement
UNION ALL SELECT 'product_sellfox', count(*) FROM tk.fact_tiktok_product WHERE raw_extra->>'source'='sellfox'
UNION ALL SELECT 'finance_daily', count(*) FROM tk.fact_tiktok_finance_daily WHERE raw_extra->>'source'='sellfox'
UNION ALL SELECT 'sync_run', count(*) FROM tk.sellfox_sync_run;
SELECT external_shop_id, name, meta->>'sellfox_shop_id' AS sf_id, meta->>'sellfox_shop_code' AS sf_code
FROM shop WHERE platform='tiktok' ORDER BY name;
"
echo "DONE"
