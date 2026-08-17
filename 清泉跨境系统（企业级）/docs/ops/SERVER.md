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

### 生产飞书 TK 切清泉组织新 Base（2026-08-12）

- 新 Base `LzTAbQsThaPOzis2lFvciDMlnyh`（清泉组织副本，2026-08-10 建）；旧金猫 `C1iHbw6TVad6rUsbZnbc2gSDnHg` 保留不删
- 生产 `/opt/qingquan/.env`：`FEISHU_APP_ID/SECRET` 切 `cli_aaf3f14a863bdbc3`，`FEISHU_BITABLE_APP_TOKEN(_TK)` 切新 Base，TK 六表 ID 全换（shop `tblrpFX6gWaf7KPX` / ads `tblgLifLVW91v5Bk` / anomaly `tblO1uGlWccuaiZF` / content `tblgFISW9sJzoZzm` / affiliate `tbleJkhx0cTtG3Y6` / experience `tbld6A91n8MQWkS2`）；切换前自动备份 `.env.bak.*`
- 影响面：`get_tenant_access_token` 仅 TK 同步 / AMZ（未配置表，空转）/ worker tasks（空转）/ IM（`TK_NOTIFY_IM=false`）使用；采购/Temu 独立凭据不受影响
- `config/feishu-tk-store-tables.json`（分店表映射，已指向新 Base）scp 到 `/opt/qingquan/config/`；容器无挂载，rebuild 后需 `docker cp` 到 `qingquan-api-1`/`qingquan-worker-1`。**注意**：容器内 `_REPO_ROOT=/`（`parents[3]`），相对路径解析为 `/config/feishu-tk-store-tables.json`（不是 `/app/config/`），文件必须放 `/config/`
- rebuild api/worker 前已校验容器内 py 与宿主机 `/opt/qingquan/backend` 完全一致（md5 全等），rebuild 不丢热修
- 重推：清 `sync_feishu_map` 旧表映射 → `scripts/_prod_exp_resync_new_base.sh`（体验分）+ `scripts/_prod_tk_full_resync_new_base.sh`（T1/T2/异常/T6/T7，lookback 30d）
- 注意：Git Bash ssh 读不了 ed25519 密钥（libcrypto unsupported），须用 `C:\Windows\System32\OpenSSH\ssh.exe`

### TK 异常任务负责人列改版 + TK 路由修复（2026-08-17）

