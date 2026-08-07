---
name: mvp-cut
description: >
  AI 开发 SOP 子技能：Spec 批准后的 MVP / Ship-now 切片（Gate M）。
  仅由总控 ai-dev-sop 在 PHASE 2 加载；不要单独作为主入口。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "2"
---

# 02 — MVP / Ship-now（Gate M）

由总控在 **PHASE 2** 加载。前提：**Spec 已用户批准**。  
目标：全量 Spec → **本迭代可交付的最小切片**，再允许 Plan/开发。

## 必读

1. 已批准的 SPEC + ACCEPTANCE 工作副本  
2. `$SOP_ROOT/skills/ai-dev-sop/references/checklists/gate-m-mvp.md`  
3. SPEC **§2.4 MVP / Ship-now**（无则补写；或 `docs/specs/MVP-<slug>.md`）

## 执行步骤

1. 复述 Spec 目标与 In Scope P0  
2. 起草 Ship-now（建议 ≤ 5 条）、Defer、Success check  
3. 校验：Ship-now ⊆ In Scope，且不触及 Out of Scope  
4. 小改动可写「Ship-now = Spec In Scope P0 全文」——**仍须**哨兵等人批  
5. 同步 ACCEPTANCE「MVP Demo」勾选区与 Success check  
6. 按清单自检后输出：

```text
MVP READY — waiting for approval
```

## 完成定义

- 用户明确批准 MVP（或合法热修 skip 并记录理由）  
- 未批准前 **禁止** 进入 PHASE 3 架构 / 输出 `ARCH READY` 或 `PLAN READY`  
- 批准后进入 **PHASE 3**（`skill-pack/03-arch-design`）

## 不做

- 把 MVP 当成又一轮需求访谈（缺口回 PHASE 1）  
- 用 Plan「技术首刀」替代产品切片批准  
- 静默扩大 Ship-now  
