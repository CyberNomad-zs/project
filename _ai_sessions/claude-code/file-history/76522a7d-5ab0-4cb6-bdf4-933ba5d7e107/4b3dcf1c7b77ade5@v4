-- 010 TikTok 异常任务（对齐飞书 AMZ「异常任务」表形态）
-- 飞书参考：ASIN健康度监控 · 异常任务
--   主键 / 日期 / 店铺 / ASIN / 产品 / 中文名称 / 异常类型 / …
-- TK 映射：ASIN → product_id（或 seller_sku）；其余协作字段对齐 public.task
-- 依赖：001_init.sql · 008_tk_schema.sql（schema tk 已存在）
--
-- 正式链路：规则/人工/Ingest → tk.fact_tk_anomaly_task（+ 可选投影 public.task）
--          → 同步 Job → 飞书「TK异常任务」

CREATE SCHEMA IF NOT EXISTS tk;

-- ---------------------------------------------------------------------------
-- 异常任务事实（飞书「异常任务」镜像；SoT 在 PG）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tk_anomaly_task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 飞书「主键」：稳定业务键，如 T20260804-a1b2c3d4 或 tiktok:{shop}:{product}:{type}:{date}
    task_key            TEXT NOT NULL,
    biz_date            DATE NOT NULL DEFAULT (CURRENT_DATE),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT,
    shop_name           TEXT,
    -- 对象：商品优先；活动/店铺级异常时 product_id 可空，object_ref 必填
    product_id          TEXT,
    seller_sku          TEXT,
    product_name        TEXT,
    product_name_cn     TEXT,
    object_ref          TEXT,
    object_type         TEXT NOT NULL DEFAULT 'product'
                        CHECK (object_type IN ('product', 'campaign', 'shop', 'order', 'other')),
    -- 异常类型（中文稳定名，与飞书单选一致；code 进 anomaly_code）
    anomaly_type        TEXT NOT NULL,
    anomaly_code        TEXT,
    priority            TEXT NOT NULL DEFAULT 'P1'
                        CHECK (priority IN ('P0', 'P1', 'P2')),
    -- 协作
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'resolved', 'cancelled', 'ignored')),
    owner_name          TEXT,
    owner_user_id       UUID REFERENCES public.org_user(id),
    due_at              TIMESTAMPTZ,
    progress_note       TEXT,
    summary             TEXT NOT NULL DEFAULT '',
    metric_snapshot     TEXT,
    -- 关联中心任务引擎（可选）
    center_task_id      UUID REFERENCES public.task(id),
    anomaly_event_id    UUID REFERENCES public.anomaly_event(id),
    dedupe_key          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_url          TEXT,
    row_status          TEXT NOT NULL DEFAULT 'success',
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    UNIQUE (task_key)
);

-- 未闭环：同店+对象+异常类型 唯一（与 public.task 开放单规则对齐）
CREATE UNIQUE INDEX IF NOT EXISTS uq_tk_anomaly_task_open_dedupe
    ON tk.fact_tk_anomaly_task (dedupe_key)
    WHERE status IN ('open', 'in_progress') AND dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_date
    ON tk.fact_tk_anomaly_task (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_status
    ON tk.fact_tk_anomaly_task (status, priority, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_shop
    ON tk.fact_tk_anomaly_task (shop_external_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_product
    ON tk.fact_tk_anomaly_task (product_id)
    WHERE product_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_owner
    ON tk.fact_tk_anomaly_task (owner_name)
    WHERE owner_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_type
    ON tk.fact_tk_anomaly_task (anomaly_type, status);

COMMENT ON TABLE tk.fact_tk_anomaly_task IS
    'TK 异常任务；对齐飞书 AMZ「异常任务」：主键/日期/店铺/商品/中文名/异常类型/负责人/状态；经 PG 再同步飞书';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.task_key IS '飞书主键；幂等键';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.product_id IS 'TK 商品 ID（对应 AMZ ASIN）';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.product_name_cn IS '中文名称';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.anomaly_type IS '飞书展示用中文异常类型';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.anomaly_code IS '机器码，如 stock_low / roi_low / sales_drop';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.dedupe_key IS '未闭环去重：tiktok:{object}:{anomaly_code}';

-- public 兼容视图（报表/旧 SQL）
DROP VIEW IF EXISTS public.fact_tk_anomaly_task CASCADE;
CREATE OR REPLACE VIEW public.fact_tk_anomaly_task AS
    SELECT * FROM tk.fact_tk_anomaly_task;
COMMENT ON VIEW public.fact_tk_anomaly_task IS '兼容视图 → tk.fact_tk_anomaly_task';

-- 授权
GRANT SELECT, INSERT, UPDATE, DELETE ON tk.fact_tk_anomaly_task TO qingquan;

-- ---------------------------------------------------------------------------
-- 异常类型字典（可选配置；规则引擎可读）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.dim_tk_anomaly_type (
    code            TEXT PRIMARY KEY,
    name_cn         TEXT NOT NULL,
    object_type     TEXT NOT NULL DEFAULT 'product',
    severity_default TEXT NOT NULL DEFAULT 'warn'
                    CHECK (severity_default IN ('info', 'warn', 'high', 'critical')),
    priority_default TEXT NOT NULL DEFAULT 'P1'
                    CHECK (priority_default IN ('P0', 'P1', 'P2')),
    description     TEXT,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 种子已 TK 针对化；完整清单与说明见 011_tk_anomaly_types_specialize.sql
-- 此处保留最小可启动集，011 会 upsert 全量并停用旧 AMZ 口径码
INSERT INTO tk.dim_tk_anomaly_type (code, name_cn, object_type, severity_default, priority_default, description, sort_order)
VALUES
    ('ads_roi_low',          '广告ROI过低',     'campaign', 'high',     'P1', '活动 ROI 低于目标或阈值', 10),
    ('ads_spend_no_sale',    '广告空耗',       'campaign', 'high',     'P1', '花费>0 无成交', 20),
    ('product_stockout',     '商品断货',       'product',  'critical', 'P0', '可售库存=0 或断货', 60),
    ('product_stock_low',    '商品库存不足',   'product',  'high',     'P0', '库存低于补货阈值', 70),
    ('product_sales_drop',   '商品销量骤降',   'product',  'high',     'P1', '销量环比下降超阈', 90),
    ('shop_gmv_drop',        '店铺GMV骤降',    'shop',     'high',     'P1', '店日 GMV 环比下降', 130),
    ('shop_health_low',      '店铺健康分低',   'shop',     'critical', 'P0', '健康分低于红线', 160),
    ('shop_late_dispatch',   '延迟发货率高',   'shop',     'high',     'P0', '延迟发货率超阈', 170),
    ('other',                '其它',           'other',    'info',     'P2', '未分类', 999)
ON CONFLICT (code) DO UPDATE SET
    name_cn = EXCLUDED.name_cn,
    description = EXCLUDED.description,
    enabled = EXCLUDED.enabled;

GRANT SELECT, INSERT, UPDATE, DELETE ON tk.dim_tk_anomaly_type TO qingquan;

DROP VIEW IF EXISTS public.dim_tk_anomaly_type CASCADE;
CREATE OR REPLACE VIEW public.dim_tk_anomaly_type AS
    SELECT * FROM tk.dim_tk_anomaly_type;

COMMENT ON TABLE tk.dim_tk_anomaly_type IS 'TK 异常类型字典；name_cn = 飞书「异常类型」选项';
