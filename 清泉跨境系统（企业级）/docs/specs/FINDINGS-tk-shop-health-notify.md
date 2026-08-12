# Findings — TK 店铺健康/体验/达人 飞书双通道（Gate B）

| 字段 | 值 |
|------|-----|
| Plan | `docs/specs/PLAN-tk-shop-health-notify.md`（**已批准**） |
| ARCH | approved |
| 状态 | approved |
| 日期 | 2026-08-11 |
| 批准 | 用户 2026-08-11「批准」 |

---

## 探查范围

已读路径/模块：

- `backend/app/domain/tk_health_rules.py`（任意下降 + ≤150；webhook 直发）
- `backend/app/domain/tk_review_rules.py`、`tk_violation_rules.py`（存在；店级违规表 020）
- `backend/app/adapters/feishu/bot.py`（仅 webhook，**无 IM**）
- `backend/app/adapters/feishu/bitable.py`、`jobs/tk_feishu_sync.py`（T1 左连 health；扩表模式成熟）
- `backend/app/api/ingest.py`（`tiktok_health_daily` 分支与 auto_eval 挂钩模式）
- `backend/app/config.py`（`feishu_bot_webhook_tk_health`、`tk_health_*`）
- `backend/migrations/007_*`、`020_tk_violation_review.sql`（health / violation / review 表）
- `collectors/tiktok-ads/scripts/run-shop-modules.ps1`、`scrape-health-daily-page.js`、`scrape-violation-page.js`、`scrape-product-reviews-page.js`
- 迁移序号：最高已见 **023** → Plan 的 **024** 序号可用

---

## 当前状态（事实）

1. 健康分：fact + 规则 + CLI + ingest auto 路径**已通**；通知**仅群 webhook**。  
2. 差评/店违规：020 表 + rules + jobs **已通**；通知同样偏 webhook。  
3. **无** `experience` / `creator_health` 事实表、scrape、ingest source。  
4. **无** `adapters/feishu/im.py`；企业应用私信需新建。  
5. 飞书 bitable 同步可复制 `tk_feishu_sync` channel 模式加新表。  
6. 店违规 `fact_tiktok_violation` 无 creator 维度 → Plan 新建 `creator_violation` **合理**，不硬塞店表。  
7. `feishu` 适配器目录仅 `bot.py` + `bitable.py`，与 Plan 增量一致。

---

## 意外发现

| 项 | 说明 | 对 Plan |
|----|------|---------|
| 迁移编号空洞 | 有 018–020、022–023，**无 021/017** 文件 | 仍用 **024**，无冲突 |
| health 通知写死 webhook | `tk_health_rules._notify_feishu` 直调 bot | Plan 改 dual **必要**，非可选优化 |
| 店违规 vs 达人违规页 | 店用 health-center 违规 tab；达人在「达人健康评分」 | 分采集脚本/分表，Plan 已覆盖 |
| 体验分 URL | 截图为 `.../health-center/experience-score?shop_region=GB` | config 增 `experienceUrl`；EU/UK 映射与 health 同模式 |

**无**「未文档化会阻断编码的隐藏单例」；**无**与已批 Spec「任意变差 / 双通道 / 全店」冲突。

---

## 对原 Plan 的影响

- [x] **无影响，按原 Plan 执行**
- [ ] 需修订 Plan
- [ ] 需打回 L1

### 修订后的 Plan

（无）

### 实施时小提示（不改 Plan 范围）

- dual 改造优先抽 `_notify_feishu` 三处（health/review/violation）为 `notify_dual`，避免漏接。  
- creator 切换依赖 ziniao page 点击；失败策略已在 ARCH/Plan（账号级隔离）。  

---

## 风险增量

| 风险 | 相对 Plan | 处置 |
|------|-----------|------|
| IM 应用权限未开 | 已标 | 私信 skip + 日志；不阻采集 |
| 达人切换不稳定 | 已标 | 超时 skip 单账号 |
| 无新增 | — | — |

---

## Gate B 自检

- [x] 基于实读  
- [x] 不扩大 Ship-now  
- [x] 不推翻 Spec  
- [x] 可按原 Plan 开工  

---

**批准记录：**

```text
批准人: 用户
日期: 2026-08-11
语句: 批准
```
