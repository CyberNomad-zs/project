# Amazon 样板流程草案 · 环比异常 → 人维任务 → 负责人

> 版本：v0.2  
> 日期：2026-07-28  
> 状态：**业务阈值与窗口已确认**；实现尚未开工（不含补货审批、巡店插件全量）  
> 对齐：[中台产品蓝图](./中台产品蓝图.md) · [架构方案](./架构方案.md) · [字段映射字典](./字段映射字典.md) · `001_init.sql`

### 已确认决策（2026-07-28）

| # | 议题 | 结论 |
|---|------|------|
| 1 | 周/月窗口 | **自然周、自然月**（非滚动 7/30 日） |
| 2 | 种子阈值 | **采用** §4.3 / 002 中的占位阈值，可后续改表调整 |
| 3 | 日+周+月同时命中 | **多单并行**（不同类型各一张未闭环单） |
| 4 | 负责人 | **上 ASIN 映射**（`listing_owner` 优先，再回落店铺负责人） |
| 5 | 首期指标 | **仅 units + sales_amount**（不做 sessions/转化环比） |

---

## 1. 目标与边界

### 1.1 目标闭环

```
赛狐（或 Ingest）写入链接日指标
  → 调度 Job 计算 日/周/月 环比
  → 命中规则生成 anomaly_event
  → task_engine 去重建单 / 更新进度
  → 解析第一负责人 owner_user_id
  → 人维列表 / 推送（飞书 outbox + 后续智能体）
  → 负责人填运营动作（task_progress）→ 闭环
  → 闭环后再命中 → 新建任务（不复活旧单）
```

### 1.2 范围

| In Scope | Out of Scope（本草案） |
|----------|------------------------|
| 链接粒度日指标事实表 | 补货审批流 |
| 环比规则配置表（可配置阈值） | 巡店 12 项全量 |
| 异常 → 任务 → 人维查询 API | 财务五表 |
| 负责人解析顺序 | 真实赛狐 SDK 实现细节 |
| 与现有 `task` / `anomaly_event` 复用 | 前端改版（可后接） |

### 1.3 设计原则

1. **复用** Phase0 `task` 部分唯一索引与 `task_engine.upsert_task_from_anomaly`  
2. **事实与规则分离**：事实可重算；规则变更不改历史事实，只影响新一轮判定  
3. **一链接一异常类型一未闭环单**；推送层按人聚合（人维视图）  
4. **幂等**：指标 Ingest + 规则跑批均可重跑  

---

## 2. 业务流程（时序）

```
┌─────────────┐    POST /ingest/sellfox_link_daily     ┌──────────────┐
│ sellfox-    │ ─────────────────────────────────────► │ ingest_raw   │
│ worker      │                                         │ + fact_amz_  │
└─────────────┘                                         │ link_daily   │
                                                        └──────┬───────┘
                                                               │
                    Cron 07:10（昨日）                           ▼
┌─────────────┐    POST /jobs/amz/mom-scan（或内部 job） ┌──────────────┐
│ scheduler   │ ─────────────────────────────────────► │ rule engine  │
└─────────────┘                                         │ + anomaly    │
                                                        │ + task upsert│
                                                        └──────┬───────┘
                                                               │ outbox
                                                               ▼
                                                        飞书 / 智能体
                                                               │
┌─────────────┐    GET 人维任务 / POST 进度·闭环         ┌──────────────┐
│ Web AMZ ·   │ ◄─────────────────────────────────────► │ task API     │
│ 环比异常任务 │                                         └──────────────┘
└─────────────┘
```

**建议调度（与会议一致，可配置）：**

| Job | 建议时间 | 输入 |
|-----|----------|------|
| 拉昨日链接日指标 | 07:00 | 赛狐 |
| 环比扫描（日/周/月） | 07:10 | `fact_amz_link_daily` + `amz_mom_rule` |
| 必提醒未闭环 | 每日固定 | `task` where amazon + open/in_progress |

