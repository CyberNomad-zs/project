# TK · P2 启动计划 — 先过门禁（内容分析 POC）

## Context

P1 工程已收口（广告 burn/cpa、商品排行、任务台分析域）。按整体计划，**P2 = ② 视频内容分析 + 商品卡 CTR/CVR（+ 可选广告细粒度全量）**。

现状摸底（2026-08-04）：

| 层 | 状态 |
|----|------|
| 内容/视频/商品卡采集 | **零实现**（无 scrape/run/config URL/debug JSON） |
| PG `fact_tiktok_content_daily` / `product_traffic_daily` | **无表** |
| ingest `tiktok_content` / `tiktok_product_traffic` | **未注册** |
| 内容异常规则 / 任务台内容页 / 飞书内容表 | **无** |
| 广告创意细粒度 | P1.7 已书面：**全量 P2**，本轮 **不做** |

计划硬约束：**采集可稳 → schema → ingest → 规则 → 看板**；**门禁不过不建空表**。

用户确认本轮切法：

1. **只做 P2.0 采集 POC**（不过门禁不落 schema/API 壳）
2. POC 范围：**视频和照片概览 + 商品卡/商品数据**（同一门禁批）

---

## 目标（本轮交付）

用 1～2 家真店（优先 Deal / Gardena UK）在紫鸟内打开：

1. **数据分析 → 内容分析 → 视频和照片 → 视频和照片概览**
2. **内容分析顶栏 · 商品卡 / 商品数据分析**（以页面实际 Tab 名为准）

产出：

- `logs/content-*-debug-*.json` / `logs/product-traffic-*-debug-*.json`（或等价命名）
- 可选：仅写 `public.ingest_raw` 的 raw 信封（**不** UPSERT 正式 fact）
- 结论文档：`docs/TK-P2-内容分析POC结论.md`（镜像 `TK-P1-广告细粒度POC结论.md`）
- 字段字典草案（可采字段表 + 不可采说明）
- **门禁 verdict**：通过 / 部分通过 / 不通过 → 决定是否开 P2.1 schema

**明确不做（本轮）：**

- 新建 `fact_tiktok_content_daily` / `product_traffic_daily` / creative 表
- 注册生产 ingest 处理器、规则、飞书 T*、任务台 `tk-content` 页
- 广告创意/组页 POC（P1.7 已冻结，另开）
- 达人/联盟（P3）

---

## 商家中心入口（POC 导航）

| # | 页面 | 路径 | 目标指标（截图级，待实采校验） |
|---|------|------|--------------------------------|
| A | 视频和照片概览 | 数据分析 → 内容分析 → 视频和照片 → 概览 | 视频归因 GMV、SKU 订单、曝光/播放、客户数、视频排行（转化/互动） |
| B | 商品卡/商品数据 | 内容分析顶栏「商品卡」或「商品数据分析」 | 曝光、点击、CTR、订单、GMV、CVR；渠道若有则记 |

**已知风险（须在 POC 记录）：**

- Compass / data-overview 类 SPA 曾出现 KPI 占位不刷新（shop-modules 已改走 homepage）
- 后台「近 7 天」卡片 vs 业务日 `biz_date` 对齐（ads 用 `set-date-range.js`；内容页须验证能否选昨日/单日）
- EU Pop 店沿用 `opsExclude*`，POC 默认 UK Deal/Gardena
- 无稳定 URL 时：先人工点进页面，从地址栏抄 path 写入 config 草案

---

## 实施步骤

### Step 0 — 文档与命名冻结（30min）

- 新建 `docs/TK-P2-内容分析POC结论.md` 骨架（结论先写「进行中」）
- 飞书表号：**本轮不建表**；在结论里注明未来内容表建议用 **T6 内容日 / D4 视频内容**，避免与现网「T4=健康 / D3=商品或 AI」冲突（见 `docs/TK-飞书驾驶舱建表方案.md`）
- `object_type` 预留值建议：`content`（仅文档；本轮不改 CHECK）