- **负责人列改版**：4 张异常表（总表 `tblO1uGlWccuaiZF` + 分店 Deal `tblExYubQqCwteW3` / Gardena `tblIUs71slVjMroo` / SHOP INOUT `tblUZ58M0DKpZRU7`）的负责人列由 `负责人`+`第一负责人`（双写文本、User 列实为空）改为 `负责人（助理）`+`负责人（运营）`（User, multiple）。全局统一：助理=郭芷杨 `ou_5ad532b7518f5e47dc9a7ce26c41d849`、运营=宋敏 `ou_967f12892b9becbd14ba85c6e3275735`
- `.env` 新增 `FEISHU_TK_OWNER_ASSISTANT_OPENID` / `FEISHU_TK_OWNER_OPERATOR_OPENID`；`config.py` 加对应字段；`bitable.py` `tk_anomaly_task_to_fields` 改为读 settings 写 `[{"id":openid}]`（空则不提供字段，保留人工指派）
- 旧 User 列在 4 表已删（main/deal/gardena 各 2 个，inout 原无 User 列）；新列 field_id：main `fldQ8RNjq8`/`fldBqZST2L`、deal `flduxEnaOP`/`fldQODLuLJ`、gardena `fldm4TfBBZ`/`fldavyuRfS`、inout `fldbuhKySi`/`fldKktrytx`
- 回填：PG-driven `--anomaly-only` 只覆盖 PG 内 72 行；飞书分店表另有 53 条 PG 已删的孤儿记录，用 `scripts/_backfill_anomaly_owners_direct.py` 按 record_id 直补，4 表共 195 条全部填上两人
- **store-tables external_ids 缺失修复**：服务器宿主机 `config/feishu-tk-store-tables.json` 曾是旧版（缺 `external_ids`），导致分店 fan-out 靠 shop_name 匹配，而 anomaly 行 shop_name 漂移（同 ID 多名），fan-out 失效。已把 dev 新版（含 external_ids）scp 到 `/opt/qingquan/config/` + `docker cp` 到两容器 `/config/`。fan-out 现按 `shop_external_id` 归属：27501502216807→deal、27758103898326→gardena、27328767468273→shop-inout
- **TK HTTP 路由修复（独立旧问题，非本次引入）**：服务器宿主机 `main.py` 曾是旧版，未 import/include `tk_ops`/`tk_anomaly_tasks`，rebuild 后 OpenAPI 缺 `/api/v1/tk/*`（17 路由全丢，任务台 TK 页 404）。已就地 patch main.py 加 `tk_anomaly_tasks`/`tk_ops` 两行 import + 两行 `include_router`（保留原有 amazon_sync/procurement），同时 scp dev 新版 `tk_ops.py`（宿主机旧版 md5 5a72a2… → dev 58def5…），rebuild 后 tk 路由恢复 17 个、总 path 37
- 注意：dev 仓库 `main.py` 与服务器版互缺（dev 缺 amazon_sync/procurement、服务器曾缺 tk）——分叉待统一
- 仪表盘 D5 异常任务台若绑旧 `负责人`/`第一负责人` 列，需在飞书 UI 重绑到新两列（组件无写 API，人工）

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
- 通知：`notify_dual` = 群 webhook（`FEISHU_BOT_WEBHOOK_TK_HEALTH`）为主；IM 私信可选（`TK_NOTIFY_IM`，**2026-08-11 起默认 false，只群发**）

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
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_product_anomaly_eval
# 仅统计：加 --dry-run；不推群：加 --no-notify
```

- 商品断货/库存通知（2026-08-17 新增）：`tk_product_rules.evaluate_product_anomalies` 接 `notify_dual`，通知 lines 含 `商品ID：{product_id}`（负责人用此 ID 去后台定位商品）+ 库存/阈值/链接；去重照 violation/review 同款（`_open_exists` 未闭环同键已存在则不重复推）。ingest 批末自动评估已传 `notify`。稳态下历史断货任务不重复推，仅新断货触发。

- `.env`：`FEISHU_BOT_WEBHOOK_TK_HEALTH` / `TK_HEALTH_*` / `TK_VIOLATION_*` / `TK_REVIEW_*`
- 批末自动评估：ingest 成功后 `_maybe_auto_eval_after_ingest`
- 热修注意：`docker compose up --force-recreate api` 后需再 `docker cp` 相关 py（镜像未 rebuild 时）
- 迁移：`psql … -f backend/migrations/020_tk_violation_review.sql`

### TK产品表 赛狐→PG→飞书同步（2026-08-17）

- 表：飞书 TK产品表 `tbl69GJ8cAAhizmj`（28 列；13 列为 Formula 飞书自算，6 可写列由本 job 灌，9 列手填）
- 数据链：赛狐 OpenAPI → `tk_sellfox_sync`（刷新 PG）→ 本 job（PG → 飞书）
- 灌入 6 列：货源 / 品名 / SKUID / 上架状态 / 售价（含VAT）（平台活动价） / 采购 GBP
- **不灌**：13 Formula 列（API 写不进，飞书自算）、采购CNY/头程CNY/亚马逊售价/黑猫RM/服务费/操作费/配送费（手填）、SKU（与 SKUID 重复）
- 采购 GBP 口径：profit_sku `raw_extra.purchaseFee` 取 `abs()`（赛狐利润扣除口径为负 → 飞书列正数）
- 关联：拆 `seller_sku` 的 `|` 多规格，join `fact_sellfox_tk_profit_sku` ON `sku_key = seller_sku_part`，取 `period_end` 最大一期
- 在售过滤：`fact_tiktok_product.status ∈ (在售/active/在线)`
- 覆盖策略：`--full`（首次全量：覆盖已有行 6 列 + 新建缺行） / 默认（只新增：已有行不动）
- 缺数据：赛狐无 profit_sku 的在售 SKU → 推 `FEISHU_BOT_WEBHOOK_TK_HEALTH`（仅 SKU 列表，**无金额**），webhook 空只落日志
- 运行记录：写 `tk.sellfox_sync_run`（modules=`["product_feishu"]`）

**前置**：先确保 PG 有赛狐数据

```bash
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_sellfox_sync --days 1
```

**触发**（手动，无 cron）：

```bash
# 预览（不实写，打印将 create/update 的行）
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_sellfox_product_feishu_sync --dry-run

# 首次全量（覆盖已有行 6 可写列 + 新建缺行）
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_sellfox_product_feishu_sync --full

# 只新增（已有行不动；幂等重跑用）
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_sellfox_product_feishu_sync
```

- `.env`：`FEISHU_BITABLE_TABLE_TK_PRODUCT=tbl69GJ8cAAhizmj` / `FEISHU_BITABLE_APP_TOKEN_TK` / `FEISHU_BOT_WEBHOOK_TK_HEALTH`
- 首跑建议：`--dry-run` 预览 → `--full` 全量 → 抽检飞书 3 行（6 可写列有赛狐值、13 公式列已重算、手填列保留）→ 再跑无 `--full` 确认幂等
- 单测：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tk_sellfox_product_feishu_sync.py -v`
- 部署：改代码需 rebuild api/worker 镜像（代码内嵌）；`.env` 加 `FEISHU_BITABLE_TABLE_TK_PRODUCT` 后 `docker cp` 或重启容器生效
- Spec 链：`docs/specs/SPEC-20260817-tk-sellfox-product-sync.md`（含 ARCH/EXPLORE/PLAN/FINDINGS/ACCEPTANCE）
