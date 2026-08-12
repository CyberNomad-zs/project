# 清泉服务器（2C4G）

| 项 | 值 |
|---|---|
| SSH | `ssh qingquan-sg` |
| IP | `43.156.50.38` |
| 用户 | `ubuntu` |
| 规格 | 2 核 / 4G · Ubuntu 24.04 · 腾讯云轻量新加坡 |
| 密钥 | 仓库 `keys/qingquan_sg_ed25519`（密码登录已关闭） |
| 代码目录 | `/opt/qingquan` |
| Compose | `/opt/qingquan/deploy/docker-compose.prod.yml` · project `qingquan` |

```bash
ssh -i keys/qingquan_sg_ed25519 ubuntu@43.156.50.38
# 或本机已配别名：
ssh qingquan-sg
```

## 热修 / 发版（api 镜像内嵌代码）

api/worker **不挂载** `backend/app`，改代码后必须：

1. `scp` 到 `/opt/qingquan/backend/...`（或 `deploy/deploy.sh` 全量 rsync）
2. 有新迁移先 `docker cp` + `psql -f`（见下）
3. 在服务器：

```bash
set -a; . /opt/qingquan/.env; set +a
cd /opt/qingquan/deploy
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env build api worker
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
curl -sS http://127.0.0.1:8000/health
```

仅 recreate **不会**带上宿主机新文件；`main.py` 漏注册路由时 OpenAPI 会缺 `/api/v1/tk/*`。

### P2 收口热修记录（2026-08-05）

- 同步：`tk_ops`（含 `/tk/content/anomaly-eval`）、`tk_anomaly`（AMZ 人维列）、`tk_*_rules`、`tk_feishu_sync`/`bitable`、`015_tk_anomaly_amz_ops_fields.sql`、`web/src/App.vue`
- 迁移：生产已 apply **015**（`level_code` / `description` / `current_value` / `needs_boss_decision`…）
- 前端：服务器 `web/` 下 `npm ci && npm run build`，dist 含 **内容分析** `tk-content`
- `.env`：删除脏行 `nFEISHU_BITABLE_TABLE_TK_CONTENT_DAILY`；保留 `FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY`
- 验收：OpenAPI 含 content / content anomaly-eval / product-traffic；未鉴权 401；health ok

### 商品卡 traffic 指标回填（2026-08-05）

英文站表头 `View-to-paid rate` / `Viewers` 曾未映射 → 行上只有 GMV。修复：

1. 采集 `scrape-product-traffic-page.js` 英文表头 + 单元格形态回填  
2. ingest `_enrich_traffic_from_raw_cells`（新上报与幂等刷新）  
3. 存量：`python scripts/tk_backfill_product_traffic_metrics.py`（容器内 `PYTHONPATH=/app`）  
4. 日更门禁：`python scripts/tk_daily_quality_check.py`（已挂 `tk-p0-post-collect.ps1` 末尾）

生产回填后：`product_traffic` 各锚点日 `null_imp=0 null_cvr=0`；quality **OK**。

### 任务台人维 + 新鲜度（2026-08-05）

- `GET /api/v1/tk/shop-daily` 增加 `freshness`：`shop_daily_max` / `ads_max` / `content_max` / `traffic_max` / `stale[]` / `boss_decision_count`（阈值对齐 `tk_daily_quality_check.py`）
- 任务台：总览新鲜度条；异常表列 **等级 / 待老板决策 / 当前值·对比值 / 说明**
- 飞书异常表：`feishu-tk-upgrade-anomaly-amz-style.py` 列已齐（skip）；`feishu-tk-daily-sync.ps1 -AnomalyOnly` → created=4 updated=30 failed=0
- 生产：scp `tk_ops.py` + `web/src` → rebuild api/worker + `npm run build`；冒烟 `SHOP_DAILY_SMOKE_OK` / `ANOMALY_SMOKE_OK` / dist 含 `数据新鲜度` `待老板决策`

## 迁移（已有库）

```bash
docker cp backend/migrations/010_xxx.sql qingquan-db-1:/tmp/
docker exec qingquan-db-1 psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -f /tmp/010_xxx.sql
```

## 生产飞书 TK 同步（容器内）

```bash
# 需 .env 含 T1/T2/异常/T6 table id（T6=FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY）
docker cp /opt/qingquan/scripts/feishu_tk_daily_sync.py qingquan-api-1:/tmp/feishu_tk_daily_sync.py
# 若 api 镜像未 rebuild，同步前 docker cp 最新 tk_feishu_sync.py / bitable.py / config.py
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python /tmp/feishu_tk_daily_sync.py --lookback-days 14
# 仅内容日：
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python /tmp/feishu_tk_daily_sync.py --content-only --lookback-days 30
# 仅达人日 T7：
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python /tmp/feishu_tk_daily_sync.py --affiliate-only --lookback-days 30
```

一键建 T6（本机有 FEISHU_*）：`python scripts/feishu-tk-create-t6-content.py`  
一键建 T7：`python scripts/feishu-tk-create-t7-affiliate.py` → 写入 `FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY`

### P3.2 达人表现热修（2026-08-06）

