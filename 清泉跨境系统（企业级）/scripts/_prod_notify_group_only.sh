#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/qingquan/.env
set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$ENV"; then
    sudo sed -i "s|^${k}=.*|${k}=${v}|" "$ENV"
    echo "UPD $k=$v"
  else
    echo "${k}=${v}" | sudo tee -a "$ENV" >/dev/null
    echo "ADD $k=$v"
  fi
}
set_kv TK_NOTIFY_IM false
set_kv TK_NOTIFY_WEBHOOK true
grep -E '^TK_NOTIFY_IM=|^TK_NOTIFY_WEBHOOK=' "$ENV" || true
if grep -qE '^FEISHU_BOT_WEBHOOK_TK_HEALTH=.+' "$ENV"; then echo FEISHU_BOT_WEBHOOK_TK_HEALTH=SET; else echo FEISHU_BOT_WEBHOOK_TK_HEALTH=EMPTY; fi

cd /opt/qingquan/deploy
set -a; . /opt/qingquan/.env; set +a
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
sleep 5
if [ -f /tmp/_prod_smoke_hotdeploy.sh ]; then
  bash /tmp/_prod_smoke_hotdeploy.sh | tail -15
fi
curl -sS -m 8 http://127.0.0.1:8000/health; echo
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("im", s.tk_notify_im, "wh", s.tk_notify_webhook, "webhook_set", bool(s.feishu_bot_webhook_tk_health))
PY
