-- 011 TikTok 异常类型字典 · TK 针对化（替换 010 中偏 AMZ 的种子）
-- 依据现有采集域：广告活动日 / 商品 / 店 KPI / 健康 / 财务
-- 依赖：010_tk_anomaly_task.sql
-- 可重复执行

-- 1) 停用旧「照搬 AMZ」码（保留行以免历史 anomaly_code 断引用；enabled=false）
UPDATE tk.dim_tk_anomaly_type
SET enabled = FALSE,
    description = COALESCE(description, '') || ' [已弃用·请改用 011 TK 专用码]'
WHERE code IN (
    'stock_low', 'stock_high', 'sales_drop', 'zero_sales',
    'roi_low', 'ads_waste', 'review_risk', 'health_risk', 'price_anomaly'
)
AND enabled = TRUE;

-- 2) 写入 TK 专用异常类型
INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    -- —— 广告（fact_ads_campaign_daily）——
    ('ads_roi_low',          '广告ROI过低',     'campaign', 'high',     'P1',
     '活动 ROI 低于目标ROI 或全局阈值（默认 3）；对标运营「低效亏损」', 10, TRUE),
    ('ads_spend_no_sale',    '广告空耗',       'campaign', 'high',     'P1',
     '花费>0 且广告销售额/订单=0', 20, TRUE),
    ('ads_budget_burn',      '广告预算将尽',   'campaign', 'warn',     'P2',
     '日预算消耗率过高（如 >80%），有断流或超支风险', 30, TRUE),
    ('ads_cpa_high',         '广告下单成本高', 'campaign', 'warn',     'P2',
     '平均下单成本(CPA) 显著高于店铺/类目基线', 40, TRUE),
    ('ads_plan_anomaly',     '广告计划异常',   'campaign', 'warn',     'P2',
     '投放中但无数据、或关停后仍持续花费等计划状态异常', 50, TRUE),

    -- —— 商品（fact_tiktok_product）——
    ('product_stockout',     '商品断货',       'product',  'critical', 'P0',
     '可售库存=0 或低于断货阈值', 60, TRUE),
    ('product_stock_low',    '商品库存不足',   'product',  'high',     'P0',
     '可售库存低于补货阈值（未断货）', 70, TRUE),
    ('product_overstock',    '商品库存积压',   'product',  'warn',     'P2',
     '库存过高 / 周转过慢', 80, TRUE),
    ('product_sales_drop',   '商品销量骤降',   'product',  'high',     'P1',
     '商品销量日或周环比下降超阈', 90, TRUE),
    ('product_zero_sales',   '商品持续零销',   'product',  'warn',     'P1',
     '在售商品连续 N 日销量为 0', 100, TRUE),
    ('product_delist',       '商品下架异常',   'product',  'high',     'P1',
     '非预期下架 / 审核中滞留 / 状态异常', 110, TRUE),
    ('product_price_anomaly','商品价格异常',   'product',  'warn',     'P2',
     '零售价或促销价异常波动', 120, TRUE),

    -- —— 店铺经营（fact_tiktok_shop_daily）——
    ('shop_gmv_drop',        '店铺GMV骤降',    'shop',     'high',     'P1',
     '店日 GMV 环比下降超阈', 130, TRUE),
    ('shop_order_drop',      '店铺订单骤降',   'shop',     'high',     'P1',
     '店日订单量环比下降超阈', 140, TRUE),
    ('shop_refund_spike',    '店铺退款异常',   'shop',     'high',     'P1',
     '退款金额或退款率异常升高', 150, TRUE),

    -- —— 账号健康（fact_tiktok_health_daily）——
    ('shop_health_low',      '店铺健康分低',   'shop',     'critical', 'P0',
     '健康分低于平台/内部红线', 160, TRUE),
    ('shop_late_dispatch',   '延迟发货率高',   'shop',     'high',     'P0',
     '延迟发货率超阈（影响健康分与流量）', 170, TRUE),
    ('shop_neg_feedback',    '负面反馈率高',   'shop',     'high',     'P1',
     '负面反馈率超阈', 180, TRUE),

    -- —— 财务（fact_tiktok_finance_daily）——
    ('finance_pending_high', '待结算积压',     'shop',     'warn',     'P2',
     '待结算金额异常偏高或账期异常', 190, TRUE),
    ('finance_refund_high',  '财务退款偏高',   'shop',     'warn',     'P2',
     '财务侧退款金额异常', 200, TRUE),

    -- —— 兜底 ——
    ('other',                '其它',           'other',    'info',     'P2',
     '未分类；人工录入或新规则过渡', 999, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = EXCLUDED.enabled;

-- 3) 兼容：旧码作为别名说明（不删，仅标注映射）
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→product_stock_low〕' || COALESCE(description, '')
WHERE code = 'stock_low';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→product_overstock〕' || COALESCE(description, '')
WHERE code = 'stock_high';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→product_sales_drop〕' || COALESCE(description, '')
WHERE code = 'sales_drop';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→product_zero_sales〕' || COALESCE(description, '')
WHERE code = 'zero_sales';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→ads_roi_low〕' || COALESCE(description, '')
WHERE code = 'roi_low';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→ads_spend_no_sale〕' || COALESCE(description, '')
WHERE code = 'ads_waste';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→shop_neg_feedback〕' || COALESCE(description, '')
WHERE code = 'review_risk';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→shop_health_low〕' || COALESCE(description, '')
WHERE code = 'health_risk';
UPDATE tk.dim_tk_anomaly_type SET description = '〔别名→product_price_anomaly〕' || COALESCE(description, '')
WHERE code = 'price_anomaly';

COMMENT ON TABLE tk.dim_tk_anomaly_type IS
    'TK 异常类型字典（011 针对化：广告/商品/店经营/健康/财务）；name_cn=飞书异常类型选项';
