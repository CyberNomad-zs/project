---
name: ai-dev-sop
description: >
  标准 AI 开发 SOP（唯一可启动前置入口）。用户说「按 AI 开发 SOP」「启动开发 SOP」、
  「/ai-dev-sop」，或给出模糊产品需求需要从澄清做到 PR 时使用。
  仅在用户明确要求按本 SOP 时使用；不要用于纯问答、纯代码解释、
  或已明确只要改一行的热修（除非用户强制要求走完整 SOP）。
disable-model-invocation: true
metadata:
  version: "2.3.1"
  phase: P2
---

# AI 开发 SOP（总控）

你是严格执行 AI 开发流程的 Agent。用**清单与门禁**替代自由裁量；**节点交付物进仓**；硬门禁未过不得写业务代码。

## 硬规则（永远遵守）

1. **禁止跳过 L1**：没有用户确认的 Spec，禁止写业务代码。
2. **禁止跳过 MVP（Gate M）**：未批 Ship-now 禁止架构/Plan/写码（热修可 skip，须记理由）。
3. **禁止跳过架构（Gate D）**：未批 ARCH（或未批 N/A）禁止 Plan/写码（热修可 skip；小改须 N/A+理由并批准）。
4. **硬门禁失败 → 停**：停止写码，回上一 PHASE；禁止「先做了再说」。
5. **G3 禁止自主**：资金与结算、外部系统凭据、法定/合规关键字段、生产数据、删数、密钥、生产部署 → 升级授权审批人。
6. **哨兵句原文输出**：到门禁必须输出规定英文哨兵句，然后等待用户「批准」。
7. **渐进加载**：进入某 PHASE 前，Read 对应 `references/` **与** `skill-pack/`。
8. **制品进仓**：Spec / MVP / ARCH / Plan / 假设写文件，不只活在对话里。见 `$SOP_ROOT/docs/节点交付物.md`。

## 启动动作

1. **识别输入层级：** INTENT-raw → 先整理为 INTENT；结构化 INTENT → 存工作副本并复述 §0。  
2. 声明 mode（`feature` / `greenfield`）；`PHASE 0`。  
3. Read [`references/workflow.md`](references/workflow.md)。  
4. 进入 PHASE 0 → 1，不得直接编码。  

## 阶段一览与 skill-pack 路由

| PHASE | 名称 | 硬门禁 | references | skill-pack |
|-------|------|--------|------------|------------|
| 0 | 识别 mode | — | `workflow.md` | — |
| 1 | L1 → SPEC | **是** | `l1-scan-dimensions.md`、`gates.md` | `01-req-clarify` |
| 2 | MVP → Gate M | **是** | `checklists/gate-m-mvp.md` | `02-mvp-cut` |
| 3 | Architecture → Gate D | **是** | `checklists/gate-d-arch.md` | `03-arch-design` |
| 4 | Explore + Plan → Gate A | **是** | `checklists/gate-a-plan.md` | `04-spec-to-plan` |
| 5 | Findings → Gate B | **是**（greenfield 可 N/A） | `checklists/gate-b-findings.md` | （属 04） |
| 6 | Implement + Verify | — | — | `05-implement-verify` |
| 7 | Diff → Gate C → PR | **是** | `checklists/gate-c-diff.md` | `06-review-ship` |
| 8 | （可选）坏模式回写 | — | — | — |

路径均相对 **`$SOP_ROOT/skill-pack/...`**（上表为短名）。人读交付物总表：[`docs/节点交付物.md`](../../../docs/节点交付物.md)。

| 制品 | 看见 |
|------|------|
| MVP | 交付面 |
| ARCHITECTURE | 内部结构 |
| PLAN | 文件级落地 |

## 哨兵句（必须原文）

| 时机 | 输出（单独一行） |
|------|------------------|
| Spec | `SPEC READY — waiting for approval` |
| MVP | `MVP READY — waiting for approval` |
| 架构 | `ARCH READY — waiting for approval` |
| Plan | `PLAN READY — waiting for approval` |
| Findings | `FINDINGS READY — waiting for approval` |
| Diff | `DIFF READY — waiting for approval` |

## L1 / 后续最低产物

- Spec 批后：§2.4 MVP → Gate M  
- MVP 批后：`ARCHITECTURE-<slug>.md` → Gate D  
- ARCH 批后：`PLAN-<slug>.md` → Gate A  
- DoR：`"$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh"` 在 `SPEC READY` 前运行  

## 用户侧唯一记法

```text
1. 甲方 INTENT-raw → 产品 INTENT
2. /ai-dev-sop + 粘贴 INTENT
3. 批 Spec → 批 MVP → 批架构 → 批 Plan →（Findings）→ 实现 → 批 Diff
4. 每个节点看进仓制品，不只看对话
5. 不确定 → ASSUMPTIONS 或升级审批
```

## 路径约定（SOP_ROOT）

**SOP_ROOT** = 本 `SKILL.md` 所在目录（`…/skills/ai-dev-sop`）再上两级。  
读包内文件用 SOP_ROOT；写制品用当前工作区 `docs/specs/`。

| 用途 | 读（SOP_ROOT） | 写（工作区） |
|------|----------------|--------------|
| Skill / references | `skills/ai-dev-sop/` | — |
| 子技能 | `skill-pack/01`…`06` | — |
| 模板 | `templates/` | `docs/specs/` |
| 交付物总表 | `docs/节点交付物.md` | — |