---

## 3. 概念模型

| 概念 | 说明 |
|------|------|
| **链接 biz_id** | 默认 **ASIN**；无 ASIN 时用 `seller_sku` 或赛狐 `commodity_id`（`biz_id_type` 标明） |
| **粒度 period** | `day` / `week` / `month` — 进入 `anomaly_type` 后缀或独立字段 |
| **环比** | 本期指标 vs 上期同长度窗口；首期指标：**销量 units、销售额 sales_amount**（可扩展 sessions/转化） |
| **人维** | 展示与推送按 `owner_user_id` 聚合；**落库仍一链接一单**（蓝图开放问题默认答） |
| **负责人** | 见 §6 解析顺序 |

### 3.1 anomaly_type 编码（建议）

| code | 含义 | period |
|------|------|--------|
| `link_dod_units_drop` | 链接销量日环比下降超阈 | day |
| `link_wow_units_drop` | 周环比销量下降 | week |
| `link_mom_units_drop` | 月环比销量下降 | month |
| `link_dod_sales_drop` | 销售额日环比下降 | day |
| `link_wow_sales_drop` | 销售额周环比下降 | week |
| `link_mom_sales_drop` | 销售额月环比下降 | month |
| `link_zero_sales` | 连续 N 日零销（可选，与字典 sales 异常衔接） | day |

**去重键（沿用引擎）：**

```text
dedupe_key = amazon:{biz_id}:{anomaly_type}
例：amazon:B0XXXX:link_wow_units_drop
```

同一 ASIN 的日环比与周环比可并存两张未闭环单（类型不同）。  
**已确认：多单并行**——不在规则层做 severity 互斥。

---

## 4. 表结构草案

> 建议 migration：`backend/migrations/002_amz_mom_tasks.sql`（本文 §9 附完整 SQL 草稿）

### 4.1 复用（已有，不改语义）

| 表 | 用法 |
|----|------|
| `shop` | `platform=amazon`，`primary_owner_user_id` 作负责人兜底 |
| `ingest_raw` | source=`sellfox_link_daily` 或 `amz_link_daily` |
| `anomaly_event` | 每次命中写入；`payload` 存环比明细快照 |
| `task` / `task_progress` | 状态机 + 运营动作 |
| `outbox_event` | `task.assigned` / `feishu.sync` / `notify.owner` |
| `org_user` | 负责人 |

### 4.2 新增 `fact_amz_link_daily`（链接 × 日 事实）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| shop_id | UUID FK shop | 可空若仅有外部店号 |
| shop_external_id | TEXT NOT NULL | 赛狐 shopId |
| biz_date | DATE NOT NULL | 业务日 |
| asin | TEXT | |
| seller_sku | TEXT | |
| parent_asin | TEXT | 可选 |
| title | TEXT | 快照 |
| units | NUMERIC(18,4) DEFAULT 0 | 销量 |
| sales_amount | NUMERIC(18,4) DEFAULT 0 | 销售额 |
| currency | TEXT | |
| sessions | NUMERIC(18,4) | 可选 |
| conversion_rate | NUMERIC(18,6) | 可选 |
| fba_fulfillable | NUMERIC(18,4) | 可选，与销售异常共用 |
| raw_extra | JSONB DEFAULT {} | 赛狐扩展字段 |
| ingest_id | UUID FK ingest_raw | |
| collected_at | TIMESTAMPTZ | |
| created_at / updated_at | TIMESTAMPTZ | |

**唯一约束：**

```text
UNIQUE (shop_external_id, biz_date, coalesce(asin, ''), coalesce(seller_sku, ''))
```

实现时用生成列或应用层保证「asin 优先、否则 sku」业务键：

