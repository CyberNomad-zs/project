-- smoke sample rows (safe synthetic shop_external_id)
INSERT INTO tk.fact_tiktok_experience_daily (
  shop_external_id, shop_name, biz_date, experience_score,
  product_satisfaction, fulfillment_score, customer_service_score,
  metrics_json, source_url, collected_at
) VALUES
 ('smoke-shop-exp','SMOKE体验', CURRENT_DATE - 1, 3.9, 4.0, 4.5, 2.5, '{}'::jsonb, 'smoke', now()),
 ('smoke-shop-exp','SMOKE体验', CURRENT_DATE, 3.8, 4.0, 4.5, 2.4, '{}'::jsonb, 'smoke', now())
ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
  experience_score = EXCLUDED.experience_score,
  customer_service_score = EXCLUDED.customer_service_score,
  updated_at = now();

INSERT INTO tk.fact_tiktok_creator_health_daily (
  shop_external_id, shop_name, creator_key, creator_name, biz_date, health_score, collected_at
) VALUES
 ('smoke-shop-exp','SMOKE体验','Grace','Grace', CURRENT_DATE - 1, 200, now()),
 ('smoke-shop-exp','SMOKE体验','Grace','Grace', CURRENT_DATE, 170, now()),
 ('smoke-shop-exp','SMOKE体验','Emma','Emma', CURRENT_DATE, 200, now())
ON CONFLICT (shop_external_id, creator_key, biz_date) DO UPDATE SET
  health_score = EXCLUDED.health_score, updated_at = now();
