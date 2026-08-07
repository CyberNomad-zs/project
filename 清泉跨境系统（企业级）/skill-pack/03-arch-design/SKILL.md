---
name: arch-design
description: >
  AI 开发 SOP 子技能：MVP 批准后的架构设计（Gate D）。
  仅由总控 ai-dev-sop 在 PHASE 3 加载；不要单独作为主入口。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "3"
---

# 03 — Architecture（Gate D）

由总控在 **PHASE 3** 加载。前提：**MVP 已批准**（或合法热修 skip）。  
目标：内部结构进仓并获批，再允许 Plan/写码。

## 必读

1. 已批 SPEC + MVP + ACCEPTANCE  
2. `$SOP_ROOT/templates/ARCHITECTURE.md`  
3. `$SOP_ROOT/skills/ai-dev-sop/references/checklists/gate-d-arch.md`  
4. 人读总表：`$SOP_ROOT/docs/节点交付物.md`  
5. feature：只读探查现有模块边界（为增量图服务）

## 执行步骤

1. 判断：完整 ARCH / 增量 ARCH / N/A（理由）/ 热修 skip  
2. 写 `docs/specs/ARCHITECTURE-<slug>.md`  
3. 校验：图与边界支撑 Ship-now；不把 Defer 做成硬依赖  
4. 自检清单通过后输出：

```text
ARCH READY — waiting for approval
```

## 完成定义

- 用户批准 ARCH（或批准 N/A / 合法 skip）  
- 未批准前 **禁止** PHASE 4 Plan 写业务代码  

## 不做

- 用文件列表 Plan 代替架构图  
- 画与 Ship-now 无关的大而全未来架构  
- 无理由空 N/A  
