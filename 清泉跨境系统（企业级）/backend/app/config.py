from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → 仓库根 .env（与 docker-compose / 启动脚本一致）
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"
_ENV_FILES = tuple(
    str(p) for p in (_ROOT_ENV, _LOCAL_ENV, Path(".env")) if p.is_file()
) or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    app_name: str = "清泉跨境系统"
    app_secret_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://qingquan:qingquan@127.0.0.1:5432/qingquan"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_expire_minutes: int = 1440
    ingest_default_api_key: str = "dev-ingest-key"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    feishu_bitable_table_tasks: str = ""
    # AMZ 驾驶舱多维表（同一 Base 下三张表；可与 tasks 分 Base）
    feishu_bitable_app_token_amz: str = ""
    feishu_bitable_table_amz_shop_daily: str = ""
    feishu_bitable_table_amz_link_daily: str = ""
    feishu_bitable_table_amz_risk: str = ""
    # TK 驾驶舱（模块 2 多店对比 / 模块 3 广告 / 异常任务；空 token 回退 FEISHU_BITABLE_APP_TOKEN）
    feishu_bitable_app_token_tk: str = ""
    feishu_bitable_table_tk_shop_daily: str = ""
    feishu_bitable_table_tk_ads_campaign: str = ""
    feishu_bitable_table_tk_anomaly_task: str = ""
    # T6 内容日（P2.4 · fact_tiktok_content_daily）
    feishu_bitable_table_tk_content_daily: str = ""
    # T7 达人日（P3.2 · fact_tiktok_affiliate_creator_daily）
    feishu_bitable_table_tk_affiliate_creator_daily: str = ""
    # 店铺体验分日（fact_tiktok_experience_daily → TK Base 新表）
    feishu_bitable_table_tk_experience_daily: str = ""
    # 分店铺表映射 JSON（相对仓库根或绝对路径）；由 scripts/feishu-tk-create-store-tables.py 生成
    # 有则同步时除总表外再按店写入对应 table_id
    feishu_tk_store_tables_json: str = "config/feishu-tk-store-tables.json"
    # 企业应用 IM 私信（宋敏等）；与群 webhook 双通道
    feishu_im_receive_id: str = ""
    feishu_im_user_id_songmin: str = ""  # 别名，优先 feishu_im_receive_id
    feishu_im_receive_id_type: str = "open_id"  # open_id | user_id | union_id
    tk_notify_webhook: bool = True
    tk_notify_im: bool = True
    default_task_due_days: int = 3
    tz: str = "Asia/Shanghai"
    # TK 广告异常规则（ads_roi_low / ads_spend_no_sale / budget_burn / cpa_high）
    tk_ads_min_spend: float = 1.0
    tk_ads_global_min_roi: float = 3.0
    # 有 target_roi 时：roi < target_roi * ratio 即命中（默认 1.0=未达目标）
    tk_ads_roi_target_ratio: float = 1.0
    # 相对目标过近时不报警的缓冲（绝对 ROI 差值）；0=不缓冲
    tk_ads_roi_target_slack: float = 0.0
    # 预算消耗率：spend/daily_budget >= ratio 即「预算将尽」（默认 80%）
    tk_ads_budget_burn_ratio: float = 0.8
    # 日预算低于此值不评预算将尽（避免 0/空预算误报）
    tk_ads_budget_min: float = 1.0
    # CPA 绝对阈值（币种随行；默认 15）
    tk_ads_max_cpa: float = 15.0
    # CPA / 客单(AOV) 占比阈值；0=关闭相对判定
    tk_ads_cpa_aov_ratio: float = 0.4
    # 广告 Ingest 成功后自动跑规则（批末触发；可用环境变量关掉）
    tk_ads_auto_eval_on_ingest: bool = True
    # TK 商品库存规则
    tk_product_stockout_qty: float = 0.0
    tk_product_stock_low_qty: float = 10.0
    tk_product_auto_eval_on_ingest: bool = True
    # TK 店铺分析规则（① 店日 GMV/订单环比）
    # 下降比例阈值：0.3 = 环比跌 ≥30% 出单
    tk_shop_gmv_drop_ratio: float = 0.3
    tk_shop_order_drop_ratio: float = 0.3
    # 前日基线过低不评（避免小基数误报）
    tk_shop_min_gmv_base: float = 50.0
    tk_shop_min_orders_base: float = 3.0
    # 跌幅 ≥ 此值提 P0（默认 50%）
    tk_shop_p0_drop_ratio: float = 0.5
    # TK 视频内容规则（② 窗口快照环比 / 有曝无单）
    tk_content_gmv_drop_ratio: float = 0.3
    tk_content_play_drop_ratio: float = 0.3
    tk_content_min_gmv_base: float = 5.0
    tk_content_min_play_base: float = 50.0
    # 曝光或播放 ≥ 此值且归因 GMV/订单均为 0 → content_imp_no_order
    tk_content_min_impressions_no_order: float = 200.0
    tk_content_p0_drop_ratio: float = 0.5
    tk_content_auto_eval_on_ingest: bool = True
    # TK 达人表现规则（③ 联盟窗口快照环比 / 有投入无成交）
    # 投入仅 est_commission；投流/寄样金额暂不采，禁止当 0
    tk_affiliate_gmv_drop_ratio: float = 0.3
    tk_affiliate_min_gmv_base: float = 5.0
    tk_affiliate_min_commission_invest: float = 1.0
    tk_affiliate_refund_ratio: float = 0.5
    tk_affiliate_min_gmv_for_refund: float = 10.0
    tk_affiliate_creators_sold_drop_ratio: float = 0.3
    tk_affiliate_min_creators_sold_base: float = 3.0
    tk_affiliate_p0_drop_ratio: float = 0.5
    tk_affiliate_auto_eval_on_ingest: bool = True
    # TK 账号健康分（fact_tiktok_health_daily）
    # 任意下降即提醒；≤ 红线再出一条「健康分低」
    tk_health_low_threshold: float = 150.0
    tk_health_auto_eval_on_ingest: bool = True
    tk_health_notify_feishu: bool = True
    # 飞书自定义群机器人 webhook（店铺健康/违规/差评提醒；空则只落异常不推群）
    feishu_bot_webhook_tk_health: str = ""
    # 违规扣分：新入库即提醒（first_seen 窗口，小时）
    tk_violation_auto_eval_on_ingest: bool = True
    tk_violation_new_within_hours: float = 48.0
    # 差评：rating ≤ 阈值视为差评；新入库即提醒
    tk_review_auto_eval_on_ingest: bool = True
    tk_review_bad_max_rating: float = 2.0
    tk_review_new_within_hours: float = 72.0
    # 仅未回复差评提醒（默认开）
    tk_review_only_unreplied: bool = True
    # 体验分 / 达人健康
    tk_experience_auto_eval_on_ingest: bool = True
    tk_creator_health_auto_eval_on_ingest: bool = True
    tk_creator_violation_new_within_hours: float = 48.0
    # 自动规则是否投影 public.task（ingest 批末默认开）
    tk_rules_project_center_task: bool = True
    # 赛狐 OpenAPI（TK 利润/商品只读同步；与发货 bridge 共用 App，勿把 TK 店写入发货白名单）
    sellfox_base_url: str = "https://openapi.sellfox.com"
    sellfox_client_id: str = ""
    sellfox_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
