# 限流分级 v16 + 飞书多维表/任务同步

## Context

用户要替换现有「一刀切流量告警」为分级限流规则，并同步飞书：

| 等级 | 条件（均须：在售 + 已有限流信号） |
|------|----------------------------------|
| **严重（红）** | SKU 货号以 `VIP` 开头（自有），**或** SKU 货号以 `JM` 开头且带「热销款」标签（黑猫） |
| **一般（橙）** | 有限流（待关注 / 近期下降），但不满足严重条件 |

推送节奏：**保持即时告警** + **09:30 / 16:30 两次汇总**（与上轮固定节点有差异才推差异条目）。  
同步：每次提醒后写入**飞书多维表格**（按严重等级降序、带店铺），并创建**飞书任务**待办。  
范围：仅在售；已下架不纳入（延续 v15）。

当前缺口：
- 插件只抓 `productId/skc/name/watch/decline`，**不读 SKU 货号、热销款**
- `pageQuery` 原始有 `productSkuSummaries[].extCode`，`parsePageQuery` 丢掉了
- 飞书只有群机器人卡片，**无** app 鉴权 / 多维表 / 任务 API
- 定时必提醒只报店级计数，不做限流差异汇总

## 推荐方案（插件 v16 内闭环）

主路径仍是 **temu-plugin**（流量日常）。在插件内完成：抓货号+热销 → 分级 → 即时/定点卡片 → 多维表 + 任务。  
凭证存 `chrome.storage.local`（本机），不上传自建服务器。  
不把 `app_secret` 写进仓库；options 页本地填写。

```
goods/list DOM + pageQuery
        │
        ▼
  在售 ∩ (待关注|近期下降)
        │
        ▼
  分级：VIP* 或 (JM* ∧ 热销款) → red；其余 → orange
        │
        ├─ 即时：新 productId 冷却内首次 → 红/橙卡片
        ├─ 09:30 / 16:30：与上轮 slot 快照 diff → 只推差异
        └─ 每次有推送：写多维表（upsert）+ 建飞书任务
```

## 严重判定细则

对每条**在售且有限流**商品：

1. 收集该商品全部 SKU 货号（优先 DOM「SKU货号」列；并用 `pageQuery` 的 `extCode` 补全）
2. `skuCodes.some(c => /^VIP/i.test(c))` → **严重**
3. 否则 `skuCodes.some(c => /^JM/i.test(c)) && hotSale === true` → **严重**
4. 否则 → **一般**
5. 无限流信号或不在售 → 不入池

「限流信号」= 行内「商品流量待关注」或「商品流量近期有下降」（与现逻辑一致；主动 scan 待关注 chip 仍先切「在售中」）。

## 实现步骤

### 1. 抓取扩展（content + background parse）

**`temu-plugin/content.js`**
- `scanProducts` 增加：
  - `skuCodes: string[]`：从商品行/合并行读「SKU货号」列文本（截图列明确）
  - `hotSale: boolean`：行内是否含「热销款」徽标（与「在售」并列）
- `pickItem` 带上 `skuCodes`、`hotSale`
- 主动 `scanWatchList` 结果同样带这两个字段

**`temu-plugin/background.js` · `normalizeSku` / `parsePageQuery`**
- SKU 增加 `extCode`（`sku.extCode`）
- product 汇总 `skuCodes`（去重）
- 把最新 pageQuery 的 `skuCodes` 按 `productId` 合并进 `latest.watchItems` / 分级池（DOM 缺货号时兜底）

### 2. 分级引擎（background 新纯函数）

新建内联或 `classifyTraffic.js`（importScripts）：

```js
function classifySeverity({ skuCodes, hotSale }) {
  const codes = (skuCodes || []).map(String);
  if (codes.some((c) => /^VIP/i.test(c.trim()))) return 'severe';
  if (hotSale && codes.some((c) => /^JM/i.test(c.trim()))) return 'severe';
  return 'general';
}
```

告警文案：
- 严重：`🔴 严重限流` + 原因（自有VIP / 黑猫JM+热销）
- 一般：`🟠 一般限流`
- 卡片 template：`red` / `orange`
- 行内仍带店铺名、编辑链接、SKC、货号

即时路径改造 `_diffAndAlert`：
- 仍按 productId + 6h 冷却（v15）
- 仅对**在售限流**条目分级后推送；文案用红/橙
- 取消「纯 chip 计数上升无明细也推」的噪音（v15 已偏静默，保持）

### 3. 定点两次汇总（改造 mustRemind）

现有 `mustRemind` 09:30 / 16:30 保留「存活汇报」，并扩展为**限流差异汇总**：

