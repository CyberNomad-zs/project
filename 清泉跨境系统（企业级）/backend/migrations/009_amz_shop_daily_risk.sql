-- 009 Amazon 驾驶舱：店铺日经营 + 风险告警（飞书 T1/T6）
-- 文档：docs/AMZ-飞书驾驶舱建表方案.md
-- 依赖：001_init.sql · 002_amz_mom_tasks.sql（链接日已有）
-- 口径：净利润/ROI 列可空（业务未定）；币种必填便于后续合计策略

-- ---------------------------------------------------------------------------
-- T1 对应：店铺 × 日 经营事实
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_amz_shop_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    biz_date            DATE NOT NULL,
    marketplace         TEXT,
    currency            TEXT NOT NULL DEFAULT 'GBP',
    sales_amount        NUMERIC(18, 4) NOT NULL DEFAULT 0,
    orders_cnt          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    units               NUMERIC(18, 4) NOT NULL DEFAULT 0,
    sessions            NUMERIC(18, 4),
    add_to_cart         NUMERIC(18, 4),
    aov                 NUMERIC(18, 4),
    refund_units        NUMERIC(18, 4),
    refund_rate         NUMERIC(18, 6),
    gross_profit        NUMERIC(18, 4),
    ad_spend            NUMERIC(18, 4) NOT NULL DEFAULT 0,
    ad_sales            NUMERIC(18, 4) NOT NULL DEFAULT 0,
    acos                NUMERIC(18, 6),
    ad_contrib_margin   NUMERIC(18, 4),
    net_profit          NUMERIC(18, 4),
    net_margin          NUMERIC(18, 6),
    roi                 NUMERIC(18, 6),
    organic_sales       NUMERIC(18, 4),
    ad_orders           NUMERIC(18, 4),
    organic_orders      NUMERIC(18, 4),
    cogs                NUMERIC(18, 4),
    fba_fees            NUMERIC(18, 4),
    platform_fees       NUMERIC(18, 4),
    sales_mom_ratio     NUMERIC(18, 6),
    profit_mom_ratio    NUMERIC(18, 6),
    sales_yoy_ratio     NUMERIC(18, 6),
    row_status          TEXT NOT NULL DEFAULT 'success',
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingest_id           UUID REFERENCES ingest_raw(id),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_fact_amz_shop_daily_date
    ON fact_amz_shop_daily (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_amz_shop_daily_shop_date
    ON fact_amz_shop_daily (shop_id, biz_date DESC);

-- 链接日扩展列（T3 仪表盘常用；可空，不破坏既有 Ingest）
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS ad_spend NUMERIC(18, 4);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS acos NUMERIC(18, 6);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS unit_net_profit NUMERIC(18, 4);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS days_of_supply NUMERIC(18, 4);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS refund_rate NUMERIC(18, 6);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS units_mom_ratio NUMERIC(18, 6);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS sales_mom_ratio NUMERIC(18, 6);
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS problem_tags TEXT;
ALTER TABLE fact_amz_link_daily ADD COLUMN IF NOT EXISTS owner_name TEXT;

-- ---------------------------------------------------------------------------
-- T6 对应：风险告警（可人工/规则/任务投影写入；同步飞书）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_amz_risk_alert (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_key           TEXT NOT NULL,
    detected_on         DATE NOT NULL DEFAULT (CURRENT_DATE),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT,
    shop_name           TEXT,
    object_ref          TEXT,
    risk_type           TEXT NOT NULL,
    priority            TEXT NOT NULL DEFAULT 'P1'
                        CHECK (priority IN ('P0', 'P1', 'P2')),
    summary             TEXT NOT NULL DEFAULT '',
    metric_snapshot     TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'resolved', 'ignored')),
    owner_name          TEXT,
    task_id             UUID REFERENCES task(id),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingest_id           UUID REFERENCES ingest_raw(id),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (alert_key)
);

CREATE INDEX IF NOT EXISTS idx_fact_amz_risk_status
    ON fact_amz_risk_alert (status, priority, detected_on DESC);

CREATE INDEX IF NOT EXISTS idx_fact_amz_risk_shop_date
    ON fact_amz_risk_alert (shop_external_id, detected_on DESC);

COMMENT ON TABLE fact_amz_shop_daily IS 'Amazon 店铺日经营；飞书 T1 店铺日经营';
COMMENT ON TABLE fact_amz_risk_alert IS 'Amazon 风险告警；飞书 T6；正式链路经 PG 再同步';
