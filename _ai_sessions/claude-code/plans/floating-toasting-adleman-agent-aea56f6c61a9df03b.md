# 紫鸟「卖家自研插件」— TikTok UK 广告数据抓取写入飞书多维表格

## Context（项目背景）

公司运营 **3 个英国 TikTok 店铺**，当前通过紫鸟浏览器手动登录各店铺广告后台、逐一导出并整理日报，耗时且易错。目标是在紫鸟 **卖家自研插件**（Chrome 扩展形态）内实现：

1. **手动一键抓取** + **每日 7:00–8:00 定时抓取**
2. 抓取 5 个核心字段：总收入(GMV/销售额)、ROI、销量、广告花费、广告系列名称
3. 写入 **飞书多维表格**（从零设计 schema，3 店汇总一张总表）
4. 安全：运行在紫鸟隔离环境，**不硬编码店铺密码**；飞书密钥仅存 `chrome.storage.local`

**现状**：`E:\project\海外TK店铺广告投流数据自动化监测\` 仅有需求文档（docx/xmind）与紫鸟店铺 ID 接口说明，**无代码**。

**主交付物**：可上传 open.ziniao.com 的 ZIP/CRX 扩展包。  
**可选补充**：本机 ziniao-cli + ZClaw Bridge 做「打开店铺窗口」的外部调度（不替代插件本体）。

参考：
- 紫鸟开放平台：卖家自研插件（与 Chrome 插件标准一致，企业内部使用）
- 接入指南：https://open.ziniao.com/docSupport?docId=121
- 飞书 bitable batch_create：`POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_create`

---

## 1. 推荐架构（MV3 扩展）

### 1.1 总体数据流

```
紫鸟浏览器 · 店铺隔离窗口（已登录 TikTok Seller，无密码）
  [Popup UI] 一键抓取 / 状态 / 预览
       |
  [Service Worker / background]
       |  chrome.alarms (7:00–8:00)
       |  编排 scrape -> normalize -> write Feishu -> log
       v
  [Content Script] 注入 Seller Center / Shop Ads 页面
       |  1) 可选 network intercept（优先）
       |  2) DOM 表格解析（兜底）
       |  3) 列头映射 + 分页 + 日期筛选
       v
  chrome.storage.local  配置 / 最近结果 / 日志环形缓冲
       |
  飞书 OpenAPI  tenant_access_token -> batch_create records
