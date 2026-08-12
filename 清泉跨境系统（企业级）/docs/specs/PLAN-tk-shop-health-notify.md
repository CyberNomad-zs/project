# PLAN: TK 店铺健康/体验/达人 飞书双通道提醒与体验分进表

| 字段 | 值 |
|------|-----|
| Spec | `docs/specs/SPEC-tk-shop-health-notify.md`（approved） |
| MVP | `docs/specs/MVP-tk-shop-health-notify.md`（approved） |
| ARCH | `docs/specs/ARCHITECTURE-tk-shop-health-notify.md`（approved） |
| ACCEPTANCE | `docs/specs/ACCEPTANCE-tk-shop-health-notify.md` |
| 状态 | approved |
| mode | feature |
| 作者 | Grok |
| 日期 | 2026-08-11 |
| 批准人 | 用户 |
| 批准日期 | 2026-08-11 |

---

## Objective

在已批 ARCH 边界内落地 MVP **M1–M5**：体验分（三模块）采集→PG→TK Base 新表；达人健康多账号+新违规；飞书 IM 私信 + 群双通道；现网健康/差评等告警改走 dual；全 stores.config 店日更可跑且单店失败隔离。

## Mode

`feature`（增量；复用 ingest / anomaly / bitable / shop-modules 模式）

## 引用

- SPEC-20260811-tk-shop-health-notify  
- MVP Ship-now M1–M5  
- ARCH D1–D6  

---

## 文件列表

| 动作 | 路径 | ARCH 模块 | 说明 |
|------|------|-----------|------|
| 新增 | `backend/migrations/024_tk_experience_creator_health.sql` | 存储 | experience_daily / creator_health_daily / creator_violation + anomaly 种子码 |
| 新增 | `backend/app/adapters/feishu/im.py` | feishu IM | tenant_token + 私信文本；无 user 则 skip |
| 改 | `backend/app/adapters/feishu/__init__.py` | feishu | 导出 im 如需 |
| 新增 | `backend/app/domain/notify_dual.py` | notify_dual | webhook + IM 统一出口；开关；失败隔离 |
| 改 | `backend/app/adapters/feishu/bot.py` | bot | 仅在需要时小改（保持 send_webhook_post 稳定） |
| 改 | `backend/app/config.py` | 配置 | IM user/开关、experience table_id、可选 notify flags |
| 改 | `.env.example` | 配置 | 文档化新键（无密文） |
| 改 | `backend/app/domain/tk_health_rules.py` | health rules | 通知改 `notify_dual` |
| 改 | `backend/app/domain/tk_review_rules.py` | review rules | 同上 |
| 改 | `backend/app/domain/tk_violation_rules.py` | violation rules | 店违规 dual；不与达人表混用 |
| 新增 | `backend/app/domain/tk_experience_rules.py` | experience rules | 总分/分项变差；指标方向表 |
| 新增 | `backend/app/domain/tk_creator_health_rules.py` | creator rules | 下降 + 新违规 |
| 改 | `backend/app/domain/tk_anomaly.py` | anomaly | 如需 object_type=`creator` 支持（已有则只接线） |
| 改 | `backend/app/api/ingest.py` | ingest | source：`tiktok_experience_daily` / `tiktok_creator_health_daily` / `tiktok_creator_violation`；auto_eval 挂钩 |
| 新增 | `backend/app/jobs/tk_experience_anomaly_eval.py` | jobs | CLI 评估体验分 |
| 新增 | `backend/app/jobs/tk_creator_health_anomaly_eval.py` | jobs | CLI 评估达人健康/违规 |
| 改 | `backend/app/jobs/tk_health_anomaly_eval.py` | jobs | 随 rules 通知路径（若仅 domain 改可不动） |
| 改 | `backend/app/jobs/tk_feishu_sync.py` | feishu sync | channel `tk_experience_daily` |
| 改 | `backend/app/adapters/feishu/bitable.py` | bitable | `experience_daily_to_fields` mapper |
| 新增 | `collectors/tiktok-ads/scripts/scrape-experience-daily-page.js` | 采集 | 体验分总分+三模块+子指标 |
| 新增 | `collectors/tiktok-ads/scripts/scrape-creator-health-page.js` | 采集 | 单账号健康分+违规列表 |
| 改 | `collectors/tiktok-ads/scripts/run-shop-modules.ps1` | 调度 | 模块 experience_daily、creator_health；失败隔离 |
| 改 | `collectors/tiktok-ads/scripts/run-shop-modules-daily.ps1` | 调度 | 默认 Modules 串加入新模块 |
| 改 | `collectors/tiktok-ads/scripts/qingquan-client.ps1` | 上报 | payload 组装新 source |
| 改 | `collectors/tiktok-ads/config/stores.config.example.json` | 配置 | experienceUrl / creatorHealthUrl 示例 |
| 改 | `collectors/tiktok-ads/config/stores.config.json` | 配置 | 主配置 URL（按 UK/EU 映射，无密钥） |
| 新增 | `scripts/feishu-tk-create-t-experience.py` | 运维 | 在 TK Base 建体验分日表并打印 table_id |
| 改 | `docs/ops/SERVER.md` | 文档 | 双通道、新表、模块、env 说明 |
| 新增 | `backend/tests/test_tk_experience_rules.py` | 测试 | 下降/方向方向/边界 |
| 新增 | `backend/tests/test_tk_creator_health_rules.py` | 测试 | 多账号 dedupe/下降 |
| 新增 | `backend/tests/test_notify_dual.py` | 测试 | mock webhook/IM；缺 user 不抛 |
| 改 | `backend/tests/test_tk_health_rules.py` 或新增 | 测试 | dual 接线 smoke（若已有 health 单测则扩） |

