# 流量回插件 + 上下架仍服务器

## Context

本机 Playwright 流量监测用独立 `.userdata` Chrome，和同事日常 Chrome 同账号双端时，会出现会话被踢、进程被挤（`browser has been closed`）、守护黑窗难懂等问题。上下架已在固定 IP 服务器用赛狐跑通，不必再回插件。

**目标分工：**

| 通道 | 职责 |
|------|------|
| **Chrome 插件**（同事日常浏览器） | 仅流量：待关注增加 + 近期下降（可点名）+ 多店空闲轮巡 + 定时必提醒 + 飞书 |
| **服务器 `temu-sellfox`** | 仅上下架点名（赛狐 `selectStatus` 12 进出） |
| **本机 Playwright 流量包** | **停发、停作日常**（代码可留作维护者应急，不推同事） |

已确认：插件**不再**报在售数量下降 / 下架点名（避免与服务器双报）；停发 `temu-traffic-local` 给同事。

---

## 旁路能力说明（不主推）

插件 v10–v13 里还有：

- **前台变体**：打开 `www.temu.com` 商品页，盯颜色/尺码等选项增减  
- **后台 SKU 规格**：从 `pageQuery` 的 `productSkuSummaries` 做同商品规格消失告警  

与「流量待关注 / 近期下降」无关。本次**不删代码**（改动面小、避免回归），但：

- 产品说明 / 打包说明以**后台流量**为准  
- 不要求同事配前台链接  
- popup 可保留显示，但不作为交付验收项  

若以后要精简 UI，再单独砍。

---

## 实现方案

### A. 插件：流量专用版（建议 bgVersion → `v14-仅流量`）

