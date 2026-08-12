# Gate B — Findings 检查清单

在**开始修改业务代码之前**输出。greenfield 无代码可探时见文末 N/A。

## 必含结构

```markdown
## Findings
### 探查范围
- 读过的路径/模块：

### 当前状态（事实）
-

### 意外发现
- 未文档化的依赖 / 多处调用 / 缺失迁移 / 与 Plan 冲突：

### 对原 Plan 的影响
- [ ] 无影响，按原 Plan 执行
- [ ] 需修订 Plan（见下）
- [ ] 需打回 L1（Spec 冲突）

### 修订后的 Plan（若有）
-

### 风险增量
-
```

## 自检

- [ ] 发现基于真实阅读，非猜测
- [ ] 若 Plan 变更，已写清差异
- [ ] 若 Spec 被推翻，已建议回 PHASE 1，而非强行编码
- [ ] 无「先改了再说」

## 哨兵句

```text
FINDINGS READY — waiting for approval
```

## greenfield N/A

```text
GATE B: N/A (greenfield, no codebase findings)
依据: <无业务代码 / 无旧系统对接 / 无强制模板探查需求>
```

存在公司模板或旧系统对接时 **不可** N/A。
