# TK · P1.2 广告系列 CTR / 展示字段评估

> 日期：2026-08-04  
> 对应计划：[TK-整体开发计划](./TK-整体开发计划.md) · P1.2  
> 结论：**本阶段书面冻结「无字段」**——系列日表不补 impressions/ctr/cvr 列，规则也不依赖 CTR。

---

## 1. 评估范围

| 项 | 内容 |
|----|------|
| 目标表 | `tk.fact_ads_campaign_daily`（系列日） |
| 候选字段 | `impressions`（展示）、`clicks`（点击）、`ctr`、`cvr` |
| 采集入口 | 紫鸟内 GMV Max 广告面板 `ads-creation/dashboard` |
| 对照文档 | `collectors/tiktok-ads/docs/调研-紫鸟广告页可抓字段.md`（2026-07-29） |

---

## 2. 现状

### 2.1 PG 列

`003_tiktok_ads_p1_fields.sql` 已加：

- `plan_status` / `delivery_status`
- `daily_budget` / `target_roi`
- `net_cost` / `avg_order_cost`

**无** `impressions` / `clicks` / `ctr` / `cvr` 列。

### 2.2 采集脚本列映射

`scrape-ads-page.js` / `extension/scraper/parse-table.js` 的 `HEADER_ALIASES` 仅覆盖：

开/关 · 系列名 · 状态 · 当前预算 · 目标 ROI · 净成本 · 花费 · 订单 · 平均下单成本 · 销售额 · ROI

现场调研表头**未出现**独立的「展示 / 点击 / CTR / CVR」列（GMV Max 商品广告默认列集）。

### 2.3 Ingest

`_process_tiktok_ads` 写入与上表一致；无 CTR 通路。

---

## 3. 结论（P1 门禁）

| 判定 | 说明 |
|------|------|
| **能否入 PG** | **否（本阶段）** — 采集页默认列无稳定 impressions/CTR 源 |
| **是否建空列** | **否** — 避免看板假 0、规则误触发 |
| **规则侧** | P1.1 已用 `daily_budget` / `avg_order_cost` 覆盖预算将尽与高 CPA；**不依赖 CTR** |
| **商品卡多渠道 CTR** | 属 **P2 · ② 内容分析/商品卡**，不在广告系列日补 |

---

## 4. 若后续要开（非 P1）

1. 广告后台自定义列 / 导出 API 能稳定给出展示·点击  
2. 扩展 `HEADER_ALIASES` + 迁移加列 + ingest 映射  
3. 率类写入前算好或看板用 sum(click)/sum(impr) 重算  
4. 再开 `ads_ctr_low` 类规则（需新字典码）

---

## 5. 验收勾选

- [x] 书面结论：系列 CTR/展示 **无字段、不入 PG**
- [x] 与采集调研、脚本别名、003 迁移一致
- [ ] （可选后续）自定义列 POC 另开工单