```sql
biz_key TEXT GENERATED ALWAYS AS (
  CASE WHEN asin IS NOT NULL AND asin <> '' THEN 'asin:' || asin
       ELSE 'sku:' || coalesce(seller_sku, '') END
) STORED
UNIQUE (shop_external_id, biz_date, biz_key)
```

### 4.3 新增 `amz_mom_rule`（环比规则）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| code | TEXT UNIQUE | 与 anomaly_type 对齐，如 `link_wow_units_drop` |
| name | TEXT | 展示名 |
| metric | TEXT | 首期仅 `units` / `sales_amount`（表 CHECK 可暂保留 sessions 供扩展，规则不启用） |
| period | TEXT | `day` / `week` / `month` |
| compare | TEXT | 默认 `mom`（环比）；预留 `yoy` |
| drop_ratio_gte | NUMERIC(8,4) | 下降比例 ≥ 此值触发，如 `0.30` = 降 30% |
| drop_abs_gte | NUMERIC(18,4) | 可选绝对下降量 |
| min_base_value | NUMERIC(18,4) | 上期基线过小不判（防噪），如销量 < 3 |
| severity | TEXT | info/warn/high/critical |
| enabled | BOOLEAN DEFAULT true | |
| platform | TEXT DEFAULT 'amazon' | 预留多平台复用 |
| meta | JSONB | 扩展 |
| created_at / updated_at | TIMESTAMPTZ | |

**种子阈值（已确认采用）：**

| code | metric | period | drop_ratio | min_base | severity |
|------|--------|--------|------------|----------|----------|
| link_dod_units_drop | units | day | 0.40 | 5 | warn |
| link_wow_units_drop | units | week | 0.30 | 10 | high |
| link_mom_units_drop | units | month | 0.30 | 20 | high |
| link_wow_sales_drop | sales_amount | week | 0.30 | 100 | warn |

> 后续只调 `amz_mom_rule` 行数据即可，不必改代码。

### 4.4 新增 `amz_mom_eval_run`（跑批记录，可观测）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| biz_date | DATE | 锚定业务日（通常昨日） |
| period | TEXT | day/week/month；一次 run 可只跑一种或 meta 记多种 |
| status | TEXT | pending/running/success/failed |
| rules_snapshot | JSONB | 当时启用的规则拷贝 |
| stats | JSONB | `{scanned, hit, created_tasks, updated_tasks, errors}` |
| error_message | TEXT | |
| started_at / finished_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

### 4.5 可选扩展 `task` 列（轻量）

若不想新表，可用 `anomaly_event.payload` 扛明细；建议 **task 增加可空扩展** 便于人维与 AMZ 列表：

| 字段 | 类型 | 说明 |
|------|------|------|
| domain | TEXT DEFAULT 'ops' | ops/purchase/… |
| metric_snapshot | JSONB | `{period, metric, current, previous, drop_ratio, window}` |
| owner_source | TEXT | `product` / `shop` / `manual` / `default_admin` |

**不破坏** 现有 `uq_task_open_dedupe`。

### 4.6 负责人映射 `listing_owner`（**首期必上**）

ASIN 级第一负责人；解析时 **优先于** `shop.primary_owner_user_id`。

| 字段 | 类型 |
|------|------|
| id | UUID |
| platform | TEXT |
| shop_id | UUID |
| biz_id | TEXT |
| biz_id_type | TEXT DEFAULT 'asin' |
| owner_user_id | UUID FK |
| UNIQUE(platform, shop_id, biz_id_type, biz_id) |

无 ASIN 映射时回落店铺负责人，再回落 admin 兜底（见 §6）。

### 4.7 ER 关系（简图）

```
shop 1──* fact_amz_link_daily
amz_mom_rule          （配置）
amz_mom_eval_run      （跑批）
fact + rule ──eval──► anomaly_event *──1 task
task.owner_user_id ──► org_user
task 1──* task_progress
```

---

## 5. 环比计算约定

### 5.1 窗口（**已确认：自然周 / 自然月**）

