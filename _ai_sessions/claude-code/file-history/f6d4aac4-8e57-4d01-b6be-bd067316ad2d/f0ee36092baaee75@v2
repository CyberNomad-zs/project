# 紫鸟「卖家自研插件」— TK 英区广告数据抓取与飞书汇总

## Context

公司有 3 个英区 TikTok 店铺，目前靠人工在紫鸟浏览器里登录后台、导出广告数据再整理日报，耗时易错。业务要求每日自动抓取 5 个核心字段（总收入、ROI、销量、广告花费、广告系列名称），汇总写入飞书多维表格。

实现路径按紫鸟开放平台 **卖家自研插件**（[文档](https://open.ziniao.com/docSupport?docId=101)）：与 Chrome 扩展一致，ZIP 打包上传生态中心，Boss 在「应用管理」分配给店铺账号使用。飞书表格从零设计；触发方式为 **手动一键 + 每日 7–8 点定时**。

---

## 推荐方案（唯一主路径）

**Chrome Manifest V3 扩展**，在紫鸟店铺窗口内运行：

| 层级 | 职责 |
|------|------|
| Content Script | 在 TK Seller / Ads 页面解析表格/接口数据，抽取 5 字段 |
| Service Worker | 飞书 tenant_access_token、批量写多维表、`chrome.alarms` 定时、重试与日志 |
| Popup / Options | 配置飞书凭证与表 ID、店铺映射、日期范围、手动抓取/预览、导出日志 |
| 本地缓存 | `chrome.storage.local` 存配置与最近一次抓取结果（不存店铺密码） |

可选补充（二期、不阻塞主交付）：本机用 `ziniao-cli` 串行 `store open` → 打开广告页 → 扩展/脚本抓取 → `store close`，用于无人值守时由外部调度器拉起店铺窗口。

---

## 飞书多维表格 Schema

**表名建议**：`TK广告日报汇总`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 日期 | 日期 | 数据所属日（默认昨天/当日可配置） |
| 店铺 | 文本 | 店铺展示名（Deal to deal / SHOP INOUT / Gardena 等） |
| 店铺ID | 文本 | 紫鸟 storeId 或业务内部编码（可选） |
| 广告系列名称 | 文本 | 对应样例中的品名/系列，如「花园拱门7/17」 |
| 广告花费 | 数字 | 货币金额，单位 USD |
| 销量 | 数字 | 订单件数 |
| ROI | 数字 | 投资回报率 |
| 总收入 | 数字 | 销售额/GMV，单位 USD |
| 抓取时间 | 日期时间 | 写入时刻 |
| 数据源URL | 文本 | 抓取时页面 URL（排障） |
| 状态 | 单选 | success / partial / error |

主键策略：业务上按「日期 + 店铺 + 广告系列名称」去重；写入前可查询当日同 key 再决定追加或更新（MVP 先追加，配置项预留「覆盖当日」）。

飞书 API：`tenant_access_token` → `bitable/v1/apps/:app_token/tables/:table_id/records/batch_create`（单次 ≤500 条，需求上限 5000 行/次时需分批）。

---

## 抓取策略

1. **优先页面表格 DOM**：等待广告系列列表加载后，按表头文案（Cost/Spend、ROI/ROAS、Orders/Units、GMV/Revenue、Campaign）模糊匹配列，再按行抽取。兼容英区 Seller Center / Shop Ads（GMV Max）与 Ads Manager 类页面。
2. **次选：拦截 XHR/Fetch 报表接口**（`chrome.webRequest` 或 content 层 hook `fetch`/`XHR`）解析 JSON，字段更稳；DOM 变更时作兜底。
3. **选择器策略**：避免硬编码哈希 class；用「表头文本 + 表格角色 + 稳定 data 属性」；抽取逻辑集中在 `src/scraper/`，便于改版时只改一处。
4. **日期**：Popup 可选「昨天 / 今天 / 自定义」；抓取前若页面有日期控件则尝试设置，失败则抓当前页展示数据并在记录中标注。
5. **店铺名**：从紫鸟环境/页面标题/用户配置映射表解析；配置里维护 `storeAlias → 飞书店铺名`。

目标 URL 形态（实现时按实机登录后确认并写入 match）：
- `*://seller*.tiktok.com/*`
- `*://ads.tiktok.com/*`
- `*://*.tiktok.com/*/shop-ads/*` 等

---

## 定时（7:00–8:00）

- 使用 `chrome.alarms`，默认 `07:30` 本地时区，可配置。
- **限制**：扩展定时仅在紫鸟进程存活且对应店铺环境已登录时可靠；Service Worker 触发后向已打开的匹配 tab 发消息执行抓取，无 tab 则写失败日志并（可选）桌面通知。
- Popup 提示：「定时抓取请保持紫鸟运行，并预先打开/登录目标店铺窗口」。
- 文档中注明：若需完全无人值守，二期用任务计划程序 + `ziniao-cli store open` 再触发扩展或 CLI 抽取。

---

## 项目目录结构

```
E:\project\海外TK店铺广告投流数据自动化监测\
├── extension/                 # 卖家自研插件源码（主交付）
│   ├── manifest.json          # MV3
│   ├── background/
│   │   └── service-worker.js  # 定时、飞书、消息路由
│   ├── content/
│   │   ├── content.js         # 注入入口
│   │   └── inject-fetch-hook.js  # 可选网络钩子
│   ├── scraper/
│   │   ├── parse-table.js     # DOM 表头匹配
│   │   ├── parse-api.js       # 接口 JSON 映射
│   │   └── normalize.js       # 统一为 5 字段 + 元数据
│   ├── feishu/
│   │   ├── auth.js            # tenant_access_token 缓存
│   │   └── bitable.js         # batch_create / 查询
│   ├── popup/
│   │   ├── popup.html
│   │   ├── popup.css
│   │   └── popup.js
│   ├── options/
│   │   ├── options.html
│   │   └── options.js
│   ├── lib/
│   │   ├── storage.js
│   │   ├── logger.js
│   │   └── constants.js
│   └── icons/
├── docs/
│   ├── 飞书表格建表说明.md
│   ├── 安装与上架指南.md      # 打包 ZIP、开放平台上架、应用管理分配
│   └── 运维与排障.md
├── scripts/
│   └── package-zip.ps1        # 根目录含 manifest 的 ZIP
└── README.md
```

---

## 配置项（Popup / Options）

| 配置 | 用途 |
|------|------|
| 飞书 app_id / app_secret | 自建应用凭证（仅存 storage，不明文入库） |
| app_token / table_id | 多维表格定位 |
| 定时开关 + 本地时刻 | 默认 07:30 |
| 默认日期模式 | yesterday / today / custom |
| 店铺名称映射 | 多行「页面识别名 → 飞书店铺名」 |
| 干跑 dry-run | 只抓取预览、不写飞书 |
| 写入模式 | append / replace-day（MVP 仅 append） |

---

## 分阶段实施

### Phase 1 — MVP（可演示手动抓取）
1. 搭 MV3 骨架与 Popup 配置页
2. Content Script：表格 DOM 解析 + 字段归一化
3. 飞书 auth + batch_create 写入（含 dry-run 预览）
4. 本地日志与抓取结果展示
5. 文档：飞书建表字段清单 + 如何创建飞书应用

### Phase 2 — 定时与稳健性
1. `chrome.alarms` + 通知
2. 失败重试（指数退避，最多 3 次）
3. 接口 JSON 兜底解析（若能在实机抓到报表请求）
4. 分批写入与简单去重提示

### Phase 3 — 打包上架
1. `package-zip.ps1` 产出 ZIP
2. 编写「开发者控制台创建卖家自研插件 → 上传 → 应用管理分配」步骤
3. 紫鸟内 `chrome://extensions` 加载已解压调试说明

### 依赖外部（非代码）
- 飞书企业自建应用 + 多维表格权限
- 紫鸟企业开发者/Boss 创建并分配插件
- 张威开放测试店铺权限后，在实机校准选择器与 URL

---

## 错误处理

- 页面未登录 / 无表格：明确错误码与中文提示
- 网络超时：重试 3 次
- 飞书 token 过期：自动刷新后重写
- 飞书限流：分批 + 退避
- 每次运行写 `logs[]`（时间、店铺、条数、错误），支持导出 JSON

---

## 风险

| 风险 | 应对 |
|------|------|
| TK 后台改版 | 表头语义匹配 + 模块化 scraper；预留适配时间 |
| 扩展定时依赖进程 | 文档说明 + 二期 CLI 拉起 |
| 飞书 API 限流 | 分批 ≤500、退避 |
| 凭证泄露 | 仅 `chrome.storage`，不进仓库；README 用占位符 |
| 紫鸟插件策略/白名单 | 按官方「应用管理 / 员工白名单」文档分配 |

---

## 验证计划

1. Chrome/紫鸟加载已解压扩展，Options 填入测试飞书表
2. 打开一个已登录英区广告页 → Popup「立即抓取」→ 预览 5 字段与样例表一致
3. 关闭 dry-run → 飞书表出现带日期/店铺的新行
4. 设置 1 分钟后的 alarm 验证定时链路
5. 断网/错 table_id 验证错误提示与日志导出
6. `package-zip.ps1` 打包后按文档上传卖家自研插件（需 Boss 账号时由用户操作）

---

## 关键文件（实现时）

- `extension/manifest.json`
- `extension/background/service-worker.js`
- `extension/content/content.js`
- `extension/scraper/*.js`
- `extension/feishu/*.js`
- `extension/popup/*`
- `docs/安装与上架指南.md`
- `docs/飞书表格建表说明.md`
- `README.md`

---

## 不在首期范围

- 影刀/八爪鱼 RPA 流程
- 飞书仪表盘可视化（需求写明后续）
- 服务商插件公开上架
- 自动登录店铺（依赖紫鸟已登录环境，不碰密码）