**不在列表（Defer / 越界禁止）：** `web/src/*` 新专页、新建飞书 Base、生产 `.env` 密文提交。

---

## 方案（5 条）

1. **存储先行**  
   迁移 `024`：三张新事实表 + anomaly 类型种子（experience_drop / experience_metric_worse / creator_health_drop / creator_violation）。唯一键：店×日；达人：店×creator_key×日。

2. **通知底座**  
   实现 `im.py` + `notify_dual.py`；配置 `FEISHU_IM_RECEIVE_ID`（宋敏）与 `TK_NOTIFY_WEBHOOK`/`TK_NOTIFY_IM`（默认 true）。将 health / review / violation 的飞书发送从「仅 webhook」改为 dual；去重策略保持「未闭环仅恶化再推」。

3. **体验分全链路（M1+M4 分项）**  
   scrape 体验分页 → ingest upsert → `tk_experience_rules` 比上次总分与分项 → 异常 + dual；`tk_feishu_sync` + bitable mapper → `FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY`。建表脚本一键建字段。

4. **达人健康多账号（M2）**  
   PS：打开 creator health URL → JS 列出切换账号 → 逐个切换刮分与近 90 天违规 → 分条 ingest。规则：按 creator_key 比上次分数；违规按业务唯一键 first_seen 判定新增。

5. **调度与验证（M5）**  
   `run-shop-modules` 默认模块串加入 `experience_daily,creator_health`；单店/模块 try 失败 continue。pytest 规则+notify；人工/脚本 1 店冒烟对齐 MVP SC1–SC4。

### 指标「变差」方向（实现写入 experience_rules 常量）

| 指标 | 变差方向 |
|------|----------|
| 体验总分 / 三模块分 | 数值 **下降** |
| 取消率、差评率、不满意率、处理时长 等 | 数值 **上升**（或等级从优秀→需关注） |
| 按时送达率等「越高越好」率 | 数值 **下降** |

（刮不到的子指标不参与规则，仅进 raw/表可选列。）

---

## 非目标

- Web 专页、飞书图表装修  
- 关闭群只留私信（默认双开；可配置）  
- 改「任意下降」为「仅 ≤150 / 仅 ≥0.1」（与已批 Spec 冲突）  
- 生产环境自主写 Secret / 部署（G3）  

---

## 待决决策（实现时默认，无需再开 Spec）

| 项 | 默认 |
|----|------|
| creator_key | 优先页面稳定 id；无则 `slug(昵称|角色|序号)` + raw 存原文 |
| 私信 receive_id_type | `open_id`（env 可改） |
| 体验分业务日 | 采集日 Asia/Shanghai（与 health 一致） |
| 飞书新表字段名 | 中文列：店铺ID/店铺名/业务日/体验总分/商品满意度/履约物流/客户服务/子指标摘要/采集时间 |

---

## 风险与回滚

| 风险 | 回滚 |
|------|------|
| DOM 刮空 | 关模块 env/Modules 列表去掉 experience/creator；不影响广告/订单 |
| 私信刷屏 | `TK_NOTIFY_IM=false` |
| 群刷屏 | webhook 置空或 `TK_NOTIFY_WEBHOOK=false` |
| 坏迁移 | 迁移 down 脚本或手工 drop 新表（仅空环境）；生产须人批 |
| 双通道重复 | 保持 anomaly dedupe + 恶化再推 |

---

## 验证计划（对照 MVP Success / ACCEPTANCE）

| 检查 | 方法 |
|------|------|
| SC1 体验分 PG+飞书 | 1 店跑 experience 模块；SQL 有行；飞书新表有行 |
| SC2 三路通知 | 构造下降样例或 dry-run+mock；实网配齐后查群+宋敏私信+任务表 |
| SC3 达人≥2 | PG `creator_health_daily` 同店两 creator_key |
| SC4 无密钥进仓 | git diff 审 `.env.example` only |
| 单测 | `pytest backend/tests/test_tk_experience_rules.py test_tk_creator_health_rules.py test_notify_dual.py -q` |
| 回归健康 | 现有 health drop/low 行为不变；通知走 dual |

### 建议实施顺序（PR 可拆）

1. `024` 迁移 + notify_dual + im + health/review/violation 接线 + 单测  
2. experience scrape→ingest→rules→feishu 表 + 建表脚本  
3. creator multi-account scrape→ingest→rules  
4. shop-modules 默认串 + SERVER.md + 1 店冒烟记录  

---

## Gate A 自检

- [x] ARCH 已批准  
- [x] 文件列表 ⊆ M1–M5，落在 ARCH 模块  
- [x] 路径具体  
- [x] 无未授权 G3 操作计划  
- [x] 进仓本文件  

---

**批准记录：**

```text
批准人: 用户
日期: 2026-08-11
语句: 批准
```
