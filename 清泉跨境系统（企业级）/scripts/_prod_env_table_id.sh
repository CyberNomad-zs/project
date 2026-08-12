#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/qingquan/.env
add_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$ENV" 2>/dev/null; then
    cur=$(grep "^${k}=" "$ENV" | head -1 | cut -d= -f2-)
    if [ -z "$cur" ]; then
      sudo sed -i "s|^${k}=.*|${k}=${v}|" "$ENV"
      echo "UPDATED $k"
    else
      echo "KEEP $k (already set)"
    fi
  else
    echo "${k}=${v}" | sudo tee -a "$ENV" >/dev/null
    echo "APPENDED $k"
  fi
}
add_kv FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY tblSyTljO6C6tRaY
add_kv TK_NOTIFY_WEBHOOK true
add_kv TK_NOTIFY_IM true
for k in FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY TK_NOTIFY_WEBHOOK TK_NOTIFY_IM FEISHU_IM_RECEIVE_ID FEISHU_BOT_WEBHOOK_TK_HEALTH FEISHU_APP_ID; do
  if grep -qE "^${k}=.+" "$ENV"; then echo "$k=SET"; else echo "$k=EMPTY"; fi
done

cd /opt/qingquan/deploy
set -a; . /opt/qingquan/.env; set +a
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
sleep 4
curl -sS -m 10 http://127.0.0.1:8000/health; echo
bash /tmp/_prod_smoke_hotdeploy.sh