锚定业务日 `D`（通常为「昨日」），窗口如下：

| period | 本期 | 上期 |
|--------|------|------|
| day | 自然日 `D` | 自然日 `D-1` |
| week | **含 D 的自然周**（周一～周日，按 `Asia/Shanghai` 或店铺时区）合计 | **上一自然周**合计 |
| month | **含 D 的自然月**合计 | **上一自然月**合计 |

实现注意：

- 周起始：**周一**（ISO；若运营要求周日起始需再改）
- 扫描日若在周中/月中：本期为「进行中的自然周/月」已发生天数的合计 vs 上期完整周/月时，**口径需固定**  
  - **首期约定（推荐）：** 仅当 `D` 为 **上周日** 时跑 week 规则；仅当 `D` 为 **上月最后一天** 时跑 month 规则；day 规则每日跑。  
  - 或：本期用「自然周/月内已有数据合计」，上期用完整上一自然周/月（不对称，需在报表标注）。  
- **默认采用「完整周期才出周/月单」**：day 每日；week 在自然周结束后首个 Job；month 在自然月结束后首个 Job。与「自然周月」一致、噪音更小。

### 5.2 下降比例

```text
drop_ratio = (previous - current) / previous
触发：previous >= min_base_value
  AND drop_ratio >= drop_ratio_gte
  AND (drop_abs_gte IS NULL OR previous - current >= drop_abs_gte)
```

`previous = 0`：不按比例触发；可另开 `link_zero_sales` 规则。

### 5.3 标题模板

```text
[{shop_name}] {asin} 周销量环比下降 {drop_ratio%}
（{previous} → {current}，窗口 {prev_range} → {curr_range}）
```

`payload` 示例：

```json
{
  "period": "week",
  "metric": "units",
  "asin": "B0XXXX",
  "seller_sku": "SKU-1",
  "current_value": 12,
  "previous_value": 40,
  "drop_ratio": 0.70,
  "current_window": ["2026-07-21", "2026-07-27"],
  "previous_window": ["2026-07-14", "2026-07-20"],
  "rule_code": "link_wow_units_drop",
  "eval_run_id": "uuid"
}
```

---

## 6. 第一负责人解析（**含 ASIN 映射**）

按序取第一个非空：

1. **`listing_owner`**（platform + shop_id + biz_id_type=asin + asin）— **首期必查**  
2. `shop.primary_owner_user_id`  
3. 请求体 / 规则 `default_owner_user_id`  
4. 系统 admin（仅兜底，并打 `owner_source=default_admin` 审计）

`owner_source` 取值：`listing` / `shop` / `rule_default` / `default_admin`。

指派后写 `outbox_event`：

```json
{
  "event_type": "notify.task_owner",
  "aggregate_type": "task",
  "payload": {
    "task_id": "...",
    "owner_user_id": "...",
    "channel": ["feishu", "agent"],
    "aggregate_by_owner": true
  }
}
```

**人维推送收敛：** 同一 `owner_user_id` 在 N 分钟内多条新建/更新，合并为一条摘要（架构通知收敛）。

---

## 7. 接口草案

Base：`/api/v1`  
鉴权：用户 JWT；Job/采集可用 `X-Api-Key`（现有 Ingest 机制）。

### 7.1 写入链接日指标（采集）

`POST /api/v1/ingest/amz_link_daily`  
（或通用 `POST /api/v1/ingest/{source}` 且 source=`amz_link_daily`）

```json
{
  "source": "amz_link_daily",
  "platform": "amazon",
  "shop_id": "396706",
  "shop_name": "Agnis",
  "biz_date": "2026-07-27",
  "collected_at": "2026-07-28T07:05:00+08:00",
  "idempotency_key": "amz_link_daily:396706:B0XXXX:2026-07-27",
  "payload": {
    "asin": "B0XXXX",
    "seller_sku": "SKU-1",
    "title": "…",
    "units": 12,
    "sales_amount": 359.5,
    "currency": "GBP",
    "fba_fulfillable": 40
  },
  "evidence": { "source_url": null }
}
```

