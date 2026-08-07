# Gate C — Diff 检查清单

commit / push / 开 PR **之前**必须完成。热修也**不可跳过**本门。

## 必含结构

```markdown
## Diff Summary
### 变更统计
- 文件数：
- 主要路径：

### 与 Plan / MVP / ARCH 对照
| 项 | 状态 | 说明 |
|----|------|------|
| Plan 项… | done / partial / extra | |
| MVP Success check… | pass / fail / partial | |
| ARCH 边界… | 遵守 / 突破 | |

### 自检结果
- 密钥/Token: 无 / 有 → ⛔
- Scope creep（超出 Ship-now）: 无 / 有 → 说明
- 测试: 已跑 <命令> / 手工步骤 <…>
- 错误处理: 未吞异常 / 有疑问

### 残余风险
-

### PR 草稿要点
- 标题：
- 背景：
- Spec/MVP/ARCH/PLAN 链接：
- 验收：
- 门禁跳过说明（若有）：
```

## 逐项检查（人+Agent）

- [ ] **范围**：未超出 MVP Ship-now 与 ARCH 边界；若有，已列出并获准
- [ ] **MVP Success**：Success check / MVP Demo 已过或标明缺口
- [ ] **交付物链接**：PR 能点到 SPEC/MVP/ARCH/PLAN
- [ ] **删除**：无意外删文件/大段逻辑
- [ ] **密钥**：无硬编码凭据、无 `.env` 真值
- [ ] **PII / 生产数据**：无写入仓库
- [ ] **测试**：有自动化或可复现手工步骤
- [ ] **AC**：ACCEPTANCE MVP Demo / P0 已覆盖或标明缺口
- [ ] **G2/G3**：无未授权 push/部署/支付相关

## 哨兵句

```text
DIFF READY — waiting for approval
```

用户批准前：禁止 push；禁止合 main；禁止发生产。