### Step 1 — 手工探路（紫鸟，1 店）

在采集机/同事机紫鸟：

1. 打开 Deal（或 Gardena）卖家中心  
2. 走到页面 A、B，截图 + 复制完整 URL  
3. 观察：数字卡 / 表格 / 是否有导出 / 网络 XHR（DevTools 若可）  
4. 试改日期：能否落到**单日**；不能则记录默认窗口（近1/7/28天）  
5. 记下：视频行是否有稳定 `content_id` / 视频链接；商品行是否有 `product_id`

输出写入 POC 文档 §「页面实勘」。

### Step 2 — 探针脚本（复用 shop-modules / ads 模式）

路径均在 `collectors/tiktok-ads/`：

| 复用 | 路径 |
|------|------|
| 编排模板 | `scripts/run-shop-modules.ps1`（store open → page visit → page exec → debug JSON） |
| 卡片型解析参考 | `scripts/scrape-shop-daily-page.js`（`innerText` + 正则） |
| 表格式解析参考 | `scripts/scrape-ads-page.js`（表头别名 + 行解析） |
| 日期 | `scripts/set-date-range.js`（内容页若控件不同则新建 `set-content-date-range.js` 或记录不可用） |
| 上报客户端 | `scripts/qingquan-client.ps1`（POC 阶段默认**只落本地 debug**；可选 raw ingest） |
| 配置 | `scripts/stores.config*.json` + `config/`；新增可选键草案 `contentUrl` / `productTrafficUrl`（example only） |

**新建（POC）：**

1. `scripts/scrape-content-overview-page.js`  
   - 返回 `{ ok, module: "content_overview", source_url, window, kpis{}, videos:[{id,title,metrics…}], raw, error }`  
2. `scripts/scrape-product-traffic-page.js`  
   - 返回 `{ ok, module: "product_traffic", … products:[{product_id, channel?, metrics…}], raw, error }`  
3. `scripts/run-content-poc.ps1`  
   - 参数：`-StoreFilter`、`-Modules content,product_traffic`、`-SkipIngest`（默认 true）  
   - 写 `logs/{module}-debug-{storeId}-{stamp}.json`  
   - 失败重试 2～3 次（对齐 shop-modules）  
4. （可选）`scripts/_probe-content-page.js`：更粗的 DOM/文案 dump，辅助调选择器

**不**改 `backend/app/api/ingest.py` allowlist（除非做 raw-only 实验且明确不 dispatch fact）。

### Step 3 — 跑 POC（≥1 店，争取 2 店 × 1～2 日）

```text
run-content-poc.ps1 → logs/*.json
人工打开 JSON 核对：归因 GMV/订单/曝光是否非空、id 是否稳定
```

验收样例门槛（门禁用）：

| 项 | 最低线 |
|----|--------|
| 视频概览 KPI 或排行 | ≥1 店抓到非空核心指标（归因 GMV 或曝光+订单 任一组合可解释） |
| 视频行 | 若有表：≥1 行含可去重 id 或 title+url |
| 商品卡 | ≥1 店非空曝光/点击或 CTR；最好带 product_id |
| 可重复 | 同一 URL/脚本连跑 2 次结构稳定（字段不漂移成空） |
| 原始落盘 | debug JSON 入库路径明确；可选 `ingest_raw` 仅 source 标记 `tiktok_content_poc` |

### Step 4 — 字段字典 + 门禁结论

在 `docs/TK-P2-内容分析POC结论.md` 写清：

1. **可采字段表**（中英/后台文案 → 建议 PG 列 → 类型 → 粒度）  
2. **不可采 / 不稳定**（占位、需登录二次、无单日）  
3. **biz_date 策略**：单日 / 窗口拆分 / 仅快照  
4. **关联键**：content↔product↔ads — 能 / 不能 / 仅 title 模糊（不能则 P2.6 分开展示）  
5. **Verdict**  
   - **通过**：开 P2.1 迁移（content_daily + product_traffic_daily）+ ingest + 最小规则  
   - **部分通过**：只建有数的一侧表；另一侧继续 POC  
   - **不通过**：冻结；任务台/飞书不建空壳；保持「无数据」  