**处理：** upsert `fact_amz_link_daily`；`ingest_raw` 幂等。  
**不**在 Ingest 路径直接建任务（判定集中在 Job，避免半包数据误触发）。

### 7.2 触发环比扫描（Job / 管理端）

`POST /api/v1/jobs/amz/mom-scan`

```json
{
  "biz_date": "2026-07-27",
  "periods": ["day", "week"],
  "shop_ids": null,
  "dry_run": false
}
```

**响应：**

```json
{
  "run_id": "uuid",
  "status": "success",
  "stats": {
    "scanned_links": 1200,
    "hits": 37,
    "tasks_created": 12,
    "tasks_updated": 25,
    "skipped": 0
  }
}
```

权限：`admin` 或内部 worker token。

### 7.3 规则 CRUD（可二期）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/amz/mom-rules` | 列表 |
| POST | `/api/v1/amz/mom-rules` | 创建 |
| PATCH | `/api/v1/amz/mom-rules/{id}` | 更新阈值/启用 |

首期可用 SQL 种子，不做 UI。

### 7.4 任务 — 扩展现有 tasks API

**已有：**

- `GET /api/v1/tasks` — 增查询参数  
- `POST /api/v1/tasks`  
- `POST /api/v1/tasks/{id}/progress`  
- `POST /api/v1/tasks/{id}/resolve`  

**建议新增 query：**

| 参数 | 说明 |
|------|------|
| platform | `amazon` |
| anomaly_type | 精确或前缀 `link_` |
| anomaly_type_prefix | `link_` |
| owner_user_id | 人维过滤 |
| shop_id | |
| status | |
| domain | `ops` |
| page / page_size | |

**新增人维聚合：**

`GET /api/v1/tasks/by-owner`

```json
{
  "items": [
    {
      "owner_user_id": "uuid",
      "owner_display_name": "张三",
      "open_count": 5,
      "in_progress_count": 3,
      "overdue_count": 1,
      "tasks": [ /* 可选 embed，或仅计数再点进列表 */ ]
    }
  ],
  "total_owners": 8
}
```

默认 `platform=amazon` 可作 query 默认值仅在 AMZ 路由包装层处理，全局 API 不写死。

### 7.5 AMZ 专用只读（可选 BFF）

`GET /api/v1/amz/mom-tasks`  
= `GET /tasks?platform=amazon&anomaly_type_prefix=link_` + 展开 `metric_snapshot`

`GET /api/v1/amz/link-daily?shop_id&asin&from&to`  
调试与仪表盘用。

`GET /api/v1/amz/mom-runs`  
跑批历史。

### 7.6 运营动作（沿用 progress）

`POST /api/v1/tasks/{id}/progress`

```json
{
  "note": "已调价 + 站内广告加预算，观察 3 日",
  "status": "in_progress"
}
```

`note` 即「运营动作」；需结构化时可后续加 `action_code`。

---

## 8. 与现有 task_engine 对接点

```python
# 伪代码
async def apply_mom_hit(db, hit: MomHit):
    owner = await resolve_owner(db, shop_id=hit.shop_id, asin=hit.asin)
    await task_engine.upsert_task_from_anomaly(
        db,
        platform="amazon",
        shop_id=hit.shop_id,
        anomaly_type=hit.rule_code,  # link_wow_units_drop
        biz_id=hit.asin or hit.seller_sku,
        biz_id_type="asin" if hit.asin else "seller_sku",
        title=hit.title,
        detail=hit.detail,
        payload=hit.snapshot,  # 含环比明细
        owner_user_id=owner,
        severity=hit.severity,
    )
```

**需小改引擎（实施时）：**

