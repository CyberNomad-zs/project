# Gate M — MVP / Ship-now 检查清单

在输出 `MVP READY — waiting for approval` 之前，MVP 正文须覆盖以下项。  
**前提**：Spec 已用户批准。  
**区分**：MVP = 产品交付面（PHASE 2）；ARCHITECTURE = 内部结构（PHASE 3）；Plan「首刀」= 技术落地（PHASE 4）。

## 必含结构

```markdown
## MVP / Ship-now
### Spec 引用
<path to SPEC>

### Ship-now（本迭代必做，建议 ≤ 5 条）
| # | 能力 | 对应 Spec In Scope # | 说明 |
|---|------|----------------------|------|
| 1 | | | |

### Defer（明确下一版）
1.
2.

### Success check（可演示/可测，≥ 1）
- [ ] <用户可感知的最小成功>

### 跳过（仅热修）
- 理由: <空 | 单文件热修…>
```

也可直接填在 SPEC **§2.4**；复杂时另存 `docs/specs/MVP-<slug>.md` 并在 SPEC 链接。

## 自检

- [ ] Spec 已批准
- [ ] Ship-now ≥ 1 条（或显式「= Spec In Scope P0 全文」）
- [ ] Defer 或 Non-goals 能看出「本迭代不做什么」
- [ ] Success check ≥ 1，可演示或可测
- [ ] Ship-now **不包含** Spec Out of Scope 项
- [ ] 未把全量 P1/P2 默默塞进 Ship-now
- [ ] 非热修：未静默跳过本门

## 哨兵句

```text
MVP READY — waiting for approval
```

用户批准前：**禁止** Explore 写业务代码、**禁止**输出 `PLAN READY`。
