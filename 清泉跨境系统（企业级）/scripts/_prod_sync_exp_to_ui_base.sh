#!/usr/bin/env bash
# Sync experience daily into the Base the user opened (LzTA... / tblSyTlj...)
set -euo pipefail
ENV=/opt/qingquan/.env

UI_BASE=LzTAbQsThaPOzis2lFvciDMlnyh
UI_TABLE=tblSyTljO6C6tRaY

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$ENV"; then
    sudo sed -i "s|^${k}=.*|${k}=${v}|" "$ENV"
  else
    echo "${k}=${v}" | sudo tee -a "$ENV" >/dev/null
  fi
  echo "SET $k=$v"
}

echo "=== before ==="
grep -E '^FEISHU_BITABLE_APP_TOKEN_TK=|^FEISHU_BITABLE_APP_TOKEN=|^FEISHU_BITABLE_TABLE_TK_EXPERIENCE' "$ENV" || true

# Keep generic app token if used elsewhere; force TK token to the UI Base
set_kv FEISHU_BITABLE_APP_TOKEN_TK "$UI_BASE"
set_kv FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY "$UI_TABLE"

# clear map so rows recreate on new base/table
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "DELETE FROM public.sync_feishu_map WHERE table_key = 'tk_experience_daily';"

docker restart qingquan-api-1
sleep 12
curl -sS -m 8 http://127.0.0.1:8000/health; echo

# re-hotdeploy after restart
docker cp /tmp/bitable.py qingquan-api-1:/app/app/adapters/feishu/bitable.py
docker cp /tmp/tk_feishu_sync.py qingquan-api-1:/app/app/jobs/tk_feishu_sync.py
docker cp /tmp/config.py qingquan-api-1:/app/app/config.py
docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py
docker cp /tmp/_prod_list_exp_tables.py qingquan-api-1:/tmp/list_exp.py

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("tk_token", (s.feishu_bitable_app_token_tk or "")[:16], "len", len(s.feishu_bitable_app_token_tk or ""))
print("table", s.feishu_bitable_table_tk_experience_daily)
PY

# verify table visible
set -a; . /opt/qingquan/.env; set +a
docker exec -e FEISHU_APP_ID -e FEISHU_APP_SECRET -e FEISHU_BITABLE_APP_TOKEN_TK -e FEISHU_BITABLE_APP_TOKEN \
  -w /app qingquan-api-1 python /tmp/list_exp.py | tail -30

echo "=== sync ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py

echo "=== map after ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT table_key, table_id, count(*) FROM public.sync_feishu_map WHERE table_key='tk_experience_daily' GROUP BY 1,2;"

echo "SYNC_UI_BASE_DONE"