- 飞书 T7「达人日」：`tblsoAKtF05YyyWd`
- 代码：`tk_ops`（`/tk/affiliate` + shop-daily + freshness.affiliate_max）、`bitable` mapper、`tk_feishu_sync`、`config`、`feishu_tk_daily_sync --affiliate-only`、任务台 `tk-affiliate`
- 生产：host `.env` 已写 T7；docker cp + recreate api/worker 后再 cp；`web/dist` 已替换
- 验收：OpenAPI 含 affiliate；`--affiliate-only` scanned=20 created=20 failed=0；health ok

### P3.3 达人表现规则热修（2026-08-07）

- 迁移：`023_tk_affiliate_anomaly.sql`（object_type +`creator`；dim 四码）
- 代码：`tk_affiliate_rules.py`、`jobs/tk_affiliate_anomaly_eval.py`、`tk_ops` `/affiliate/anomaly-eval`、`ingest` 批末 auto-eval、`tk_anomaly.OBJECT_TYPES`、`config` 阈值、`web` 筛+按钮
- 生产 apply 023 + docker cp api/worker 相关 py + 重建 `web/dist` 替换
- 手动 dry-run：
  ```bash
  docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
    python -m app.jobs.tk_affiliate_anomaly_eval --dry-run
  ```
- 验收：OpenAPI 含 `/api/v1/tk/affiliate/anomaly-eval`；单元测试 `test_tk_affiliate_rules` 7 passed；投入仅预计佣金

### P3.4 / P3.5（2026-08-07）

- 文档：`docs/TK-P3-分盘与口径.md`（SoT；禁混加）
- 前端：`drillToTkAffiliate` / `drillToTkCreatorTasks` / `drillFromTkTaskToAffiliate`；总览店日、平台店铺、店级联盟、达人行、异常行互跳
- 热修：仅需替换 `web/dist`（无后端变更）

## TK 店铺健康 / 违规 / 差评 群提醒（飞书机器人）

共用 webhook：`FEISHU_BOT_WEBHOOK_TK_HEALTH`（自定义群机器人；空则只落 `tk.fact_tk_anomaly_task` 不推群）。

### 健康分

- 规则：`shop_health_drop`（较上次快照**任意下降**）+ `shop_health_low`（`≤ TK_HEALTH_LOW_THRESHOLD`，默认 150）
- 数据：`tk.fact_tiktok_health_daily`（采集 `run-shop-modules*.ps1` → ingest `tiktok_health_daily`）
- 去重：未闭环同码只刷新；**分数继续恶化**才再推
- 通知：**双通道** `notify_dual` = 群 webhook（`FEISHU_BOT_WEBHOOK_TK_HEALTH`）+ 企业应用 IM 私信（`FEISHU_IM_RECEIVE_ID`）

### 店铺体验分（2026-08-11）

- 表：`tk.fact_tiktok_experience_daily`（迁移 **024**）
- 采集：`experience_daily` 模块 → `scrape-experience-daily-page.js` → source `tiktok_experience_daily`
- 规则：`shop_experience_drop` / `shop_experience_metric_worse`（任意变差）
- 飞书：TK Base 表 `FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY`（`scripts/feishu-tk-create-t-experience.py`）
- 同步：`tk_feishu_sync` channel `tk_experience_daily`

### 达人健康多账号

- 表：`tk.fact_tiktok_creator_health_daily` + `tk.fact_tiktok_creator_violation`
- 采集：`creator_health` 模块  
  1. `scrape-creator-health-page.js` 打开切换面板 → 列账号  
  2. 对每个账号 `scrape-creator-health-switch.js`（替换 `__CREATOR_TARGET__`）点击切换 → 刮分/违规  
  3. `qingquan-client` 分条 ingest（每达人 health + 其违规）  
- 上限：`options.creatorHealthMaxAccounts`（默认 12）  
- 规则：`creator_health_drop` / `creator_violation`

### 违规扣分

- 规则：`shop_violation` — `tk.fact_tiktok_violation` 中 `first_seen_at` 落在窗口内（默认 48h）即提醒
- 采集：`run-shop-modules.ps1 -Modules violation`（`scrape-violation-page.js`，URL=`violationUrl`/`health-center`）
- ingest source：`tiktok_violation`；迁移 **020**
- 通知：同上双通道

### 差评处理

- 规则：`shop_bad_review` — rating ≤ `TK_REVIEW_BAD_MAX_RATING`（默认 2），默认仅未回复，窗口 72h
- 采集：`run-shop-modules.ps1 -Modules reviews`（`scrape-product-reviews-page.js`，URL=`productReviewsUrl`）
- ingest source：`tiktok_review`
- 通知：同上双通道

### 手动评估

```bash
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_health_anomaly_eval
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_violation_anomaly_eval
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_review_anomaly_eval
# 仅统计：加 --dry-run；不推群：加 --no-notify
```

- `.env`：`FEISHU_BOT_WEBHOOK_TK_HEALTH` / `TK_HEALTH_*` / `TK_VIOLATION_*` / `TK_REVIEW_*`
- 批末自动评估：ingest 成功后 `_maybe_auto_eval_after_ingest`
- 热修注意：`docker compose up --force-recreate api` 后需再 `docker cp` 相关 py（镜像未 rebuild 时）
- 迁移：`psql … -f backend/migrations/020_tk_violation_review.sql`
