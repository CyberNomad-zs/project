# 赛狐上下架监测 · Linux 服务器部署

本地 IP 常变 → 反复改赛狐 API 白名单。  
把本模块放到**固定公网 IP** 的云主机上，白名单只加一次。

## 为什么只上赛狐

| | 赛狐上下架 | 整套 temu-monitor（含浏览器） |
|--|---------|------------------------------|
| 依赖 | Node 18+ 即可 | Chrome + 登录态 + Playwright |
| 出站 | 赛狐 OpenAPI + 飞书 | + Temu 卖家中心 |
| 白名单 | 固定服务器 IP | 同左 + 浏览器风控 |
| 流量待关注/下降 | ❌ 仍用本机 Chrome 插件 | 服务器上也不稳 |

**推荐：服务器只跑赛狐上下架；限流/待关注继续本机插件。**

## 一、买机与网络

1. 任意轻量 Linux（1 核 1G 足够），系统 Ubuntu 22.04 / Debian 12 等。
2. **要有固定公网 IPv4**（或弹性公网 IP 绑死不换）。
3. 安全组：只需出站 HTTPS（443）。**不需要入站业务端口**（无 Web 服务）。
4. 记下公网 IP，后面填赛狐白名单。

查出口 IP（以实际出网为准）：

```bash
curl -4 -s ifconfig.me; echo
# 或
curl -4 -s https://api.ip.sb/ip
```

若机器走 NAT/共享出口，白名单填**最终出口**，不是内网 IP。

## 二、本机打包上传

在开发机（Windows）项目里：

```powershell
cd E:\project\temu\temu-monitor
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\pack-sellfox.ps1
```

生成 `_dist\temu-sellfox-linux-*.zip`（**不含** `sellfox.config.json` 密钥）。

```powershell
# 代码包
scp _dist\temu-sellfox-linux-XXXX.zip user@YOUR_SERVER_IP:/tmp/

# 密钥配置单独传（权限稍后在服务器收紧）
scp sellfox.config.json user@YOUR_SERVER_IP:/tmp/sellfox.config.json
```

服务器：

```bash
sudo mkdir -p /opt/temu-monitor
cd /tmp
sudo apt-get update && sudo apt-get install -y unzip rsync   # 若无
unzip -o temu-sellfox-linux-*.zip -d /tmp/temu-sellfox
cd /tmp/temu-sellfox
sudo bash deploy/install-sellfox-linux.sh /opt/temu-monitor
# 覆盖安装脚本生成的空配置
sudo cp /tmp/sellfox.config.json /opt/temu-monitor/sellfox.config.json
sudo chown temu:temu /opt/temu-monitor/sellfox.config.json
sudo chmod 600 /opt/temu-monitor/sellfox.config.json
```

`install-sellfox-linux.sh` 会：

- 检查 Node ≥ 18
- 创建系统用户 `temu`
- 同步到 `/opt/temu-monitor`
- 写入 systemd 单元 `temu-sellfox`

若服务器还没 Node：

```bash
# Ubuntu 示例（Node 20）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt-get install -y nodejs
node -v   # 应 >= v18
```

**无需 `npm install`**：赛狐模块只用 Node 内置 `fetch` / `crypto`。

## 三、赛狐 IP 白名单

1. 登录赛狐开放平台 → 应用 / API 安全 → **IP 白名单**。
2. 加入服务器公网 IP（可先 `curl -4 -s ifconfig.me`）。
3. 与 `sellfox-bridge` 若共用同一 `clientId`，白名单是**并集**：服务器 IP + 桥接所在 IP 都要留着（本机动态 IP 可从白名单删掉，省得再改）。

生效一般很快；若 `probe` 仍报 IP/权限类错误，等 1～2 分钟再试。

## 四、验收

```bash
cd /opt/temu-monitor
sudo -u temu node src/sellfox/cli.js probe   # 只读分布
sudo -u temu node src/sellfox/cli.js once    # 正式一轮（首轮只建基准不告警）
sudo systemctl start temu-sellfox
sudo systemctl status temu-sellfox
sudo journalctl -u temu-sellfox -f
# 或
tail -f /opt/temu-monitor/data/monitor.log
```

`probe` 成功应能看到三店 `onSale12` 等分布。  
`once` 首轮：`首轮：建立在售基准 …，不告警`。  
第二轮起有下架才会飞书。

## 五、日常运维

| 操作 | 命令 |
|------|------|
| 看状态 | `systemctl status temu-sellfox` |
| 看日志 | `journalctl -u temu-sellfox -f` |
| 重启 | `systemctl restart temu-sellfox` |
| 停止 | `systemctl stop temu-sellfox` |
| 改配置后 | 改 `sellfox.config.json` → `systemctl restart temu-sellfox` |
| 重置基准 | 删 `data/sellfox-state.json` 后重启（下一轮重新建基准） |
| 更新代码 | 重新 scp zip → `sudo bash deploy/install-sellfox-linux.sh`（保留 config/data）→ restart |

崩溃会由 systemd `Restart=always`（约 30s）拉起；进程内也按 `intervalMinutes`（默认 15）轮询。

## 六、安全注意

- `sellfox.config.json` 含 `clientSecret` 与飞书 webhook → **chmod 600**，勿提交 git、勿打进公开镜像。
- 可用环境变量代替文件里的密钥：`SELLFOX_CLIENT_ID` / `SELLFOX_CLIENT_SECRET`（见 unit 里注释）。
- 服务器不必开放 22 以外入站；建议密钥登录、禁密码。
- 本机开发用的 `sellfox.config.json` 仍可留着调试；上线后本机 IP 可移出白名单。

## 七、目录结构（服务器）

```
/opt/temu-monitor/
  package.json                 # dependencies 为空
  sellfox.config.json          # 密钥，600
  sellfox.config.example.json
  SELLFOX.md
  deploy/
    sellfox.service
    install-sellfox-linux.sh
    README-SERVER.md
  src/
    config.js logger.js feishu.js
    sellfox/                   # client / products / diff / monitor / cli
  data/
    sellfox-state.json         # 在售基准
    monitor.log
  logs/
```

## 八、故障排查

| 现象 | 处理 |
|------|------|
| `code` 含 IP / 白名单 / 无权限 | 核对 `curl -4 ifconfig.me` 与赛狐白名单是否一致 |
| `40019` 限流 | 代码已退避重试；可把 `intervalMinutes` 调到 20～30 |
| 飞书没消息 | 首轮不告警；检查 `feishuWebhooks`；看 log 是否 dry/跳过 |
| `在售疑似不全` 跳过 | 滑窗漏数保护，不改基准；下轮恢复即可 |
| systemctl 起不来 | `journalctl -u temu-sellfox -n 50`；确认 `User=temu` 对目录可写 |
| Node 找不到 | `which node`，改 unit 里 `ExecStart=` 后 `daemon-reload` |

## 九、与本机插件分工

```
服务器 temu-sellfox  ──► 下架 / 上架点名（selectStatus 离开/进入 12）──► 飞书
本机 Chrome 插件     ──► 流量待关注 / 近期下降                       ──► 飞书
```

两边 webhook 可同一群；上下架只保留服务器这一路，避免和旧 Playwright/插件下架逻辑双报。
