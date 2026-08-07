# 状态机：PHASE 0–8（强制顺序）

> 任一硬门禁失败 → **停止写码**，回上一 PHASE。  
> **节点 = 哨兵句 + 人批准 + 进仓制品**（见 `$SOP_ROOT/docs/节点交付物.md`）。

## 总览

```text
Intent
  → PHASE 0  mode
  → PHASE 1  L1 澄清 + SPEC 批准          [硬]  + skill-pack/01
  → PHASE 2  MVP / Ship-now → Gate M      [硬]  + skill-pack/02
  → PHASE 3  Architecture → Gate D        [硬]  + skill-pack/03
  → PHASE 4  Explore + Plan → Gate A      [硬]  + skill-pack/04
  → PHASE 5  Findings → Gate B            [硬 / greenfield 可 N/A]
  → PHASE 6  Implement + Verify                 + skill-pack/05
  → PHASE 7  Diff → Gate C → PR           [硬]  + skill-pack/06
  → PHASE 8  （可选）坏模式回写
```

人保留：产品优先级、MVP 切片、架构边界、安全合规、生产发布。  
Agent 可承担：澄清/MVP/架构草稿、实现、测试初稿、文档同步、低风险本地改动（G0–G1）。

| 制品 | 看见 |
|------|------|
| MVP | 交付面 |
| ARCHITECTURE | 内部结构 |
| PLAN | 本迭代文件级落地 |

---

## PHASE 0 — 识别 mode

| 信号 | mode |
|------|------|
| 已有仓库、改功能/修 bug | `feature` |
| 「从 0 / 新项目 / 新服务」 | `greenfield` |
| 不确定 | 问 1 句；有代码则 `feature`，否则 `greenfield` |

输出 `mode` + 理由后进入 PHASE 1。  
Read：`references/l1-scan-dimensions.md`、`$SOP_ROOT/skill-pack/01-req-clarify/SKILL.md`。

---

## PHASE 1 — L1 需求澄清（硬门禁）

1. Read 八维清单 + gates DoR + **`$SOP_ROOT/skill-pack/01`**。  
2. 缺口扫描；每轮 3–5 问；安全/资金/权限优先。  
3. 写 SPEC + ACCEPTANCE 到工作区 `docs/specs/`。  
4. 运行 `$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh`（须 PASS）。  
5. 输出：

```text
SPEC READY — waiting for approval
```

**通过**：用户批准 + DoR。批准后 → PHASE 2（不得跳到 Plan/写码）。

---

## PHASE 2 — MVP / Ship-now → Gate M（硬门禁）

Read：`$SOP_ROOT/skill-pack/02-mvp-cut/SKILL.md`、`checklists/gate-m-mvp.md`。

```text
MVP READY — waiting for approval
```

批准前禁止写业务代码、禁止 `ARCH READY` / `PLAN READY`。热修可 skip（记理由）。

---

## PHASE 3 — Architecture → Gate D（硬门禁）

Read：`$SOP_ROOT/skill-pack/03-arch-design/SKILL.md`、`checklists/gate-d-arch.md`、`templates/ARCHITECTURE.md`。  
前提：**MVP 已批准**（或合法 skip）。

1. feature：只读探查现有边界 → **增量**架构；greenfield：模块/目录顶层图。  
2. 写 `docs/specs/ARCHITECTURE-<slug>.md`。  
3. 小改无边界变化：可 N/A（须写理由），**仍须**哨兵等人批。  
4. 输出：

```text
ARCH READY — waiting for approval
```

批准前禁止 `PLAN READY`、禁止写业务代码。

---

## PHASE 4 — Explore + Plan → Gate A（硬门禁）

Read：`$SOP_ROOT/skill-pack/04-spec-to-plan/SKILL.md`、`checklists/gate-a-plan.md`。  
前提：**ARCH 已批准**（或 N/A/skip 已批）。

Plan **⊆ Ship-now**，且落在 ARCH 已声明模块/边界内。  
交付物：`docs/specs/PLAN-<slug>.md`（或等价固定路径）。

```text
PLAN READY — waiting for approval
```

---

## PHASE 5 — Findings → Gate B

Read：`checklists/gate-b-findings.md`。

```text
FINDINGS READY — waiting for approval
```

greenfield 可 N/A（无代码且无遗留约束）。  
Spec/MVP/ARCH 冲突 → 回 PHASE 1–3；Plan 错 → 再批 Gate A。

---

## PHASE 6 — Implement + Verify

Read：`$SOP_ROOT/skill-pack/05-implement-verify/SKILL.md`。

贴合 MVP + ARCH + Plan；超出先请示。

---

## PHASE 7 — Diff → Gate C → PR

Read：`$SOP_ROOT/skill-pack/06-review-ship/SKILL.md`、`checklists/gate-c-diff.md`。

```text
DIFF READY — waiting for approval
```

热修可跳 M/D/A/B，**不可跳 C**。

---

## PHASE 8 — 坏模式回写（可选）

3–5 条短规则写回 `AGENTS.md` 或 checklist。

---

## 回退矩阵

| 触发 | 回到 |
|------|------|
| 需求目标/范围/验收变更 | PHASE 1 |
| Ship-now 切片错误 | PHASE 2 |
| 模块边界/数据流错误 | PHASE 3 |
| Plan 不可行 | PHASE 4（必要时 1–3） |
| Diff 暴露错误实现 | PHASE 6 或 4 |
| 触及 G3 且无授权 | **停止**；升级审批 |

## 状态报告格式

```text
## SOP Status
- mode: feature | greenfield
- phase: N — <name>
- skill-pack: <loaded pack id or none>
- artifacts: <paths>
- mvp: draft | waiting | approved | skipped
- arch: draft | waiting | approved | N/A | skipped
- gate: none | waiting | approved | N/A
- blockers: <none | list>
- next: <one action>
```
