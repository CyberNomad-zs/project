---
name: review-ship
description: >
  AI 开发 SOP 子技能：Diff 门禁、PR 与发布边界。
  仅由总控 ai-dev-sop 在 PHASE 7 加载；不要单独作为主入口。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "7"
---

# 06 — Review + Ship 边界

由总控在 **PHASE 7** 加载。

## 必读

1. `checklists/gate-c-diff.md`  
2. `gates.md`（G2/G3、DoD）  
3. MVP Success + ARCH 边界 + Plan  

## Gate C

对照 Plan **与** MVP Success **与** ARCH 边界；PR 链 SPEC/MVP/ARCH/PLAN。

```text
DIFF READY — waiting for approval
```

**不可跳过** Gate C。可选 PHASE 8 回写。
