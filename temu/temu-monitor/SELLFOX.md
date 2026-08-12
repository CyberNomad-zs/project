# 赛狐 OpenAPI · Temu 上下架监测

挂在 `temu-monitor` 下，用赛狐多平台接口做 **在售集合 diff → 下架 / 上架告警**，飞书复用本项目 `feishu.js`。

## 能做什么 / 不能做什么

| 能力 | 支持 |
|------|------|
| 下架点名（离开 `selectStatus=12`） | ✅ |
| 上架点名（新进 `selectStatus=12`，含重新上架） | ✅ |
| 多店（Agnis / HomeCove / Twilight Cove） | ✅ |
| 服务器轮询、不依赖 Chrome | ✅ |
| 限流 / 商品流量待关注 | ❌ 继续插件 |
| 流量近期下降 | ❌ 继续插件 |

在售定义：赛狐 Temu 跨境父体 **`selectStatus === "12"`**（已加入站点）。  
与卖家后台页签「在售中」多数时候对齐，但赛狐同步可能短暂超前/抖动，**不能 100% 当后台 count**。  
- **下架**：上轮在售，且本轮结果里**仍能看到该 SKC**、状态已不是 12（常见变 13）  
- **上架**：本轮在售集合里有、上轮没有，且 **连续两轮仍为 12** 才告警（首轮进 `pendingOnshelf`，次轮确认；抖动自动丢弃）  
- **防误报**：若本轮全量 unique / 本店 allCount 骤降，或在售 SKC 从结果中「失踪」（漏拉），**跳过本轮、不告警、不改坏基准**  
  （2026-07-30 实锤：unique 954→918 导致 HomeCove 假下架 5 + 假上架 5）  
  （2026-08-05 实锤：HomeCove 单轮 +4 上架，同事只上 1 个、后台仍 15；改为上架二次确认）

实调：Agnis 在售 13 与后台 countStatus 一致。

## 配置

```bash
cd temu-monitor
npm run sellfox:init
# 编辑 sellfox.config.json（已 gitignore）
```

`clientId` / `clientSecret` 与 `E:\project\海外仓\sellfox-bridge` 相同即可。  
`shopId`：396706 Agnis / 398202 HomeCove / 398203 Twilight Cove。

```json
"alerts": {
  "delist": true,
  "onshelf": true
}
```

飞书：本文件 `feishuWebhooks` 或主 `config.json` 的 webhook。  
卡片：仅下架红 / 仅上架绿 / 同轮混合橙。

## 命令

```bash
npm run sellfox:probe   # 只读分布
npm run sellfox:dry     # diff 不写状态、不发飞书
npm run sellfox:once    # 正式一轮（首轮只建基准）
npm run sellfox:start   # 常驻
```

## 服务器部署（推荐）

本地宽带 IP 常变会导致赛狐 **IP 白名单**反复重申。  
本模块是**纯 HTTP**（Node 内置 fetch，**不需要 Chrome / Playwright / npm 依赖**），适合挂在固定公网 IP 的 Linux 云主机上用 systemd 常驻。

完整步骤见：

- **`deploy/README-SERVER.md`** — 买机、白名单、打包上传、验收、运维
- `deploy/pack-sellfox.ps1` — 本机打精简 zip（不含密钥）
- `deploy/install-sellfox-linux.sh` — 服务器安装 + 注册 `temu-sellfox` 服务
- `deploy/sellfox.service` — systemd 单元模板

摘要：

```powershell
# 本机打包
powershell -File deploy\pack-sellfox.ps1
scp _dist\temu-sellfox-linux-*.zip user@SERVER:/tmp/
scp sellfox.config.json user@SERVER:/tmp/
```

```bash
# 服务器
unzip /tmp/temu-sellfox-linux-*.zip -d /tmp/temu-sellfox
cd /tmp/temu-sellfox && sudo bash deploy/install-sellfox-linux.sh
sudo cp /tmp/sellfox.config.json /opt/temu-monitor/sellfox.config.json
# 赛狐后台把 curl -4 ifconfig.me 的 IP 加白名单
sudo -u temu node /opt/temu-monitor/src/sellfox/cli.js probe
sudo systemctl enable --now temu-sellfox
```

限流 / 流量待关注仍用本机 Chrome 插件；服务器负责上下架。

## 接口与约束

- `POST /api/multiplatform/temu/product/getParentPageList.json`
- `dateType` 建议 **`updateDate`**（比 createDate 覆盖全）
- 起止日期间隔 **≤ 30 天**（代码自动滑窗）
- **IP 白名单**：填服务器固定公网出口；可与 sellfox-bridge 共用 client，白名单做并集

## 状态

`data/sellfox-state.json`：按 `shopId` 存 `onSaleMap`。删掉即重置基准（下一轮重新建基准、不告警）。

## 与插件 / Partner

| | 赛狐（本模块） | Chrome 插件 | Temu Partner |
|--|----------------|-------------|--------------|
| 下架 / 上架 | 主路径 | 轮巡 DOM 兜底 | 需 Local 权限 |
| 限流 | ❌ | ✅ chip | 有标签则可用 |
| 依赖 | 赛狐授权+白名单 | 浏览器开着 | Partner App |

## 代码

```
src/sellfox/
  client.js    签名与 HTTP
  products.js  滑窗拉取 + 分组
  diff.js      在售 diff（delist + onshelf）
  monitor.js   一轮编排
  config.js
  cli.js
```
