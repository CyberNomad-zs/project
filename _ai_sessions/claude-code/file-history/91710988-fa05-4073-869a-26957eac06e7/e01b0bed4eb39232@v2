# P3.0 达人表现 · 采集 POC 方案

## Context

经营计划 **P3 = ③ 达人表现（联盟中心→数据分析→表现）**，目标是「达人是否出单」看板 + 异常域。  
现状：**无 URL、无 scrape、无 PG 表、无 ingest、无任务台达人页**。计划强制 **门禁先过再建模**。

你已拍板：
1. **只做 P3.0 POC**（不过门禁不建表、不上报 fact）
2. **三店含 Pop**：Deal / INOUT / Pop（Gardena）

本轮交付 = 紫鸟可重复探路 + 字段/ID 结论 + 书面门禁 verdict。  
**P3.1+（schema/ingest/规则/飞书/TAB）不在本轮。**

---

## 目标与非目标

### 做
- 发现并固化 **联盟中心·表现**（及必要辅助页）真实 URL / 子域
- 验证 **店级 KPI** 与 **达人明细行** 能否稳抓
- 判定 **达人稳定主键**（creator_id / handle / 内部 id）
- 盘点 **三类投入**（佣金 / 达人投流 / 寄样·合作费）各自是否有数、来自哪页；缺项标「暂不采」
- 输出 `docs/TK-P3-达人表现POC结论.md`（镜像 P2 内容 POC 写法）
- 配置示例写入 `affiliateUrl`（及按需辅助 URL），**默认 SkipIngest**

### 不做
- 不建 `fact_tiktok_affiliate_*`、不改 anomaly CHECK、不写 ingest/规则/飞书 sync
- 不挂日更计划任务
- 不新建任务台达人 TAB / 飞书达人表
- 不用广告花费或店日 GMV **假填**达人归因

---

## 命名冻结（POC 文档即写死，避免与现网冲突）

| 用途 | 编号 | 说明 |
|------|------|------|
| 达人事实 → 飞书（过门禁后） | **T7 达人日** | **不要**用计划旧文的 T5（建表方案里 T5=财务） |
| 达人看板（过门禁后） | **D5 联盟达人** | **不要**用 D4（已是视频内容） |
| 异常 `object_type`（过门禁后） | 预留 **`creator`** 或 **`affiliate`** | 本轮不改 DB |
| 异常域中文 | **达人表现** | 与店铺分析 / 视频内容 / 广告 / 库存并列 |
| PG 表名（过门禁后草案） | `fact_tiktok_affiliate_daily` + `fact_tiktok_affiliate_creator_daily` | 与整体计划一致；`fact_creator_sample` 寄样另议 |

---

## 门禁标准（POC 结论必须逐项给 🟢/🟡/🔴）

| # | 门禁 | 通过条件 |
|---|------|----------|
| G1 | 页面可达 | 三店均可进联盟中心子域；登录/跳转可脚本化（允许人工点一次「前往联盟中心」后抓最终 URL） |
| G2 | 店级 KPI | 至少稳定抓到：达人归因 GMV、成交件数、动销达人数、预计佣金（退款/视频数/直播数有则记） |
| G3 | 达人行 + ID | 明细表 ≥1 行且 **跨刷新同一达人 id 不变**；无稳定 id → 🔴 不建 creator 日表 |
| G4 | 是否出单口径 | 可用「归因 GMV>0 或 成交件>0」定义；文档写清窗口（自然日 vs 近7天等，对齐页面） |
| G5 | 投入分项 | 佣金/投流/寄样 **各自**写：可采页 / 暂不采；**禁止**把缺项当 0 |
| G6 | 禁混加 | 书面：归因 GMV ≠ 广告花费可加总；与 ① 渠道「达人带货」对账策略（以谁为准或仅对照） |

**Verdict 规则：**
- G1–G4 全 🟢 → 可开 P3.1 schema（creator 表视 G3）
- 任一项 🔴 关键路径 → 停在 POC，不建空表
- 仅 G5 部分 🟡 → 可建「有数字段」窄表，投入缺项列不建或 nullable + UI「无数据」

---

## 实施步骤

### 1) 探路脚本（优先）