6. **下期 backlog**：P2.1～P2.6 清单（引用整体计划，不提前写死迁移 SQL 除非通过）

### Step 5 —（仅门禁通过后的预告，本轮不实施）

克隆现网模式（备忘，**批准本计划不等于现在做**）：

| 层 | 克隆源 | 新增 |
|----|--------|------|
| Migration | `007`/`010` 风格直建 `tk.*` | `fact_tiktok_content_daily`, `fact_tiktok_product_traffic_daily`；`dim` 内容异常码；可选 `object_type` 加 `content` |
| Ingest | `_process_tiktok_shop_daily` | `tiktok_content` / `tiktok_product_traffic` |
| Rules | `tk_shop_rules` 环比 + `tk_ads_rules` 有曝无单 | `tk_content_rules.py` + job |
| API | `tk_ops` shop-daily / ranking | `GET /tk/content/…`, traffic 对比 |
| UI | `App.vue` tk-ads / ranking | `tk-content` + 分析域「视频内容」 |
| Feishu | `tk_feishu_sync` TABLE_SPECS | **T6/D4**（新编号），勿复用 T4/D3 |

广告创意全量仍受 P1.7 二次门禁，**不绑死在内容 POC 通过上**。

---

## 关键文件（本轮会动）

**新建**

- `collectors/tiktok-ads/scripts/scrape-content-overview-page.js`
- `collectors/tiktok-ads/scripts/scrape-product-traffic-page.js`
- `collectors/tiktok-ads/scripts/run-content-poc.ps1`
- `docs/TK-P2-内容分析POC结论.md`
- （可选）`docs/TK-P2验收清单.md` 仅 POC 章节

**可能小改**

- `collectors/tiktok-ads/scripts/stores.config.example.json` — 注释/示例 `contentUrl` / `productTrafficUrl`
- `docs/TK-整体开发计划.md` — P2.0 状态勾选、下一刀指向 POC 结论
- `collectors/tiktok-ads/docs/每日定时任务.md` 或路线图 — 一句「内容 POC 未入日更」

**只读参照**

- `scripts/run-shop-modules.ps1`, `scrape-shop-daily-page.js`, `scrape-ads-page.js`, `qingquan-client.ps1`
- `docs/TK-P1-广告细粒度POC结论.md`, `docs/TK-整体开发计划.md` §P2
- `backend/app/api/ingest.py`（确认不误加 fact 分发）

---

## 验证

1. `run-content-poc.ps1` 退出码 0 或可解释的部分成功；`logs/` 有 JSON  
2. JSON 人工可读：关键指标非全 null  
3. POC 文档 verdict 三选一已填，字段表完整  
4. **回归**：未改 api 镜像行为；`pytest` 不必为 POC 新增（无后端变更则跳过）  
5. 生产：**不** rebuild api；不 apply 新迁移  

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 内容 SPA 抓不到数 | 先 probe dump；尝试拦截 XHR；失败则 verdict=不通过 |
| 只有「近7天」无单日 | 文档冻结为窗口快照或 7 日均摊禁令；规则延后 |
| 无 content_id | 用平台 URL / 标题哈希仅 POC；正式表前必须稳定键 |
| 商品卡与视频不同 DOM | 两个 scrape 文件，独立 ok 标志 |
| 误建空表 | 本计划禁止 migration；结论未通过不开 P2.1 |
| 命名 P2 与采集路线图 P2a/b/c 混淆 | 文档写「经营计划 P2 / 内容」 |

---

## 成功画像（本轮结束时）

- 仓库里有**真页面** debug 样例 + 可重复脚本  
- 书面门禁结论可执行：通过则下一会话直接 P2.1；不通过则停在采集，不装门面  
- 任务台/飞书/PG 正式内容层仍为空，但**原因可解释**（有 POC 文档）
