# 服务器：配置 TK 飞书驾驶舱 env 并触发同步
# 在能 SSH 的机器上执行（文档主机：qingquan-sg / 或 root@43.156.50.38）
#
#   bash scripts/server-tk-feishu-sync.sh
#   # 或
#   ssh <host> 'bash -s' < scripts/server-tk-feishu-sync.sh
#
# 前提：/opt/qingquan 为部署目录；API 以 docker compose 或 systemd 运行

set -euo pipefail

APP_DIR="${QINGQUAN_DIR:-/opt/qingquan}"
ENV_FILE="${APP_DIR}/.env"
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"

T1_TABLE="tblwh7EVeAFPfvuy"   # 店铺日经营
T2_TABLE="tblXaQ871ZcrrTPL"   # 广告活动日明细
BASE_TOKEN="C1iHbw6TVad6rUsbZnbc2gSDnHg"

echo "== host $(hostname) =="
echo "== app dir $APP_DIR =="
test -f "$ENV_FILE" || { echo "missing $ENV_FILE"; exit 1; }

upsert_env() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    # portable sed
    sed -i.bak -E "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    echo "updated $key"
  else
    printf '\n%s=%s\n' "$key" "$val" >> "$ENV_FILE"
    echo "appended $key"
  fi
}

# 飞书应用凭证：若服务器已有则保留；仅补 TK 表 id
upsert_env FEISHU_BITABLE_APP_TOKEN_TK "$BASE_TOKEN"
upsert_env FEISHU_BITABLE_TABLE_TK_SHOP_DAILY "$T1_TABLE"
upsert_env FEISHU_BITABLE_TABLE_TK_ADS_CAMPAIGN "$T2_TABLE"

# 若 FEISHU_APP_ID 为空，提示人工填（不把密钥写进脚本仓库）
if ! grep -qE '^FEISHU_APP_ID=.+' "$ENV_FILE"; then
  echo "WARN: FEISHU_APP_ID empty — set app id/secret on server before sync works"
fi

echo "== FEISHU_* (masked) =="
grep -E '^FEISHU_' "$ENV_FILE" | sed -E 's/(SECRET|TOKEN)=.+/\1=***/'

# 重启 API / worker 使 env 生效
if command -v docker >/dev/null 2>&1 && [[ -f "$COMPOSE_FILE" ]]; then
  echo "== docker compose restart api worker =="
  cd "$APP_DIR"
  docker compose restart api worker 2>/dev/null || docker-compose restart api worker 2>/dev/null || true
elif systemctl list-units --type=service 2>/dev/null | grep -q qingquan; then
  echo "== systemctl restart qingquan* =="
  systemctl restart qingquan-api qingquan-worker 2>/dev/null || systemctl restart qingquan 2>/dev/null || true
else
  echo "WARN: cannot auto-restart; restart API/worker manually after env change"
fi

sleep 3
echo "== health =="
curl -fsS https://qingquan.jmzlai.com/health || curl -fsS http://127.0.0.1:8000/health || true
echo

# 触发同步（需 admin 登录；从 env 读默认账号或外部传入）
ADMIN_USER="${ADMIN_USERNAME:-admin}"
ADMIN_PASS="${ADMIN_PASSWORD:-}"
if [[ -z "$ADMIN_PASS" ]]; then
  ADMIN_PASS=$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
fi
API="${QINGQUAN_API:-https://qingquan.jmzlai.com}"

if [[ -z "$ADMIN_PASS" ]]; then
  echo "WARN: no ADMIN_PASSWORD; skip auto export. Call export API manually."
  exit 0
fi

TOKEN=$(curl -fsS -X POST "$API/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)

if [[ -z "$TOKEN" ]]; then
  echo "WARN: login failed; skip export trigger"
  exit 0
fi

for KEY in tk_ads_campaign tk_shop_daily; do
  echo "== export $KEY =="
  curl -fsS -X POST "$API/api/v1/export/feishu" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"table_key\":\"$KEY\",\"mode\":\"incremental\",\"lookback_days\":60,\"limit\":2000,\"dry_run\":false,\"run_inline\":true}" \
    | python3 -m json.tool || true
  echo
done

echo "DONE. Check Feishu:"
echo "  T1 https://dcnkj1up67d5.feishu.cn/base/${BASE_TOKEN}?table=${T1_TABLE}"
echo "  T2 https://dcnkj1up67d5.feishu.cn/base/${BASE_TOKEN}?table=${T2_TABLE}"
