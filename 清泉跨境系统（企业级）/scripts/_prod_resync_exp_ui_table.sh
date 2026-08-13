#!/usr/bin/env bash
set -euo pipefail

# Ensure files are in place (host + container)
sudo cp /tmp/bitable.py /opt/qingquan/backend/app/adapters/feishu/bitable.py
sudo cp /tmp/tk_feishu_sync.py /opt/qingquan/backend/app/jobs/tk_feishu_sync.py
sudo cp /tmp/config.py /opt/qingquan/backend/app/config.py

docker cp /tmp/bitable.py qingquan-api-1:/app/app/adapters/feishu/bitable.py
docker cp /tmp/tk_feishu_sync.py qingquan-api-1:/app/app/jobs/tk_feishu_sync.py
docker cp /tmp/config.py qingquan-api-1:/app/app/config.py
docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py

# Force table id to UI table
TARGET=tblSyTljO6C6tRaY
ENV=/opt/qingquan/.env
if grep -q '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' "$ENV"; then
  sudo sed -i "s|^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=.*|FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=${TARGET}|" "$ENV"
else
  echo "FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=${TARGET}" | sudo tee -a "$ENV" >/dev/null
fi
echo "env table:"
grep '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' "$ENV"

# Restart so Settings reloads env (then re-copy hot files after restart)
docker restart qingquan-api-1
sleep 12
curl -sS -m 8 http://127.0.0.1:8000/health; echo

# re-apply hot files after restart (image may overwrite mount? use docker cp always)
docker cp /tmp/bitable.py qingquan-api-1:/app/app/adapters/feishu/bitable.py
docker cp /tmp/tk_feishu_sync.py qingquan-api-1:/app/app/jobs/tk_feishu_sync.py
docker cp /tmp/config.py qingquan-api-1:/app/app/config.py
docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("table", s.feishu_bitable_table_tk_experience_daily)
print("has mapper", hasattr(__import__("app.adapters.feishu.bitable", fromlist=["x"]), "tk_shop_daily_to_fields"))
print("exp mapper", hasattr(__import__("app.adapters.feishu.bitable", fromlist=["x"]), "tk_experience_daily_to_fields"))
PY

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py
echo "RESYNC_UI_TABLE_DONE"