1. 新建任务时写入 `owner_user_id`（已有参数则确认 INSERT 带上）  
2. 更新已存在任务时：可选刷新 `metric_snapshot` / 不覆盖人工改过的 owner  
3. 新建后 `enqueue notify.task_owner`（现仅 feishu.sync）  

---

## 9. SQL 草稿（002）

路径建议：`backend/migrations/002_amz_mom_tasks.sql`

```sql
-- 002 Amazon 环比样板：事实 / 规则 / 跑批 / task 扩展
-- 依赖 001_init.sql

-- 链接日事实
CREATE TABLE IF NOT EXISTS fact_amz_link_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    biz_date            DATE NOT NULL,
    asin                TEXT,
    seller_sku          TEXT,
    parent_asin         TEXT,
    title               TEXT,
    units               NUMERIC(18, 4) NOT NULL DEFAULT 0,
    sales_amount        NUMERIC(18, 4) NOT NULL DEFAULT 0,
    currency            TEXT DEFAULT 'GBP',
    sessions            NUMERIC(18, 4),
    conversion_rate     NUMERIC(18, 6),
    fba_fulfillable     NUMERIC(18, 4),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingest_id           UUID REFERENCES ingest_raw(id),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    biz_key             TEXT GENERATED ALWAYS AS (
                            CASE
                                WHEN asin IS NOT NULL AND btrim(asin) <> '' THEN 'asin:' || btrim(asin)
                                ELSE 'sku:' || coalesce(btrim(seller_sku), '')
                            END
                        ) STORED,
    CONSTRAINT chk_amz_link_identity CHECK (
        (asin IS NOT NULL AND btrim(asin) <> '')
        OR (seller_sku IS NOT NULL AND btrim(seller_sku) <> '')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_amz_link_daily
    ON fact_amz_link_daily (shop_external_id, biz_date, biz_key);

CREATE INDEX IF NOT EXISTS idx_fact_amz_link_shop_date
    ON fact_amz_link_daily (shop_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_amz_link_asin_date
    ON fact_amz_link_daily (asin, biz_date DESC);

-- 环比规则
CREATE TABLE IF NOT EXISTS amz_mom_rule (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    metric              TEXT NOT NULL CHECK (metric IN ('units', 'sales_amount', 'sessions')),
    period              TEXT NOT NULL CHECK (period IN ('day', 'week', 'month')),
    compare             TEXT NOT NULL DEFAULT 'mom',
    drop_ratio_gte      NUMERIC(8, 4) NOT NULL,
    drop_abs_gte        NUMERIC(18, 4),
    min_base_value      NUMERIC(18, 4) NOT NULL DEFAULT 0,
    severity            TEXT NOT NULL DEFAULT 'warn'
                        CHECK (severity IN ('info', 'warn', 'high', 'critical')),
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    platform            TEXT NOT NULL DEFAULT 'amazon',
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 跑批
CREATE TABLE IF NOT EXISTS amz_mom_eval_run (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    biz_date            DATE NOT NULL,
    period              TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'success', 'failed')),
    rules_snapshot      JSONB NOT NULL DEFAULT '[]'::jsonb,
    stats               JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_amz_mom_run_date ON amz_mom_eval_run (biz_date DESC);

-- task 轻量扩展
ALTER TABLE task ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT 'ops';
ALTER TABLE task ADD COLUMN IF NOT EXISTS metric_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE task ADD COLUMN IF NOT EXISTS owner_source TEXT;

CREATE INDEX IF NOT EXISTS idx_task_domain_platform ON task (domain, platform, status);

-- ASIN 负责人（可选）
CREATE TABLE IF NOT EXISTS listing_owner (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            TEXT NOT NULL,
    shop_id             UUID REFERENCES shop(id),
    biz_id              TEXT NOT NULL,
    biz_id_type         TEXT NOT NULL DEFAULT 'asin',
    owner_user_id       UUID NOT NULL REFERENCES org_user(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, shop_id, biz_id_type, biz_id)
);

-- 种子规则（阈值占位，上线前业务确认）
INSERT INTO amz_mom_rule (code, name, metric, period, drop_ratio_gte, min_base_value, severity)
VALUES
    ('link_dod_units_drop', '链接日销量环比下降', 'units', 'day', 0.40, 5, 'warn'),
    ('link_wow_units_drop', '链接周销量环比下降', 'units', 'week', 0.30, 10, 'high'),
    ('link_mom_units_drop', '链接月销量环比下降', 'units', 'month', 0.30, 20, 'high'),
    ('link_wow_sales_drop', '链接周销售额环比下降', 'sales_amount', 'week', 0.30, 100, 'warn')
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE fact_amz_link_daily IS 'Amazon 链接日指标；环比样板事实源';
COMMENT ON TABLE amz_mom_rule IS 'Amazon 环比异常规则；code=anomaly_type';
COMMENT ON TABLE amz_mom_eval_run IS '环比扫描跑批记录';
```