镜像内容侧：

| 新建 | 作用 |
|------|------|
| `collectors/tiktok-ads/scripts/_discover-affiliate-nav.js` | 商家中心点「联盟」→ 抓跳转 URL / 新域 host / 顶栏·左树文案 |
| `collectors/tiktok-ads/scripts/_probe-affiliate-page.js` | 落地页粗 dump：KPI 文案、表头、行样例、window/XHR 线索 |
| `collectors/tiktok-ads/scripts/scrape-affiliate-performance-page.js` | 结构化：`ok/error`、`kpis{}`、`rows[]`、`window`、`pageUrl`、候选 `creator_id` |
| `collectors/tiktok-ads/scripts/run-affiliate-poc.ps1` | 编排；**默认 `-SkipIngest`**；三店循环；debug JSON → `logs/affiliate-*-debug-*.json` |

**复用：**
- `run-content-poc.ps1` 的 Ziniao open/visit/maximize、重试、debug 落盘、ops 店列表过滤模式
- `ziniao-window.ps1`
- **本轮 POC 不要走 `opsExcludeStoreIds`**（用户要求含 Pop）；用显式 store 列表或临时 config，避免 Pop 被经营 exclude 掉

**店清单（本轮）：**

| 紫鸟名 | storeId | 业务名 | 平台 |
|--------|---------|--------|------|
| Tiktok_Shop2 | `27501502216807` | Deal | 英国本土 |
| Tiktok - KK Seagull | `27328767468273` | INOUT | 英国本土 |
| TikTok - Pop | `27758103898326` | Gardena | 欧盟 |

欧盟与 UK 可能是 **不同联盟 host**（类比 ads/order 的 eu 域）；探路时 **分平台记最终 URL**，写入 `affiliateUrl.byPlatform`。

**导航假设（待实证）：**
```text
seller-uk（或 eu）商家中心
  → 左侧「联盟」→「前往联盟中心首页」（可能新开域）
  → 数据分析 → 表现
辅助（有余力再探，不阻塞 G1–G4）：样品 / 达人 / 所有视频
```

### 2) 配置

- `stores.config.example.json` 增加：
  - `affiliateUrl`: `{ default, byPlatform }`（POC 实勘后填真 URL；初值可空 + 注释）
  - 可选 `affiliateCreatorsUrl` / `affiliateSamplesUrl`（仅当辅助页有独立 URL）
- **不改** 日更 `run-shop-modules-daily` 默认 modules
- 本地 `stores.config.json` 可在 POC 成功后写入 URL（注意含密钥，不提交）

### 3) 字段字典（写进 POC 结论，不落迁移）

**店×窗（日后 `affiliate_daily`）：**  
`shop_external_id, biz_date|window_anchor, window_label, gmv_affiliate, order_units, refund_amount, video_cnt, live_cnt, creators_published, creators_sold, est_commission, currency, source, raw_extra`

**达人×窗（日后 `affiliate_creator_daily`）：**  
`shop_external_id, creator_id, creator_name, biz_date|window, gmv, order_units, est_commission, video_cnt?, collab_type?, product_cat?, raw_extra`  
`UNIQUE` 草案：`(shop_external_id, creator_id, biz_date, window_label)`

**是否出单：** `gmv > 0 OR order_units > 0`（POC 用页面字段名对齐后定稿）

**投入：**
| 分项 | 期望来源 | POC 记法 |
|------|----------|----------|
| 佣金 | 表现页预计佣金 | 有则映射 `est_commission` |
| 达人投流 | 联盟或广告侧（未知） | 找不到 → 暂不采 |
| 寄样/合作费 | 样品页或飞书人工表 | 找不到 → 暂不采 |

### 4) 文档

新建 **`docs/TK-P3-达人表现POC结论.md`**，结构对齐 `docs/TK-P2-内容分析POC结论.md`：

1. 命名冻结（T7/D5）  
2. POC 问题  
3. 仓库交付文件表  
4. 实页 URL（分店/分平台）  
5. 字段映射（中文表头 → 英文 key）  
6. 门禁 G1–G6 判定表 + **总 verdict**  
7. 明确 **下一步 / 禁止项**（不过门禁禁止 schema）

