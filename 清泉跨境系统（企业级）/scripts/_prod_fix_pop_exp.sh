#!/usr/bin/env bash
set -euo pipefail

echo "=== shop rows for TK ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT id, platform, external_shop_id, name, status
FROM public.shop
WHERE platform ILIKE '%tiktok%' OR external_shop_id IN ('27758103898326','27501502216807','27328767468273')
ORDER BY name;
"

echo "=== ensure Pop shop row ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
INSERT INTO public.shop (id, platform, external_shop_id, name, status, created_at, updated_at)
SELECT gen_random_uuid(), 'tiktok', '27758103898326', 'Gardena', 'active', now(), now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.shop WHERE external_shop_id = '27758103898326'
);
SELECT id, external_shop_id, name FROM public.shop WHERE external_shop_id = '27758103898326';
"

echo "=== insert fact from payload ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
WITH s AS (
  SELECT id AS shop_id, name FROM public.shop WHERE external_shop_id = '27758103898326' LIMIT 1
), p AS (
  SELECT payload, id AS ingest_id, collected_at FROM public.ingest_raw
  WHERE id = '77ad3c0a-3bb7-4b36-979f-e9b273dd0dba'
)
INSERT INTO tk.fact_tiktok_experience_daily (
  id, shop_id, shop_external_id, shop_name, biz_date,
  experience_score, product_satisfaction, fulfillment_score, customer_service_score,
  metrics_json, source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
)
SELECT
  gen_random_uuid(),
  s.shop_id,
  '27758103898326',
  COALESCE(s.name, 'Gardena'),
  '2026-08-11'::date,
  (p.payload->>'experience_score')::numeric,
  (p.payload->>'product_satisfaction')::numeric,
  (p.payload->>'fulfillment_score')::numeric,
  (p.payload->>'customer_service_score')::numeric,
  COALESCE(p.payload->'metrics_json', '{}'::jsonb),
  p.payload->>'source_url',
  jsonb_build_object('scrape_raw', p.payload->'scrape_raw'),
  COALESCE(p.collected_at, now()),
  p.ingest_id,
  now(), now()
FROM s, p
ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
  experience_score = EXCLUDED.experience_score,
  product_satisfaction = EXCLUDED.product_satisfaction,
  fulfillment_score = EXCLUDED.fulfillment_score,
  customer_service_score = EXCLUDED.customer_service_score,
  metrics_json = EXCLUDED.metrics_json,
  source_url = EXCLUDED.source_url,
  raw_extra = EXCLUDED.raw_extra,
  ingest_id = EXCLUDED.ingest_id,
  updated_at = now();
"

echo "=== verify all real experience ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, shop_external_id, biz_date, experience_score,
       product_satisfaction, fulfillment_score, customer_service_score
FROM tk.fact_tiktok_experience_daily
WHERE shop_external_id != 'smoke-shop-exp'
ORDER BY shop_name;
"

echo "=== re-sync experience feishu ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py

echo "FIX_POP_DONE"
