---
name: req-clarify
description: >
  AI 开发 SOP 子技能：L1 需求澄清。仅由总控 ai-dev-sop 在 PHASE 1 加载；
  不要单独作为项目主入口（请用 /ai-dev-sop）。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "1"
---

# 01 — 需求澄清（L1）

由总控在 **PHASE 1** 加载。目标：模糊需求 → 可开发 Spec。

## 必读（SOP_ROOT = `…/skills/ai-dev-sop` 目录再上两级）

1. 结构化 INTENT（当前工作区工作副本）。若只有 `INTENT-raw` 或原文：先整理/代填 §0，并挂上 raw 路径
2. `$SOP_ROOT/skills/ai-dev-sop/references/l1-scan-dimensions.md`
3. `$SOP_ROOT/skills/ai-dev-sop/references/gates.md`（DoR 节）
4. 模板：`$SOP_ROOT/templates/SPEC.md`、`ACCEPTANCE.md` → 写到工作区 `docs/specs/`
5. 需要时：`$SOP_ROOT/templates/spec-compliance-checklist.md`

## INTENT → 八维映射

| INTENT | L1 维 |
|--------|-------|
| §0 / §1 | 维 1–2 用户、目标 |
| §2 | 维 3 范围 |
| §3 | 维 4 流程与异常 |
| §4 | 维 5–8 数据/集成/NFR/合规 |
| §5 | SPEC 原始需求原文 |
| §6 | OPEN QUESTIONS 种子 |

## 执行步骤

1. 固化 INTENT 工作副本；复述 §0  
2. 八维扫描，标记：已明 / 缺口 / 假设 / N/A  
3. 每轮 3–5 问；优先：安全、数据丢失、资金、权限、合规；优先问 §6 未知清单  
4. 一次一问更稳；所有假设用 `[ASSUMES: …]`  
5. 写出 SPEC + ACCEPTANCE 工作副本（建议 `docs/specs/`）；SPEC §1.1 引用 INTENT 路径或嵌入原文  
6. Out of Scope **由人主导**，Agent 不得默默扩 scope  
7. 运行：

```bash
"$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh" <SPEC> [ACCEPTANCE]
```

8. PASS 后输出：

```text
SPEC READY — waiting for approval
```

9. Spec 批准后 → **PHASE 2 MVP** → **PHASE 3 ARCH** → Plan；**不要**直接写码  
10. 交付物路径见 `$SOP_ROOT/docs/节点交付物.md`

## 完成定义

- DoR 量化与布尔项全过（见 gates）  
- 用户明确批准；制品已进仓  
- 未批准前 **禁止** 进入后续写业务代码  

## 不做

- 直接拆任务写码  
- 跳过维 8（须填或 N/A+理由）  
- 用「先做再说」跳过 MVP（Gate M）  
