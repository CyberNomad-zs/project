# Gate D — Architecture 检查清单

在输出 `ARCH READY — waiting for approval` 之前完成。  
**前提**：MVP（Gate M）已批准或合法热修 skip。  
**区分**：MVP = 产品交付面；ARCHITECTURE = 内部结构；Plan = 文件级落地。

## 必含结构

使用 `$SOP_ROOT/templates/ARCHITECTURE.md` → 工作区 `docs/specs/ARCHITECTURE-<slug>.md`。

非 N/A 时至少包含：

- [ ] 模块/逻辑视图（mermaid 或等价）
- [ ] 关键数据流或时序（可简）
- [ ] 边界：改什么 / 不改什么
- [ ] 关键决策 ≥1 条，或显式 N/A
- [ ] 明确支撑哪些 Ship-now 项

## 自检

- [ ] MVP 已批准（或 skip 理由已记录）
- [ ] 架构能覆盖 Ship-now；未把 Defer 做成必须依赖
- [ ] feature：标明相对现有系统的**增量**；greenfield：目录/模块顶层清晰
- [ ] 无「适当分层 / 以后再说」等无边界表述
- [ ] 触及 G3 已标升级
- [ ] N/A 时理由具体（非「太简单」空话）

## 哨兵句

```text
ARCH READY — waiting for approval
```

用户批准前：**禁止**输出 `PLAN READY`、**禁止**写业务代码。