- 每店维护 `snapshot.slotTrafficMap`：`{ [productId]: { severity, name, skc, skuCodes, hotSale, kinds } }`
- 定点触发时：
  1. 用当前 `latest` 在售限流池（watchItems∪declineItems，已过滤下架）做分级 → `currMap`
  2. 与 `slotTrafficMap` diff：新增 / 等级升级（general→severe）/ 消失（可选：汇总里提一句「解除 N 条」，默认也报）
  3. **有差异才推**差异卡片（红条优先排序）；无差异只发简短存活卡（或一行「限流无变化」）
  4. 写回 `slotTrafficMap = currMap`
- 排序：严重在前，一般在后；同级按店名

### 4. 飞书多维表 + 任务

**新模块 `temu-plugin/feishuApp.js`**（importScripts）：

| 能力 | API（开放平台） |
|------|----------------|
| token | `POST /open-apis/auth/v3/tenant_access_token/internal` |
| 多维表查/增/更 | bitable `app_token` + `table_id`：按「店铺+productId」查重 → 有则 update，无则 create |
| 任务 | task v2 创建任务（标题含等级/店/商品；描述含编辑链接） |

**options 新增配置（本地）：**
- `feishuAppId` / `feishuAppSecret`
- `bitableAppToken` / `bitableTableId`
- `bitableTodoEnabled`（是否建任务）
- 可选：`taskGuid` / 任务清单 id（若开放平台要求归属）

**多维表建议字段（创建时对齐，用户表已有则映射）：**

| 字段 | 类型 |
|------|------|
| 店铺 | 文本 |
| 商品名 | 文本 |
| productId | 文本（唯一键一部分） |
| SKC | 文本 |
| SKU货号 | 文本（多货号逗号） |
| 限流类型 | 单选：待关注 / 近期下降 / 两者 |
| 严重等级 | 单选：严重 / 一般 |
| 热销款 | 复选 |
| 编辑链接 | URL |
| 最近推送时间 | 日期 |

写入前按「严重 → 一般」排序批量提交；更新已存在行的等级/时间，避免重复堆行。

**任务：**
- 仅**新增或升级为严重**时建任务（避免一般限流刷任务）；标题：`[严重限流] 店名 · 商品名`
- 可选：一般限流只写表不建任务（配置开关，默认严重才建）

**权限提示（使用说明）：** 应用需开通 bitable 读写、task 创建；把应用做成多维表协作者。

### 5. 版本与文档

- `bgVersion`: `v16-限流分级`
- `manifest.version`: `0.2.2`
- 更新 `使用说明.txt`、memory `temu-plugin-versions` / `traffic-plugin-primary`
- options / popup 展示分级说明与飞书应用配置状态（已填/未填）

## 关键文件

| 文件 | 改动 |
|------|------|
| `temu-plugin/content.js` | skuCodes、hotSale 扫描 |
| `temu-plugin/background.js` | parse 保留 extCode；分级；即时文案；slot diff；调 feishuApp |
| `temu-plugin/feishuApp.js` | **新建** token + bitable upsert + task |
| `temu-plugin/options.html` + `options.js` | 应用/表配置项 |
| `temu-plugin/manifest.json` | 0.2.2；host 已有 open.feishu.cn |
| `temu-plugin/使用说明.txt` | v16 规则与配置步骤 |
| memory 版本记录 | v16 条目 |

不改 sellfox 服务器（下架通道无关）；不恢复本机 Playwright 日常流量。

## 不在本期

- 近 7 天销量（已改为 JM+热销款）
- 把 app_secret 放到公司服务器中转（若后续要多同事共用同一应用再拆）
- 修改已有多维表字段名以外的业务流程（字段映射可配置化最小集）

## 验证

1. chrome://extensions **关开**插件 → popup 显示 `v16-限流分级`
2. 打开 goods/list「在售中」：
   - VIP 货号 + 待关注/下降 → 红卡「严重·自有」
   - JM 货号 + 热销款 + 限流 → 红卡「严重·黑猫」
   - 其它限流在售 → 橙卡「一般」
   - 已下架限流 → 不出现
3. 同一 productId 6h 内切店不重复即时推
4. 手动 `mustRemindNow`：无变化只存活；改一条等级后再点 → 只推差异
5. 多维表出现/更新对应行；严重新建飞书任务
6. 未填 app 配置时：卡片仍发，表/任务跳过并 log，不阻断告警

## 交付前需用户提供（实施时填 options，不进 git）

- 飞书企业自建应用 `app_id` / `app_secret`
- 多维表格链接或 `app_token` + `table_id`
- （可选）任务归属清单 id
- 确认表头字段名（若与上表不一致，做一层映射）
