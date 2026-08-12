-- 008 TK schema：与 Temu 的 temu schema 对称，把 TK 事实表迁入 tk
-- 依赖：001–007 已在 public 建好相关表（或本脚本对「表已在 tk」可重复执行）
--
-- 设计：
--   schema tk     = TikTok 平台事实（广告/订单/商品/店级KPI/健康/财务）
--   public.shop / public.ingest_raw / public.task… = 三平台共用中心
--
-- 用法：
--   psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -f 008_tk_schema.sql
--
-- 可重复：已在 tk 的表会跳过迁移；public 上的兼容视图会重建。

CREATE SCHEMA IF NOT EXISTS tk;
COMMENT ON SCHEMA tk IS 'TikTok 店铺运营采集事实（广告/订单/商品/店级KPI/健康/财务）；中心 shop/ingest_raw 仍在 public';

-- 把 public 下已有 TK 相关表挪到 tk（若仍在 public）
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'fact_ads_campaign_daily',
    'fact_tiktok_order',
    'fact_tiktok_product',
    'fact_tiktok_shop_daily',
    'fact_tiktok_health_daily',
    'fact_tiktok_finance_daily'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = t
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'tk' AND table_name = t
    ) THEN
      EXECUTE format('ALTER TABLE public.%I SET SCHEMA tk', t);
      RAISE NOTICE 'moved public.% to tk.%', t, t;
    ELSIF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'tk' AND table_name = t
    ) THEN
      RAISE NOTICE 'already in tk.% — skip', t;
    ELSE
      RAISE NOTICE 'table % not found in public or tk — skip (create via earlier migrations first)', t;
    END IF;
  END LOOP;
END $$;

-- public 兼容视图：旧 SQL / 报表若仍写 public.fact_* 可继续用
-- （写入仍应打 tk. 或依赖 search_path）
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'fact_ads_campaign_daily',
    'fact_tiktok_order',
    'fact_tiktok_product',
    'fact_tiktok_shop_daily',
    'fact_tiktok_health_daily',
    'fact_tiktok_finance_daily'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'tk' AND table_name = t AND table_type = 'BASE TABLE'
    ) THEN
      EXECUTE format('DROP VIEW IF EXISTS public.%I CASCADE', t);
      -- 若 public 上还残留同名空壳则上面已处理；用视图转发
      BEGIN
        EXECUTE format('CREATE OR REPLACE VIEW public.%I AS SELECT * FROM tk.%I', t, t);
        EXECUTE format('COMMENT ON VIEW public.%I IS %L', t,
          '兼容视图 → tk.' || t || '；新代码请直接用 tk.' || t);
      EXCEPTION WHEN duplicate_table THEN
        -- public 仍是 BASE TABLE（迁移未挪走）时忽略
        RAISE NOTICE 'public.% still base table, no view', t;
      END;
    END IF;
  END LOOP;
END $$;

-- 授权（应用用户 qingquan）
GRANT USAGE ON SCHEMA tk TO qingquan;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tk TO qingquan;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA tk TO qingquan;
ALTER DEFAULT PRIVILEGES IN SCHEMA tk
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO qingquan;

-- 验收
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM information_schema.tables
  WHERE table_schema = 'tk' AND table_type = 'BASE TABLE';
  RAISE NOTICE 'tk schema ready: % base tables', n;
END $$;