核心改动都在现有 `E:\project\temu\temu-plugin\`，**不必重写**。

#### 1. 关掉下架 / 在售下降告警

`background.js`：

- `_diffAndAlert`：删除或永久关闭 `latest.onSale < snap.onSale` 的 `📉 在售数量下降` 分支  
- `cycleStores`：去掉每店 `scanOnSale` + `diffOnSale`（切店 → `waitForStoreCapture` → 即可；靠 inject 的 countStatus/pageQuery + content chip 刷新流量）  
- `diffOnSale` 可保留死代码或加 `DELIST_IN_PLUGIN = false` 总闸，避免误开  

`content.js`：

- `scanOnSale` 命令可保留但不被 background 调用；或同样用开关短路  

#### 2. 保留流量链路（已有，回归即可）

| 能力 | 已有符号 |
|------|----------|
| chip 待关注 / 下降 | content `readTraffic` / `countDeclineBadges` → `chipStats` |
| 待关注增加 + 点名 | `_diffAndAlert` + `scanWatchViaTab` → `scanWatchList` |
| 下降增加 + 点名 | `_diffAndAlert` + `declineItems` |
| 多店 | `switchTo` / `listStores` / idle `cycleStores`（去掉 scanOnSale 后） |
| 必提醒 | `sendMustRemind` / options 时间 |
| 飞书 | `config.webhook`（options 填写，可与团队共用同一 webhook） |

#### 3. `waitForStoreCapture` 微调

现在等 `latest.onSale` 数字刷新。去掉下架后仍可**继续用 countStatus 的 onSale 作「切店已生效」信号**（不告警，只作就绪），改动最小。备选：改为 `latest.ts` 或 `trafficWatch != null`。

#### 4. 文案与版本

- `bgVersion` → `v14-仅流量`（popup 可辨 SW 是否更新）  
- `manifest.json`：`version`  bump（如 `0.2.0`），`description` 改为只提流量异常，不提在售下架  
- `使用说明.txt`：删「下架点名 / 先轮巡建在售基准」；写清  
  - 装插件 + 开着 goods/list  
  - **关掉本机 Playwright 常驻**，避免双通道飞书  
  - 上下架看服务器，插件不管  
  - 空闲才自动轮巡；人工操作时不会抢切店（仍是会话级，idle 策略保留）  

#### 5. 打包分发

- 用现有 `打包crx.ps1` 或 `Compress-Archive` 打 `temu-plugin` 解压包（推荐加载已解压）  
- 同事：chrome://extensions 开发者模式 → 加载已解压 → 填 webhook → 开 goods/list → 测飞书 / 看 popup `v14-仅流量`  

---

### B. 服务器：不变

- `temu-sellfox` 继续只做 delist/onshelf  
- **不要**在插件再开 diffOnSale  
- 飞书可与插件同群（不同文案：服务器红/绿上下架卡 vs 插件流量卡）或分群，按现网即可  

---

### C. 本机 Playwright 流量：退役日常，不删库

| 动作 | 说明 |
|------|------|
| **停发** `deploy/pack-traffic-local.ps1` 给同事 | 脚本可留，README 标「维护者应急，非日常」 |
| 更新 `temu-monitor/使用说明.txt`、`PLUGIN_PARITY.md`、`README` | 主路径 = 插件流量 + 服务器上下架；Playwright once/start 仅开发/应急 |
| 同事机 | 取消计划任务 TemuMonitor、停 run-forever、可卸本机包（保留也行但不要 start） |
| 代码 | `src/run.js` 浏览器流量逻辑**保留**，便于 DOM 回归；默认不推使用 |

---

### D. 明确不做什么（本次）

- 不把赛狐搬回插件  
- 不要求插件与 Playwright 双开  
- 不重做前台变体 / SKU（不删、不验收）  
- 不改服务器 sellfox 业务逻辑  

---

## 关键文件

| 路径 | 变更 |
|------|------|
| `temu-plugin/background.js` | 关 onSale 告警、cycle 去 scanOnSale、bgVersion v14 |
| `temu-plugin/content.js` | 可选：scanOnSale 短路（非必须） |
| `temu-plugin/manifest.json` | version/description |
| `temu-plugin/使用说明.txt` | 流量-only + 与 Playwright/服务器分工 |
| `temu-plugin/popup.js` / `options` | 文案：弱化下架；popup 仍可显示在售数字作参考 |
| `temu-monitor/PLUGIN_PARITY.md` | 改为主路径插件+服务器 |
| `temu-monitor/使用说明.txt` | 标退役 / 仅应急 |
| `temu-monitor/deploy/pack-traffic-local.ps1` 或 README | 注明勿作日常分发 |
| 可选 memory | 更新项目记忆中的主路径 |

---

## 验证

1. **插件（本机或同事）**  
   - 关开扩展 → popup `后台：v14-仅流量`  
   - 开 `goods/list`，各店 chip 有待关注/下降数字  
   - 测试飞书 OK  
   - 手动「轮巡所有店」：只切店刷新，**不**再扫在售清单、不发下架卡  
   - 人为把某店 trafficWatch 基准调低或等真实增加：应出待关注告警（可带链接）  
   - 在售从 13→12：**插件不发**在售下降；服务器赛狐若检出下架仍发服务器卡  

2. **双通道防重**  
   - 同事机确认无 `node … cli.js start` / 无 TemuMonitor 任务  

3. **服务器**  
   - `systemctl status temu-sellfox` 仍 active（不改代码则仅冒烟）  

4. **回归风险**  
   - MV3：必须**关开插件开关**重建 SW，仅点 ↻ 不够  
   - 空闲轮巡仍会切店：验收时注意 idle 4 分钟策略未改  

---

## 同事迁移步骤（交付时写进说明）

1. 停本机监测：关守护/前台常驻；计划任务「取消开机自启」  
2. 装/重载 `temu-plugin`（v14）  
3. options 填飞书 webhook（可与原 config.json 同群）  
4. 保持 Chrome + `goods/list` 标签  
5. 点测试飞书；看 popup 三店数据  
6. 本机 Playwright 包可删可留，**不要再 start**  

---

## 实施顺序

1. 改 `background.js` 告警与 cycle（核心）  
2. bump manifest + bgVersion + 使用说明  
3. 改 temu-monitor 文档 / 分发策略  
4. 打插件 zip 自测  
5. 发同事 + 确认服务器卖狐仍跑、本机 Playwright 已停  
