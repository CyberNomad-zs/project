#!/usr/bin/env bash
# 在 Linux 云主机上安装「赛狐下架监测」常驻服务。
# 用法（在解压后的项目根，或 pack 出来的目录内）:
#   sudo bash deploy/install-sellfox-linux.sh
#   sudo bash deploy/install-sellfox-linux.sh /opt/temu-monitor
set -euo pipefail

INSTALL_DIR="${1:-/opt/temu-monitor}"
SERVICE_NAME="temu-sellfox"
SERVICE_USER="${SELLFOX_USER:-temu}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "请用 root 运行: sudo bash $0 $*"
    exit 1
  fi
}

check_node() {
  if ! command -v node >/dev/null 2>&1; then
    echo "未找到 node。请先安装 Node.js 18+（推荐 20 LTS）:"
    echo "  # Debian/Ubuntu 示例"
    echo "  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"
    echo "  apt-get install -y nodejs"
    exit 1
  fi
  local major
  major="$(node -p "process.versions.node.split('.')[0]")"
  if [[ "$major" -lt 18 ]]; then
    echo "Node $(node -v) 过旧，需要 >= 18（原生 fetch）"
    exit 1
  fi
  echo "Node: $(node -v)  OK"
  echo "可执行文件: $(command -v node)"
}

echo "=== Temu Sellfox 安装 ==="
echo "源目录: $SRC_ROOT"
echo "安装到: $INSTALL_DIR"
need_root "$@"
check_node

# 系统用户（无登录 shell）
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$SERVICE_USER" || \
    useradd --system --home-dir "$INSTALL_DIR" --shell /bin/false "$SERVICE_USER"
  echo "已创建用户 $SERVICE_USER"
fi

mkdir -p "$INSTALL_DIR" "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

# 同步代码（不覆盖已有密钥配置与状态）
rsync -a --delete \
  --exclude 'node_modules' \
  --exclude '.userdata' \
  --exclude 'logs' \
  --exclude 'data' \
  --exclude 'capture' \
  --exclude 'sellfox.config.json' \
  --exclude 'config.json' \
  --exclude 'openapi.config.json' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  "$SRC_ROOT/" "$INSTALL_DIR/"

mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

# 首次：从 example 生成配置（不覆盖）
if [[ ! -f "$INSTALL_DIR/sellfox.config.json" ]]; then
  if [[ -f "$INSTALL_DIR/sellfox.config.example.json" ]]; then
    cp "$INSTALL_DIR/sellfox.config.example.json" "$INSTALL_DIR/sellfox.config.json"
    echo "已生成 $INSTALL_DIR/sellfox.config.json —— 请填写 clientId/clientSecret/feishuWebhooks"
  else
    echo "缺少 sellfox.config.example.json"
    exit 1
  fi
else
  echo "保留已有 sellfox.config.json"
fi

NODE_BIN="$(command -v node)"
UNIT_SRC="$INSTALL_DIR/deploy/sellfox.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"

# 按本机路径改写 unit
sed \
  -e "s|WorkingDirectory=/opt/temu-monitor|WorkingDirectory=${INSTALL_DIR}|g" \
  -e "s|User=temu|User=${SERVICE_USER}|g" \
  -e "s|Group=temu|Group=${SERVICE_USER}|g" \
  -e "s|ExecStart=/usr/bin/node|ExecStart=${NODE_BIN}|g" \
  -e "s|ReadWritePaths=/opt/temu-monitor/data /opt/temu-monitor/logs|ReadWritePaths=${INSTALL_DIR}/data ${INSTALL_DIR}/logs|g" \
  -e "s|file:///opt/temu-monitor/SELLFOX.md|file://${INSTALL_DIR}/SELLFOX.md|g" \
  "$UNIT_SRC" > "$UNIT_DST"

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
# 配置含密钥，收紧权限
chmod 600 "$INSTALL_DIR/sellfox.config.json" 2>/dev/null || true
chmod 755 "$INSTALL_DIR"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "=== 安装完成（尚未启动，先配密钥与白名单）==="
echo ""
echo "1) 查本机公网出口 IP（填进赛狐开放平台 IP 白名单）:"
echo "   curl -4 -s ifconfig.me ; echo"
echo "   # 或: curl -4 -s https://api.ip.sb/ip"
echo ""
echo "2) 编辑配置:"
echo "   sudo -u $SERVICE_USER nano $INSTALL_DIR/sellfox.config.json"
echo "   # clientId / clientSecret / feishuWebhooks / stores"
echo ""
echo "3) 先手动测一轮（确认白名单+密钥）:"
echo "   cd $INSTALL_DIR && sudo -u $SERVICE_USER $NODE_BIN src/sellfox/cli.js probe"
echo "   cd $INSTALL_DIR && sudo -u $SERVICE_USER $NODE_BIN src/sellfox/cli.js once"
echo ""
echo "4) 启动常驻:"
echo "   sudo systemctl start $SERVICE_NAME"
echo "   sudo systemctl status $SERVICE_NAME"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "常用:"
echo "   systemctl restart $SERVICE_NAME"
echo "   systemctl stop $SERVICE_NAME"
echo "   tail -f $INSTALL_DIR/data/monitor.log"
