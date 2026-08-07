# Gate A — Plan 检查清单

在输出 `PLAN READY — waiting for approval` 之前完成。  
**前提**：ARCH（Gate D）已批准，或 N/A/skip 已批。

## 必含结构

写到 `docs/specs/PLAN-<slug>.md`（或等价固定路径）：

```markdown
## Plan
### Objective
### Mode
### 引用
- Spec / MVP / ARCH 路径
### 文件列表
| 动作 | 路径 | 所属 ARCH 模块 | 说明 |
### 方案（3–5 条）
### 非目标
### 待决决策
### 风险与回滚
### 验证计划（对照 MVP Demo）
```

## 自检

- [ ] ARCH 已批准（或 N/A/skip 理由已记录）
- [ ] 文件列表 ⊆ Ship-now，且落在 ARCH 边界内
- [ ] 路径具体；无「相关文件」
- [ ] 交付物已进仓（不只对话）
- [ ] 未计划未授权 G3

## 哨兵句

```text
PLAN READY — waiting for approval
```
