---
name: spec-to-plan
description: >
  AI 开发 SOP 子技能：架构批准后的 Explore、Plan、Findings。
  仅由总控 ai-dev-sop 在 PHASE 4–5 加载；不要单独作为主入口。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "4-5"
---

# 04 — Plan（Explore / Gate A / Gate B）

由总控在 **PHASE 4–5** 加载。前提：**Spec、MVP、ARCH 均已批准**（合法 skip/N/A 除外）。

## 必读

1. SPEC + MVP + ARCHITECTURE + ACCEPTANCE  
2. `$SOP_ROOT/skills/ai-dev-sop/references/checklists/gate-a-plan.md`  
3. `$SOP_ROOT/skills/ai-dev-sop/references/checklists/gate-b-findings.md`  
4. `$SOP_ROOT/docs/节点交付物.md`

## PHASE 4 — Explore + Plan

Plan **⊆ Ship-now**，且落在 ARCH 模块/边界内。  
写 `docs/specs/PLAN-<slug>.md`。

### feature

只读探查 → 精确文件列表 + 方案 3–5 条 + 验证计划。

### greenfield

目录树/里程碑/首刀（技术第一步，≠ 另定产品范围）。

```text
PLAN READY — waiting for approval
```

## PHASE 5 — Findings

```text
FINDINGS READY — waiting for approval
```

冲突回 PHASE 1–3；Plan 错再批 Gate A。

## 不做

- 未批 ARCH 就 Plan  
- 以 Plan 扩大 Ship-now 或突破 ARCH 边界  
