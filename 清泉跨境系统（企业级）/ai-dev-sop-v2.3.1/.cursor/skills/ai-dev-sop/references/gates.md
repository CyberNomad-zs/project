# 门禁：DoR · Gate M/D/A/B/C · G0–G3

> 过门禁前由总控 Read。执行形态：**哨兵句 + 人批准 + 进仓制品**。  
> 交付物总表：`$SOP_ROOT/docs/节点交付物.md`。

---

## 1. L1 DoR（Definition of Ready）

**未通过 DoR → 禁止进入 PHASE 2 及之后写业务代码。**

### 1.1 量化阈值

| 指标 | 阈值 | 不达标动作 |
|------|------|------------|
| Out of Scope | **≥ 3 条** | 回 L1 补边界 |
| Open Questions（未关闭） | **≤ 2** | 再澄清或 `[ASSUMES:]` |
| Edge / 异常场景 | **≥ 3** | 回 L1 |
| 用户批准 Spec | **必须** | 无批准 → 停 |
| 不可测措辞 | **0** | 改写 |

### 1.2 哨兵句

```text
SPEC READY — waiting for approval
```

交付物：`SPEC-*.md` + `ACCEPTANCE-*.md`。

---

## 2. Gate M / D / A / B / C

| Gate | 时机 | 哨兵句 | 交付物 | 人要回答 |
|------|------|--------|--------|----------|
| **M MVP** | Spec 后 | `MVP READY — waiting for approval` | §2.4 / MVP-*.md | 本迭代交付面？ |
| **D Arch** | MVP 后 | `ARCH READY — waiting for approval` | ARCHITECTURE-*.md | 内部结构能否支撑？ |
| **A Plan** | Arch 后 | `PLAN READY — waiting for approval` | PLAN-*.md | 文件级方案 ⊆ MVP∩ARCH？ |
| **B Findings** | 探查后 | `FINDINGS READY — waiting for approval` | Findings 节 | 事实是否推翻？ |
| **C Diff** | commit 前 | `DIFF READY — waiting for approval` | Diff Summary + PR | 能否提交？ |

### 跳过规则

| 场景 | M | D | A | B | C |
|------|---|---|---|---|---|
| 默认 | 不可跳 | 不可跳 | 不可跳 | 不可跳 | **不可跳** |
| 单文件热修 | 可跳 | 可跳 | 可跳 | 可跳 | **不可跳** |
| 小改无边界变化 | 不可跳 | **N/A+批准**（不可静默跳） | 不可跳 | 按左 | 不可跳 |
| greenfield 无可探代码 | — | 不可跳（须 ARCH） | — | 可 N/A | 不可跳 |

### 清单

- [`checklists/gate-m-mvp.md`](checklists/gate-m-mvp.md)
- [`checklists/gate-d-arch.md`](checklists/gate-d-arch.md)
- [`checklists/gate-a-plan.md`](checklists/gate-a-plan.md)
- [`checklists/gate-b-findings.md`](checklists/gate-b-findings.md)
- [`checklists/gate-c-diff.md`](checklists/gate-c-diff.md)

---

## 3. G0–G3

| 等级 | 示例 | 权限 |
|------|------|------|
| **G0** | 读文件 | 可自动 |
| **G1** | 改本地、跑测试 | 可自动 |
| **G2** | push、改共享配置 | **必须确认**（预览） |
| **G3** | 生产/资金/密钥/合规字段/生产 PII 等 | **禁止自主** |

### 3.1 G3 阻断清单

- 生产部署 / 生产配置变更
- 删除数据、truncate、不可逆迁移
- 密钥、Token、证书、`.env` 真值写入仓库或日志
- **支付、退款、结算、计费** 相关逻辑
- **外部系统生产凭据** 的配置与使用
- **法定/合规关键字段** 的写入逻辑
- **生产用户数据 / 真实 PII** 用于调试或长期进 Prompt
- 权限提升、对全体用户开放的管理接口

### 3.2 G2 预览模板

```text
## G2 操作预览
- 动作: <push | 改配置 | …>
- 影响范围: <环境/人/数据>
- 回滚: <如何回滚>
- 请回复「批准」或「取消」
```

---

## 4. DoD 雏形

- [ ] Gate C 已批准  
- [ ] 节点交付物路径齐全（或合法 skip/N/A 理由）  
- [ ] MVP Success / ARCH 边界 / Plan 文件列表一致  
- [ ] 无密钥与生产数据  
- [ ] PR 链 SPEC / MVP / ARCH / PLAN  

---

## 5. 放行话术

```text
⛔ GATE BLOCKED — <名称>
原因: <一条>
需要你: <批准 | 补充信息 | 升级审批>
```

```text
<哨兵句>
请审阅进仓制品；回复「批准」继续，或指出要改的点。
```

---

## 6. 机械校验

```bash
"$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh" <SPEC.md> [ACCEPTANCE.md]
```

脚本只管 Spec DoR；MVP/ARCH 靠清单与人批。