并轻量回写：
- `docs/TK-整体开发计划.md`：P3.0 状态、飞书编号更正为 T7/D5、下一刀指向 POC  
- `collectors/tiktok-ads/docs/TK-整站运营数据采集路线图.md`：注明经营 P3 ≈ 路线图旧称 P4 联盟（避免编号混用）

### 5) 建议执行顺序（实现时）

```text
① _discover-affiliate-nav.js + 单店 Deal 手工/半自动打开联盟中心，落最终 URL
② _probe 落 KPI/表头 dump
③ scrape-affiliate-performance-page.js 结构化
④ run-affiliate-poc.ps1 跑 Deal → INOUT → Pop
⑤ 对照三店 JSON 写 POC 结论 + example config URL
⑥ 总 verdict；若 🟢 再另开轮做 P3.1（不在本 plan）
```

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 联盟中心另域 / SSO / 验证码 | discover 记 host；验证码则 POC 标 🔴 并截图说明 |
| Pop 欧盟路径不同或无联盟权限 | 分平台 URL；单店失败不拖死 UK 两店结论 |
| 仅有店级 KPI 无达人行 | G3 🔴 → 只允许日后店级表，不做 creator 日表 |
| 页面是窗口快照（类 content 近7天） | 与 P2 一样：**不拆成 7 行**；`window_label` + 锚点日 |
| 达人 id 仅昵称 | 试 URL/ data-* / 接口；仅昵称则跨店不可靠，文档降级 |
| 与 ① 渠道达人 GMV 双口径 | POC 只对照记差异，不选 SoT 填数 |

---

## 关键现成资产（只读复用）

- 编排模板：`collectors/tiktok-ads/scripts/run-content-poc.ps1`
- 导航探路：`_discover-content-nav.js` / `_discover-content-nav-deep.js`
- 结论模板：`docs/TK-P2-内容分析POC结论.md`、`docs/TK-P1-广告细粒度POC结论.md`
- 需求 SoT：`docs/TK-整体开发计划.md` §P3；XMind：`_xmind_tk_dash_new/outline.md`
- 店配置：`collectors/tiktok-ads/config/stores.config.json`（POC 跑机用；含密钥勿提交变更到 Git）

**过门禁后的全链路复制清单（本轮不实施，仅备忘）：**  
schema(012/013 风) → ingest refreshable → `tk_affiliate_rules` → job CLI → `/tk/affiliate` TAB → 飞书 T7（仿 T6 content）→ post-collect / 独立日更模块。

---

## 验证（本轮 Definition of Done）

1. `run-affiliate-poc.ps1` 对 **三店** 各至少 1 次跑通或明确失败原因进 log  
2. `logs/` 下有 discover/probe/scrape debug JSON（可进 Git 的脱敏样例可选）  
3. `docs/TK-P3-达人表现POC结论.md` 含：
   - 分平台 URL  
   - 字段表  
   - G1–G6 判定 + 总 verdict  
   - 「下一步 / 禁止 schema」  
4. `stores.config.example.json` 有 `affiliateUrl` 键（有真 URL 则填）  
5. **代码库无** affiliate fact 迁移、无 ingest source、无日更挂载  

手动抽查：用紫鸟打开结论中的 URL，肉眼对一下 scrape 的 KPI/首行达人是否一致。

---

## 关键文件（将新建/修改）

**新建**
- `collectors/tiktok-ads/scripts/_discover-affiliate-nav.js`
- `collectors/tiktok-ads/scripts/_probe-affiliate-page.js`
- `collectors/tiktok-ads/scripts/scrape-affiliate-performance-page.js`
- `collectors/tiktok-ads/scripts/run-affiliate-poc.ps1`
- `docs/TK-P3-达人表现POC结论.md`

**修改**
- `collectors/tiktok-ads/config/stores.config.example.json` — `affiliateUrl`
- `docs/TK-整体开发计划.md` — P3.0 进行中、T7/D5 命名
- `collectors/tiktok-ads/docs/TK-整站运营数据采集路线图.md` — 编号对照一句

**明确不改（本轮）**
- `backend/app/api/ingest.py`、migrations、`tk_*_rules`、`tk_feishu_sync`、web 任务台
