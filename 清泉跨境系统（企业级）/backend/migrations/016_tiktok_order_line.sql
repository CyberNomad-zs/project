-- 016 TikTok 订单明细行（SKU 粒度）
-- 依赖：005_tiktok_orders.sql + 008_tk_schema.sql（表在 tk）
-- 粒度：店铺 × 订单号 × 行键（sku_id / seller_sku / line_no）
-- 订单头 fact_tiktok_order 仍保留；本表补 SKU 级数量/金额

CREATE TABLE IF NOT EXISTS tk.fact_tiktok_order_line (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    order_id            TEXT NOT NULL,
    line_no             INT NOT NULL DEFAULT 1,
    line_key            TEXT NOT NULL,
    product_id          TEXT,
    product_name        TEXT,
    seller_sku          TEXT,
    sku_id              TEXT,
    quantity            NUMERIC(18, 4) NOT NULL DEFAULT 0,
    pay_amount          NUMERIC(18, 4),
    unit_price          NUMERIC(18, 4),
    currency            TEXT DEFAULT 'GBP',
    biz_date            DATE,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, order_id, line_key)
);

CREATE INDEX IF NOT EXISTS idx_tk_order_line_order
    ON tk.fact_tiktok_order_line (shop_external_id, order_id);

CREATE INDEX IF NOT EXISTS idx_tk_order_line_biz_date
    ON tk.fact_tiktok_order_line (biz_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_tk_order_line_seller_sku
    ON tk.fact_tiktok_order_line (seller_sku)
    WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '';

CREATE INDEX IF NOT EXISTS idx_tk_order_line_sku_id
    ON tk.fact_tiktok_order_line (sku_id)
    WHERE sku_id IS NOT NULL AND btrim(sku_id) <> '';

COMMENT ON TABLE tk.fact_tiktok_order_line IS 'TK 订单明细行（SKU）；幂等 shop_external_id+order_id+line_key';
COMMENT ON COLUMN tk.fact_tiktok_order_line.line_key IS '稳定行键：优先 sku_id，其次 seller_sku，再次 line_no';
COMMENT ON COLUMN tk.fact_tiktok_order_line.raw_extra IS '详情页多余字段 JSON';

-- public 兼容视图
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'tk' AND table_name = 'fact_tiktok_order_line' AND table_type = 'BASE TABLE'
  ) THEN
    EXECUTE 'DROP VIEW IF EXISTS public.fact_tiktok_order_line CASCADE';
    BEGIN
      EXECUTE 'CREATE OR REPLACE VIEW public.fact_tiktok_order_line AS SELECT * FROM tk.fact_tiktok_order_line';
      EXECUTE 'COMMENT ON VIEW public.fact_tiktok_order_line IS ''兼容视图 → tk.fact_tiktok_order_line''';
    EXCEPTION WHEN duplicate_table THEN
      RAISE NOTICE 'public.fact_tiktok_order_line still base table, no view';
    END;
  END IF;
END $$;