```

### 1.2 模块划分

| 模块 | 路径建议 | 职责 |
|------|----------|------|
| Manifest | `extension/manifest.json` | MV3 权限、content_scripts 匹配、alarms、storage、host_permissions |
| Background SW | `extension/background/service-worker.js` | 消息路由、alarms、token 缓存、写表、重试、日志 |
| Scraper (content) | `extension/content/scraper.js` | 页面内采集：API 嗅探 + DOM |
| Selectors / mappers | `extension/content/selectors.js` + `mappers.js` | 列头别名、URL 白名单、数值清洗 |
| Feishu client | `extension/lib/feishu.js` | token 获取、batch_create、search 去重（可选） |
| Config | `extension/lib/config.js` | storage 读写、默认值、校验 |
| Logger | `extension/lib/logger.js` | 分级日志、环形缓冲、导出 JSON/CSV |
| Popup | `extension/popup/*` | 一键抓取、进度、最近结果、快捷配置入口 |
| Options | `extension/options/*` | 飞书凭证、店铺映射、调度、dry-run、日期策略 |
| Shared messages | `extension/lib/messages.js` | 消息 type 常量与校验 |

### 1.3 Manifest V3 关键权限（原则）

```json
{
  "manifest_version": 3,
  "name": "TK UK Ads to Feishu",
  "version": "0.1.0",
  "permissions": ["storage", "alarms", "scripting", "activeTab", "tabs"],
  "host_permissions": [
    "https://seller*.tiktok.com/*",
    "https://seller-uk.tiktok.com/*",
    "https://*.tiktokglobalshop.com/*",
    "https://ads.tiktok.com/*",
    "https://open.feishu.cn/*"
  ],
  "background": { "service_worker": "background/service-worker.js" },
  "action": { "default_popup": "popup/popup.html" },
  "options_page": "options/options.html",
  "content_scripts": [
    {
      "matches": [
        "https://seller*.tiktok.com/*",
        "https://seller-uk.tiktok.com/*",
        "https://*.tiktokglobalshop.com/*",
        "https://ads.tiktok.com/*"
      ],
      "js": ["content/selectors.js", "content/mappers.js", "content/scraper.js"],
      "run_at": "document_idle"
    }
  ]
}
```

**说明**：
- 实际 host 列表需在 **首次登录测试店铺后** 用 DevTools 确认（英区可能是 `seller.tiktok.com` 带 locale 或 `seller-uk.tiktok.com`）。
- **不要**申请店铺登录相关隐私权限；依赖紫鸟店铺窗口已登录态。
- Network intercept：优先 content 侧 `fetch`/`XHR` 钩子；避免依赖 MV3 blocking webRequest。

### 1.4 消息协议（popup / SW / content）

| 消息 type | 方向 | 载荷要点 |
|-----------|------|----------|
| `SCRAPE_NOW` | popup -> SW | `{ dateFrom?, dateTo?, dryRun?, storeNameOverride? }` |
| `SCRAPE_IN_TAB` | SW -> content | 同上 |
| `SCRAPE_RESULT` | content -> SW | `{ ok, records[], meta, errors[] }` |
| `WRITE_FEISHU` | SW 内部 | records + config |
| `GET_STATUS` | popup -> SW | 返回 lastRun、alarm 下次时间、token 是否有效 |
| `EXPORT_LOGS` | popup -> SW | 返回 logs blob |
| `CONFIG_UPDATED` | options -> SW | 重建 alarms |

---


## 2. 飞书多维表格 Schema（从零设计）

### 2.1 推荐：单表总表（MVP）

**Base 名称**：`TK英区广告日报`  
**数据表名**：`广告系列日报`

| 字段名（飞书列名） | 类型 | 必填 | 说明 |
|-------------------|------|------|------|
| 业务日期 | 日期 | 是 | 广告数据所属日（默认「昨日」或「今日」可配置） |
| 店铺 | 单选 | 是 | 三个店铺选项（可后续改文本） |
| 广告系列名称 | 文本 | 是 | Campaign name（样例中的品名列） |
| 广告花费 | 数字 | 是 | Cost/Spend，货币数值 |
| 销量 | 数字 | 是 | Orders / Units |
| ROI | 数字 | 是 | ROI 数值（如 2.35，非百分比字符串） |
| 总收入 | 数字 | 是 | GMV / 销售额 / 总收入列 |
| 币种 | 单选 | 否 | GBP / USD（英区默认 GBP，可配置） |
| 抓取时间 | 日期时间 | 是 | 插件写入时刻 |
| 来源URL | 文本 | 否 | 排障 |
| 运行ID | 文本 | 否 | 同一次抓取的 UUID，便于回溯 |
| 状态 | 单选 | 是 | success / partial / failed |
| 备注 | 文本 | 否 | 解析异常、列缺失提示 |

**可选第二表（二期）**：`抓取运行日志`  
字段：运行ID、业务日期、店铺、开始/结束时间、条数、成功/失败、错误摘要、dryRun。

### 2.2 样例行（3 店）

| 业务日期 | 店铺 | 广告系列名称 | 广告花费 | 销量 | ROI | 总收入 | 币种 | 状态 |
|---------|------|-------------|---------|------|-----|--------|------|------|
| 2026-07-22 | Deal to deal | 花园拱门7/17 | 128.50 | 36 | 2.41 | 309.68 | GBP | success |
| 2026-07-22 | SHOP INOUT | Summer Dress A | 90.00 | 20 | 1.85 | 166.50 | GBP | success |
| 2026-07-22 | Gardena | Garden Tool Kit | 210.00 | 15 | 1.20 | 252.00 | GBP | success |

> 店铺真实名称以权限开放后后台为准；Options 里用「显示名 <-> 匹配规则」映射。

### 2.3 去重与写入策略

- **业务主键**：`业务日期 + 店铺 + 广告系列名称`
- **MVP**：只 `batch_create` 追加；Options 提供「允许重复」开关
- **Phase 2**：写前 `records/search` 按主键过滤；已存在则 `batch_update` 或跳过
- 批量：每批 100–200 条（远低于 500/1000 上限，降低限流风险）
- 鉴权：`POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`  
  body: `{ app_id, app_secret }`，token 缓存至 `expire - 5min`

### 2.4 飞书侧一次性准备（运维）

1. 创建企业自建应用，开通「多维表格」读写权限并发布版本  
2. 新建多维表格，按上表建字段  
3. 将应用添加为多维表格协作者（可管理/可编辑）  
4. 从 URL 取 `app_token`（`base/xxx`）与 `table_id`（`table/xxx`）  
5. 填入插件 Options（不写进代码仓库）

---

## 3. 抓取策略（TikTok Seller / Shop Ads · UK）

### 3.1 目标页面（以实测为准）

权限到位后，在紫鸟店铺窗口中确认真实入口（典型路径）：

1. Seller Center 登录态  
2. 左侧菜单 **Shop Ads** / **广告** / **GMV Max**  
3. **Campaign list** 列表页（含 Cost、Orders、ROI、GMV/Revenue、Campaign name）  
4. 日期筛选：Yesterday / Custom（默认抓「昨日」以对齐日报）

候选 URL 模式：
- `https://seller.tiktok.com/*`
- `https://seller-uk.tiktok.com/*`
- `https://*.tiktokglobalshop.com/*`
- `https://ads.tiktok.com/*`（若跳转 Ads Manager）

**实施前阻塞项**：张威开放 3 店测试权限后，用 1 个店铺完整走通一次，导出：
- 最终 URL
- Network 里返回列表的 XHR（JSON 字段名）
- 表头 DOM 文本（中英）

### 3.2 双通道采集（优先 API，DOM 兜底）

#### 通道 A：Network intercept（首选）

在 content script 注入前 hook `window.fetch` / `XMLHttpRequest`。  
匹配 URL 关键字（可配置）：`campaign` / `gmv_max` / `shop_ads` / `stat` / `report` / `list`。

标准字段别名示例（实测后固化）：

| 标准字段 | 常见后端/表头别名 |
|----------|------------------|
| campaignName | campaign_name, name, campaignName |
| spend | cost, spend, ad_spend, stat_cost |
| orders | orders, order_cnt, sales_count, units |
| roi | roi, ROI（注意 ROAS 不等于 ROI） |
| gmv | gmv, revenue, total_revenue |

**注意**：Product GMV Max 的 ROI 定义可能含 organic/affiliate 归因；以 Seller Center 当前列说明为准。

#### 通道 B：DOM 表格解析（兜底）

1. 等待主表格容器出现（MutationObserver + 超时 30s）  
2. 读表头文本 -> 别名表映射列索引（中英双语）  
3. 遍历数据行 -> cell 文本 -> `normalizeNumber()`  
4. 分页：下一页按钮 / 滚动加载；最多 N 页（默认 20）  
5. 列缺失：行 `status=partial`，备注写缺失列名

#### 通道 C：导出 CSV（最后手段，二期）

MVP **不做**文件下载主路径。

### 3.3 选择器策略（容忍 UI 变更）

| 层级 | 做法 |
|------|------|
| L1 表头文本 | 不用脆弱 class hash；用 `th` / `[role=columnheader]` 文本匹配 |
| L2 role/aria | `table`、`grid`、`row`、`columnheader` |
| L3 data-* | 若有 `data-testid` / `data-e2e` 优先 |
| L4 结构回退 | 第一列偏名称、数值列按表头；失败则 popup 展示错误 |
| 配置化 | `selectors.js` 导出 `HEADER_ALIASES`、`TABLE_CANDIDATES`，改版只改配置 |

数值清洗：去掉 `£ $ , %`；空/`-` -> null -> partial。

### 3.4 店铺识别

不读店铺密码。优先级：
1. Options 里用户为当前窗口选择的店铺  
2. 页面顶栏店铺名文本匹配 `storeMappings[].matchPatterns`  
3. `document.title` 推断  
失败则 popup 强制选择店铺后再写入。

### 3.5 单次抓取编排（SW）

```
1. 校验配置（飞书 4 件套 + 至少 1 个店铺映射）
2. 找到匹配 content_scripts 的 active tab；否则提示打开 Shop Ads
3. 向 content 发 SCRAPE_IN_TAB（含日期、dryRun）
4. content：确保日期范围 -> 采集 -> 返回 records
5. normalize + 注入 店铺/业务日期/运行ID/抓取时间
6. dryRun：只存结果并在 popup 预览，不写飞书
7. 非 dryRun：batch_create，失败重试
8. 写 lastRun + logs；popup 展示摘要
```

**多店**：插件在 **每个店铺窗口各运行一次**（紫鸟按账号隔离）。3 个窗口各自一键/各自 alarm；总表靠「店铺」字段汇总。不在单个扩展进程内跨账号登录切换。

---


## 4. 调度方案（扩展内 + 可选 CLI）

### 4.1 扩展内：`chrome.alarms`（主方案）

- Options：`scheduleEnabled`、`scheduleHourStart=7`、`scheduleHourEnd=8`、`timezone`（默认 `Asia/Shanghai`，可改为 `Europe/London`）  
- SW `onInstalled` / `CONFIG_UPDATED`：创建 alarm `daily-scrape`  
  - `periodInMinutes: 1440`，或每天计算下次 7:00–8:00 内随机分钟  
- `onAlarm`：若当前时间在 [7,8) 且今日未成功跑过 -> `SCRAPE_NOW`  
- **硬性前提**：
  1. 紫鸟浏览器进程在线  
  2. 对应店铺窗口已打开且 Seller 登录未过期  
  3. Service Worker 可被 alarm 唤醒（MV3 支持）

**无法保证完全无人值守**：电脑休眠、紫鸟未开、店铺未登录时定时失败。应对：失败写本地 log、popup 红点「今日未抓取」、Phase2 飞书 webhook 告警。

### 4.2 可选 CLI 互补（非主交付）

Windows 任务计划在 7:05 执行：

```
ziniao store list -> 对 3 个 storeId 依次 store open
-> page visit 到 Shop Ads URL
-> 等待扩展 alarm 或 page eval 触发
-> store close
```

用途：保证「窗口被打开」。**数据写入仍由扩展完成**。

### 4.3 手动一键

Popup「立即抓取」不受时段限制；提供「仅预览 (dry-run)」。

---

## 5. 文件/目录结构（拟创建）

```
E:\project\海外TK店铺广告投流数据自动化监测\
├── README.md
├── docs\
│   ├── feishu-schema.md
│   ├── scrape-map.md                 # 权限后补全 URL/接口/表头
│   ├── ziniao-publish.md
│   └── runbook.md
├── extension\                        # ★ 主交付
│   ├── manifest.json
│   ├── background\service-worker.js
│   ├── content\
│   │   ├── scraper.js
│   │   ├── selectors.js
│   │   ├── mappers.js
│   │   └── net-hook.js
│   ├── lib\
│   │   ├── config.js
│   │   ├── feishu.js
│   │   ├── logger.js
│   │   ├── normalize.js
│   │   └── messages.js
│   ├── popup\ (popup.html/css/js)
│   ├── options\ (options.html/css/js)
│   └── icons\
├── scripts\
│   ├── pack-zip.ps1
│   └── smoke-feishu.mjs
├── optional-cli\
│   └── open-stores-and-wait.ps1
└── _extract\ ...                     # 已有需求提取物
```

打包：`extension\` 目录内容 ZIP，**根目录必须是 manifest.json**。

---

## 6. 分阶段实施步骤

### Phase 0 — 环境与权限（0.5–1 天，阻塞）

- [ ] 张威开放 3 个英区店铺在紫鸟中的访问权限  
- [ ] 开发者账号登录 open.ziniao.com，可创建「卖家自研插件」  
- [ ] 飞书自建应用 + 空多维表 + 应用协作者  
- [ ] 本地紫鸟：开发者模式 load unpacked  

### Phase 1 — MVP（3–5 天）

1. 脚手架：manifest + 空 SW + popup  
2. Options：飞书 4 件套存 storage，测试获取 token  
3. `feishu.js`：写 1 条假数据验证表结构  
4. 真机固化 Shop Ads URL + 表头/接口 -> `docs/scrape-map.md`  
5. content scraper：DOM 通道先通  
6. popup：一键抓取 -> 预览 -> 写入飞书  
7. 错误提示与本地 log  
8. 1 店端到端通过后扩展到另 2 店  

**MVP 验收**：手动在 1 店打开广告列表 -> 一键 -> 飞书出现正确 5 字段 + 店铺 + 日期。

### Phase 2 — 稳固与定时（2–3 天）

1. Network intercept + DOM fallback  
2. 分页 / 日期筛选自动化  
3. `chrome.alarms` 每日 7–8 点 + 「今日已跑」幂等  
4. 重试、partial、日志导出  
5. 店铺映射 UI、dry-run  
6. （可选）去重 search+update  

### Phase 3 — 打包发布与文档（1–2 天）

1. `pack-zip.ps1` 产出 ZIP  
2. open.ziniao.com 创建卖家自研插件并上传版本  
3. Boss 应用管理：分配给 3 个店铺账号  
4. 各店窗口验证  
5. 完成发布文档 + runbook  
6. （可选）Task Scheduler + ziniao-cli  

### Phase 4 — 增强（后续）

- 飞书 webhook 失败告警  
- 运行日志子表 / 仪表盘  
- CLI 完全无人值守  
- 选择器配置热更新（评估安全）  

---


## 7. 配置 UI（Popup / Options）

### 7.1 Options 页

| 区块 | 字段 | 说明 |
|------|------|------|
| 飞书 | app_id, app_secret | password 输入，仅 local storage |
| 飞书 | app_token, table_id | 从多维表 URL 复制 |
| 飞书 | 测试连接 | 拉 token + 可选 list fields |
| 店铺映射 | displayName, matchPatterns[], currency | 3 行预置可改 |
| 抓取 | defaultDateMode: yesterday / today / custom | 默认 yesterday |
| 抓取 | maxPages, requestTimeoutMs | |
| 调度 | enableSchedule, hourStart, hourEnd, tz | 默认 7–8 |
| 写入 | dryRunDefault, allowDuplicate | |
| 高级 | headerAliases JSON 导入 | 改版时更新映射 |
| 危险区 | 清空日志 / 导出配置（脱敏 secret） | |

### 7.2 Popup 页

- 当前识别店铺名 / 手动下拉  
- 业务日期显示  
- 按钮：`立即抓取` | `预览(dry-run)` | `打开 Options` | `导出日志`  
- 进度 + 最近一次：条数、成功/失败、飞书写入结果  
- 快捷链接：打开 Shop Ads（URL 可配置）  

**安全**：secret 不在 popup 明文展示；不写 Git；勿截图含 secret。

---

## 8. 错误处理、重试、本地日志

### 8.1 错误分类

| code | 场景 | 用户动作 |
|------|------|----------|
| `NO_TAB` | 未打开广告页 | 打开 Shop Ads |
| `NOT_LOGGED_IN` | 跳转登录页 | 紫鸟内重新进店 |
| `TABLE_NOT_FOUND` | 选择器失效 | 更新 selectors / scrape-map |
| `PARTIAL_COLUMNS` | 缺列 | 写入 partial + 备注 |
| `FEISHU_AUTH` | token 失败 | 检查 app_id/secret |
| `FEISHU_PERM` | 无表权限 | 应用加协作者 |
| `FEISHU_RATE` | 限流 | 退避重试 |
| `NETWORK` | 超时 | 重试 |
| `CONFIG_INVALID` | 缺配置 | 打开 Options |

### 8.2 重试

- 飞书写：指数退避 1s/2s/4s，最多 3 次；429/5xx 重试，4xx 不重试  
- 页面：表格等待最多 30s，轮询 1s  
- 采集：API 失败自动降级 DOM  

### 8.3 日志

- 分级 debug/info/warn/error；环形最多 500 条  
- storage key `logs`  
- popup 导出 JSON  
- 单次 run 摘要：runId、store、counts、durationMs、errorCodes  

---

## 9. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Seller Center / Shop Ads UI 改版 | DOM 全挂 | 表头映射 + API 通道；selectors 配置化；runbook 半日适配 |
| 广告接口字段变化 | intercept 失效 | 降级 DOM；维护 scrape-map |
| Seller 登录过期 | 定时失败 | 紫鸟常开会话；失败告警；CLI 辅助开店 |
| 电脑休眠 / 紫鸟未启动 | alarm 不跑 | 值守机；可选 CLI+任务计划 |
| 飞书 rate limit | 写入失败 | 小批量 + 退避；3 店串行 |
| ROI vs ROAS 语义混淆 | 报表失真 | 以页面列名为准；schema 备注定义 |
| 密钥泄露 | 飞书被写脏数据 | 仅 storage；最小权限；定期轮换 |
| 紫鸟扩展更新 ChromeID | 更新失败 | 更新包用旧密钥打 CRX，保持 ChromeID |
| 多店铺数据串味 | 写错店 | 强制店铺映射；每窗口独立 |
| 同日重复点击 | 重复行 | allowDuplicate；Phase2 主键去重 |

---

## 10. 验证 / 测试计划

### 10.1 单元级

- `normalizeNumber`：货币、百分号、空值  
- `mapHeaders`：中英表头别名  
- `feishu` mock：token 缓存过期逻辑  

### 10.2 集成（紫鸟真实环境）

| 用例 | 步骤 | 期望 |
|------|------|------|
| T1 假数据写飞书 | Options 测试连接 + 写 1 行 | 表中可见 |
| T2 单店 DOM dry-run | 打开列表 -> 预览 | 5 字段非空、条数>0 |
| T3 单店真实写入 | 取消 dry-run | 飞书新增，店铺/日期正确 |
| T4 缺列 | 故意改 aliases | partial + 备注 |
| T5 token 错误 | 错误 secret | FEISHU_AUTH |
| T6 未开广告页 | 空白页点抓取 | NO_TAB |
| T7 三店各跑一次 | 三窗口 | 总表可按店铺筛选 |
| T8 定时 | 改 alarm 为 2 分钟后 | 到点自动跑（窗口保持打开） |
| T9 重复抓取 | 同日两次 | 按 allowDuplicate 行为 |
| T10 打包安装 | ZIP 上传紫鸟 -> 分配店铺 | 店铺窗口插件可用且 T3 通过 |

### 10.3 验收标准（交付）

1. 3 个英区店均可手动一键抓取并写入总表  
2. 核心 5 字段 + 店铺 + 业务日期完整  
3. 定时可在 7–8 点触发（浏览器/店铺在线前提下）  
4. 无明文店铺密码；飞书密钥仅本地配置  
5. 提供打包 ZIP、上传/分配文档、runbook  
6. 失败可导出日志定位  

---

## 关键实现决策（已拍板建议）

1. **主路径 = MV3 卖家自研插件**，不做影刀 RPA 主方案  
2. **单飞书总表**，店铺字段区分；不做 3 分表  
3. **默认抓昨日**，符合日报习惯  
4. **每店铺窗口独立运行扩展**，不跨店切换登录  
5. **CLI 仅作开店辅助**，不替代扩展写飞书  

---

## 实施优先级排序（开发任务清单）

1. 扩展脚手架 + Options 配置存储  
2. 飞书 token + batch_create 打通  
3. 真机探测 Shop Ads DOM/API -> 固化 mappers  
4. Content scraper + popup 一键  
5. 错误处理与日志导出  
6. alarms 定时  
7. 打包脚本 + 紫鸟上传文档  
8. 三店回归 + 可选 CLI  

---

## Critical Files for Implementation

实现时最关键的新建文件：

- `E:\project\海外TK店铺广告投流数据自动化监测\extension\manifest.json`
- `E:\project\海外TK店铺广告投流数据自动化监测\extension\background\service-worker.js`
- `E:\project\海外TK店铺广告投流数据自动化监测\extension\content\scraper.js`
- `E:\project\海外TK店铺广告投流数据自动化监测\extension\lib\feishu.js`
- `E:\project\海外TK店铺广告投流数据自动化监测\extension\options\options.js`

权限实测后必须补全：

- `E:\project\海外TK店铺广告投流数据自动化监测\docs\scrape-map.md`
