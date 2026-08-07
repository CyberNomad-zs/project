# 差距盘点：归档 Work OS Spec vs 现有实现

| 字段 | 值 |
|------|-----|
| 日期 | 2026-07-28 |
| 对照制品 | `docs/specs/SPEC-qingquan-work-os.md`、`MVP-qingquan-work-os.md`、`ACCEPTANCE-qingquan-work-os.md` |
| 代码基线 | `backend/` + `web/` + `collectors/`（Phase 0 中心基座 + AMZ 环比样板） |
| 结论摘要 | **基座有、Work OS 主线未落地**。现有 `task` 模型是「异常任务跟踪」雏形，距 Spec 的 Case/认领/处置字段/监督台/飞书群通知仍有结构性差距。 |

---

## 1. 产品方向对照

| 维度 | 归档 Spec（目标） | 现有实现 / 文档 | 差距 |
|------|-------------------|-----------------|------|
| 一句话 | 监督员工是否处理异常 + 过程留痕 | 多平台经营中台蓝图（采购/财务/多域导航 + 任务中心） | 蓝图更宽；**差异化主线（人与过程）未产品化** |
| 主体界面 | 员工工作台 + 老板监督台 | Vue 导航含「异常任务中心」「老板驾驶舱」等，多为壳/域规划 | 无独立「认领→处置→关闭」与「超时红灯监督」闭环 UI |
| 飞书定位 | **群机器人通知**（必做）；非主库 | **Bitable 同步**任务表（`sync_feishu_*` / Worker） | 方向相反：有多维表同步，**无群 Webhook @人** |
| 智能推荐 C | 1.0 不做，只攒字段 | 无推荐引擎 | 对齐（都不做）；但 **C 预留字段也没有** |

---

## 2. MVP 六件事逐项对照

| # | MVP Ship-now | Spec 要求 | 现有能力 | 状态 |
|---|--------------|-----------|----------|------|
| 1 | 案件本子 + 状态机 | `open → claimed → closed`；关案必填 disposition + rationale | `task`: `open / in_progress / resolved / cancelled`；`progress_note` 可选关案 | **部分** — 无认领态、无强制处置字段 |
| 2 | 信号建案 | `temu_alert` / `tiktok_risk` / `fulfillment_exception` | `ingest` + `upsert_task_from_anomaly`；AMZ 环比规则种子；模拟采集脚本 | **部分** — 通用建任务有；三类型 Case 契约未固定 |
| 3 | 员工工作台 | 认领 → 填处置 → 关闭；未认领不可关 | 任务列表/进度 API；Web 任务中心偏列表 | **缺口** — 无 claim API/UI 规则 |
| 4 | 老板监督台 | 按人/店/超时筛选 + 红灯 | 任务可按 owner/status/platform 筛；`due_at` 有 | **缺口** — 无 SLA 分类型、无超时红灯监督视图 |
| 5 | 案件时间线 | append-only：create/claim/close/… + actor/ts | `task_progress` 有 note/from/to/operator | **部分** — 有流水雏形，缺结构化 activity 与处置结果 |
| 6 | 飞书群通知 | 新建/超时 → 群 @ + 深链；失败不挡闭环 | 飞书 **多维表** create/update；无群消息/Webhook | **缺口** |

---

## 3. 数据模型对照

| Spec 概念 | 期望字段/行为 | 现有表/字段 | 差距 |
|-----------|---------------|-------------|------|
| Case | case_type、状态机 claimed、SLA 双时限 | `task` + `anomaly_type`、`due_at` 单截止 | 需扩展或映射 Case 语义 |
| CaseEvent | activity 枚举、actor、outcome | `task_progress` | 需结构化 activity / outcome |
| 自创字段 | disposition_code、rationale、outcome_label、false_positive | 无 | **全缺** |
| 角色 | manager / operator / admin | `org_user.is_admin` 布尔 | 无三角色权限模型 |
| 通知日志 | 群发送成功/失败 | 无（仅 bitable map/job） | **全缺** |
| 幂等 | case_type + source_ref | `dedupe_key = platform:biz_id:anomaly_type` + open 唯一索引 | 思路可复用，类型命名需对齐 |

---

## 4. 可复用资产（实现 Work OS 时优先用）

| 资产 | 路径 | 用途 |
|------|------|------|
| 登录 JWT | `backend/app/api/auth.py` | 1.0 简单账号（A8） |
| 店铺主数据 | `shop` + `api/shops.py` | 按店筛选 / 负责人 |
| 异常→任务引擎 | `domain/task_engine.py` | 幂等建单、进度、闭环骨架 |
| Ingest 幂等 | `ingest_raw` + API | 信号接入 |
| Outbox | `outbox_event` | 可改挂「飞书群通知」而非仅 bitable |
| Web 壳 | `web/src/App.vue` | 导航与登录；任务中心可改造 |
| 采集 Agent | `collectors/agent-core` | 边缘上报 |
| Docker 栈 | `deploy/docker-compose.yml` | 本地/演示环境 |

---

## 5. 不应在 1.0 继续做深的（相对 Work OS Spec）

| 项 | 原因 |
|----|------|
| 采购/财务/美工完整产品线 | Spec Out of Scope；导航可保留壳，不占 MVP |
| 飞书多维表当主展示 | Spec 明确飞书=通知喇叭；bitable 可降级/后置 |
| AMZ 环比规则深化 | 与 MVP 三线（Temu/TK/仓）优先级不同；可作 task 样板保留 |
| C 推荐 / 平台写回 | Spec 禁止 1.0 |

---

## 6. 推荐落地路径（供 SOP 后续 Gate 使用）

```text
Phase0 基座（已有）
  → 语义升级：task ≈ Case（状态机 + 处置字段 + CaseEvent）
  → API：claim / close(强制字段) / 监督列表(超时)
  → Web：工作台 + 监督台 + 详情时间线（对照 mocks/mvp-*.html）
  → 通知：群 Webhook 接入 outbox（与 bitable 解耦）
  → 接入：Temu 真告警优先；TK/仓夹具
```

**SOP mode 建议：** `feature`（已有仓库与 Phase0 代码；Work OS 为在基座上的主线切片，非空仓 greenfield）。

---

## 7. 验收覆盖速查（相对 ACCEPTANCE）

| 功能 | Happy 可测？ | 备注 |
|------|--------------|------|
| F1 信号建案 | 半可 | 通用 task 可测；缺 case_type 语义与三线夹具约定 |
| F2 工作台闭环 | 否 | 无 claim / 强制 disposition |
| F3 监督台超时 | 否 | 有 due_at，无红灯监督产品 |
| F4 时间线 | 半可 | progress 列表可扩展 |
| F5 飞书群 | 否 | 仅 bitable |
| F6 无智能建议 | 是 | 当前无该入口 |

---

## 8. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-28 | 初版：归档 Spec 迁入 `docs/specs/` 后对照代码盘点 |
