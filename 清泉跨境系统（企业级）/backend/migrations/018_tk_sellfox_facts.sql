-- 018 赛狐 OpenAPI → TK 财务/商品补充事实
-- 依赖：008_tk_schema.sql（tk schema）
-- 说明：
--   - 利润报表多为「查询区间汇总」，用 period_start/period_end 存，不与前台日 KPI 混加
--   - 账单明细按结算行存；可再 rollup 到 fact_tiktok_finance_daily
--   - 商品仍写 tk.fact_tiktok_product（raw_extra.source=sellfox）

CREATE SCHEMA IF NOT EXISTS tk;

-- 店级利润区间快照
CREATE TABLE IF NOT EXISTS tk.fact_sellfox_tk_profit_shop (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,          -- 紫鸟 storeId
    shop_name           TEXT,
    sellfox_shop_id     TEXT,                   -- 赛狐数字 shopId，如 610764
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    currency            TEXT DEFAULT 'GBP',
    sales_qty           NUMERIC(18, 4),
    return_qty          NUMERIC(18, 4),
    gross_sales_amount  NUMERIC(18, 4),
    gross_sales_refund  NUMERIC(18, 4),
    settlement_amount   NUMERIC(18, 4),
    gross_profit        NUMERIC(18, 4),
    gross_rate          NUMERIC(18, 6),
    ads_cost            NUMERIC(18, 4),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, period_start, period_end, currency)
);

CREATE INDEX IF NOT EXISTS idx_sf_tk_profit_shop_period
    ON tk.fact_sellfox_tk_profit_shop (period_end DESC, shop_external_id);

COMMENT ON TABLE tk.fact_sellfox_tk_profit_shop IS '赛狐 TK 利润报表-按店铺（区间汇总）';

-- SKU/MSKU 利润区间快照
CREATE TABLE IF NOT EXISTS tk.fact_sellfox_tk_profit_sku (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    sellfox_shop_id     TEXT,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    grain               TEXT NOT NULL DEFAULT 'sku',  -- sku | msku
    sku_key             TEXT NOT NULL,                 -- 幂等键：sku 或 msku 拼接
    sku_list            JSONB NOT NULL DEFAULT '[]'::jsonb,
    msku_list           JSONB NOT NULL DEFAULT '[]'::jsonb,
    commodity_name_list JSONB NOT NULL DEFAULT '[]'::jsonb,
    currency            TEXT DEFAULT 'GBP',
    sales_qty           NUMERIC(18, 4),
    return_qty          NUMERIC(18, 4),
    gross_sales_amount  NUMERIC(18, 4),
    gross_sales_refund  NUMERIC(18, 4),
    settlement_amount   NUMERIC(18, 4),
    gross_profit        NUMERIC(18, 4),
    gross_rate          NUMERIC(18, 6),
    ads_cost            NUMERIC(18, 4),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, period_start, period_end, grain, sku_key, currency)
);

CREATE INDEX IF NOT EXISTS idx_sf_tk_profit_sku_period
    ON tk.fact_sellfox_tk_profit_sku (period_end DESC, shop_external_id);
CREATE INDEX IF NOT EXISTS idx_sf_tk_profit_sku_key
    ON tk.fact_sellfox_tk_profit_sku (sku_key);

COMMENT ON TABLE tk.fact_sellfox_tk_profit_sku IS '赛狐 TK 利润报表-按 SKU/MSKU（区间汇总）';

-- 账单/结算明细（订单级流水）
CREATE TABLE IF NOT EXISTS tk.fact_sellfox_tk_statement (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    sellfox_shop_id     TEXT,
    statement_id        TEXT NOT NULL,
    order_id            TEXT NOT NULL DEFAULT '',
    statement_time      TIMESTAMPTZ,
    statement_date      DATE,
    statement_status    TEXT,
    payment_status      TEXT,
    order_status        TEXT,
    order_type          TEXT,
    order_create_time   TIMESTAMPTZ,
    marketplace_id      TEXT,
    marketplace_name    TEXT,
    currency            TEXT DEFAULT 'GBP',
    sales_qty           NUMERIC(18, 4),
    return_qty          NUMERIC(18, 4),
    gross_sales_amount  NUMERIC(18, 4),
    gross_sales_refund  NUMERIC(18, 4),
    settlement_amount   NUMERIC(18, 4),
    ads_cost            NUMERIC(18, 4),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, statement_id, order_id)
);

CREATE INDEX IF NOT EXISTS idx_sf_tk_statement_date
    ON tk.fact_sellfox_tk_statement (statement_date DESC, shop_external_id);
CREATE INDEX IF NOT EXISTS idx_sf_tk_statement_order
    ON tk.fact_sellfox_tk_statement (order_id);

COMMENT ON TABLE tk.fact_sellfox_tk_statement IS '赛狐 TK 利润报表-账单明细（结算流水）';

-- 同步运行日志
CREATE TABLE IF NOT EXISTS tk.sellfox_sync_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',  -- running|success|partial|failed
    period_start    DATE,
    period_end      DATE,
    modules         JSONB NOT NULL DEFAULT '[]'::jsonb,
    stats           JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tk TO qingquan;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA tk TO qingquan;