---

## 10. OpenAPI 片段（草案）

```yaml
# 可并入 openapi-v1.yaml 的 paths 摘要

/api/v1/jobs/amz/mom-scan:
  post:
    tags: [amz-mom]
    summary: 触发 Amazon 链接环比扫描
    security: [{ bearerAuth: [] }]
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              biz_date: { type: string, format: date }
              periods:
                type: array
                items: { type: string, enum: [day, week, month] }
              dry_run: { type: boolean, default: false }
    responses:
      "200":
        description: 跑批结果

/api/v1/tasks/by-owner:
  get:
    tags: [tasks]
    summary: 按负责人聚合未闭环任务（人维）
    security: [{ bearerAuth: [] }]
    parameters:
      - in: query
        name: platform
        schema: { type: string }
      - in: query
        name: anomaly_type_prefix
        schema: { type: string, example: link_ }
    responses:
      "200":
        description: 人维汇总

/api/v1/amz/mom-rules:
  get:
    tags: [amz-mom]
    summary: 环比规则列表
  post:
    tags: [amz-mom]
    summary: 创建规则

/api/v1/amz/link-daily:
  get:
    tags: [amz-mom]
    summary: 链接日指标查询
```

---

## 11. 实施切片（确认草案后）

| 序号 | 切片 | 交付 |
|------|------|------|
| A | 执行 `002` migration + 种子规则 | 表可用 ✅ 已完成 |
| B | Ingest `amz_link_daily` → fact upsert | mock 脚本可灌数 ✅ 已完成 |
| C | `mom-scan` Job：day 每日；week/month 在完整自然周期结束后跑 | dry_run + 真实建单（多单并行） |
| D | `listing_owner` + shop 回落 + tasks 列表参数 + by-owner | 人维 API |
| E | outbox 通知事件（可先日志） | 可观测 |
| F | Web「环比异常任务」接真实 API | 演示闭环 |

---

## 12. 业务确认清单

| # | 议题 | 状态 | 结论 |
|---|------|------|------|
| 1 | 周/月窗口 | ✅ 已确认 | 自然周、自然月；完整周期出周/月单（见 §5.1） |
| 2 | 种子阈值 | ✅ 已确认 | 采用 §4.3 四条规则 |
| 3 | 多类型同时命中 | ✅ 已确认 | 多单并行 |
| 4 | 负责人 | ✅ 已确认 | 上 `listing_owner` ASIN 映射 |
| 5 | 首期指标 | ✅ 已确认 | 仅 units + sales_amount |

**实现前仍可再定（工程细节）：** 自然周是否周一为第一天（草案默认 ISO 周一）。

---

## 13. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-07-28 | 首版草案：表 + 接口 + 计算约定 + SQL 草稿 |
| v0.2 | 2026-07-28 | 锁定五项业务决策：自然周月、种子阈值、多单并行、ASIN 负责人、指标仅件+钱 |
