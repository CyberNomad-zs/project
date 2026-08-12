# TK 健康 / 体验分 / 达人 · 上线检查单

> 对应 SPEC/MVP/PLAN：`docs/specs/*-tk-shop-health-notify.md`  
> 日期：2026-08-11

## 1. 数据库

- [x] 已 apply `backend/migrations/024_tk_experience_creator_health.sql`（生产 2026-08-11；severity 须用 high 非 medium）
- [x] 存在表：`tk.fact_tiktok_experience_daily`、`tk.fact_tiktok_creator_health_daily`、`tk.fact_tiktok_creator_violation`
- [x] `tk.dim_tk_anomaly_type` 含：`shop_experience_drop`、`shop_experience_metric_worse`、`creator_health_drop`、`creator_violation`
- [ ] **本机 PG**：未跑（本机 5432 拒绝连接 / Docker Desktop 未起）

```bash
# 生产示例
docker cp backend/migrations/024_tk_experience_creator_health.sql qingquan-db-1:/tmp/024.sql
docker exec qingquan-db-1 psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -f /tmp/024.sql
```

## 2. 环境变量（生产 `.env`，勿提交 git）

- [x] `FEISHU_APP_ID` / `FEISHU_APP_SECRET`（已 SET）
- [ ] `FEISHU_IM_RECEIVE_ID` = 宋敏 open_id（**仍 EMPTY** → 私信通道未通）
- [x] `FEISHU_BOT_WEBHOOK_TK_HEALTH` 已 SET（群通道可用）
- [x] `TK_NOTIFY_WEBHOOK=true`、`TK_NOTIFY_IM=true` 已追加
- [x] `FEISHU_BITABLE_APP_TOKEN_TK` 已有
- [x] `FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=tbl9CYd8vb4DJaGN`（生产 Base 建表；勿用本机 Base 的 tblSyTlj…）

```bash
# 本机有 FEISHU_* 时建体验分日表
backend/.venv/Scripts/python.exe scripts/feishu-tk-create-t-experience.py
```

## 3. 发版

- [x] 核心 py **热更 docker cp** 进 api/worker + restart（非完整 image rebuild；持久化以 `/opt/qingquan/backend` 为准）
- [ ] 采集机更新 `collectors/tiktok-ads/scripts/*` 与 config URL（experienceUrl / creatorHealthUrl）— **本机紫鸟日更未跑**
- [x] 日更脚本默认 Modules 已含 experience/creator（代码侧）；任务计划是否已装待确认

## 4. 冒烟

- [ ] 单店真实紫鸟采集（依赖采集机 + 紫鸟登录）— **未执行**
- [x] PG 样例行：`smoke-shop-exp` 体验分 2 日 + 达人 Grace/Emma
- [ ] 单店 creator multi-account 日志 — **未执行**
- [x] dry-run 体验分：scanned=1 hit_drop=1 hit_metric=1 will_notify
- [x] dry-run 达人：scanned=2 hit_drop=1（Grace 200→170）will_notify
- [ ] 实发群/私信：群可开；**私信缺 FEISHU_IM_RECEIVE_ID**
- [x] 飞书「体验分日」sync：`scanned=2 created=2 failed=0`（table `tbl9CYd8vb4DJaGN`）

### 冒烟记录（2026-08-11）

| 项 | 结果 |
|----|------|
| 生产 health | ok |
| 迁移 024 | 三表 + 4 anomaly 码 OK（metric severity 改为 high） |
| 热更 api/worker | IMPORT_OK；experience_table True |
| 规则 dry-run 样例 | 体验分下降+分项；达人 Grace 下降 |
| 飞书 sync | success created=2 |
| 私信 | **缺 FEISHU_IM_RECEIVE_ID** |
| 本机 PG / 紫鸟采集 | 未跑 |
| 完整 image rebuild | 未做（热更；下次正式发版建议 rebuild） |

## 5. 回滚

- [ ] 日更 Modules 去掉 `experience_daily,creator_health`
- [ ] `TK_NOTIFY_IM=false` 停私信；webhook 置空停群
- [ ] 新表可保留；规则评估关：`TK_EXPERIENCE_AUTO_EVAL_ON_INGEST=false` 等
