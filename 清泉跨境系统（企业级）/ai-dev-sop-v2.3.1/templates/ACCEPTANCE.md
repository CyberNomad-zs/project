# ACCEPTANCE: <与 SPEC 相同标题>

| 字段 | 值 |
|------|-----|
| Spec ID | SPEC-… |
| 状态 | draft \| ready \| approved |

> 与 SPEC 成对使用。优先 **Gherkin**；也可用可勾选 AC。  
> 每条**主功能**：至少 **1 happy + 1 error**。全篇 **Edge ≥ 3**。

---

## 约定

- 场景标题清晰、可独立验证
- 禁止：可能、大概、适当、优化一下、尽快
- 每个 Scenario 应能在 <5 分钟内由人或脚本判定 pass/fail

---

## 功能 F1: <名称>

### Happy

```gherkin
Scenario: F1-H1 <标题>
  Given <前置>
  When <动作>
  Then <可观测结果>
```

### Error / 边界

```gherkin
Scenario: F1-E1 <标题>
  Given <前置>
  When <失败或边界动作>
  Then <错误提示或降级行为>
```

---

## 功能 F2: <名称>（按需复制）

### Happy

```gherkin
Scenario: F2-H1 <标题>
  Given
  When
  Then
```

### Error / 边界

```gherkin
Scenario: F2-E1 <标题>
  Given
  When
  Then
```

---

## Edge 清单（汇总，**≥ 3**）

| ID | 描述 | 期望行为 | 对应 Scenario |
|----|------|----------|---------------|
| E1 | | | |
| E2 | | | |
| E3 | | | |

---

## 可勾选验收（发布/Demo 用）

### MVP Demo（与 SPEC §2.4 Success check 对齐）

> 本迭代必须能演示/测过的最小集；Gate C 对照此项。

- [ ] <Success check 1>
- [ ]

### P0

- [ ] <从 Scenario 提炼的检查项>
- [ ]
- [ ]

### P1（可选）

- [ ]

---

## 验证记录

| 日期 | 人/命令 | 结果 | 备注 |
|------|---------|------|------|
| | | pass/fail | |
