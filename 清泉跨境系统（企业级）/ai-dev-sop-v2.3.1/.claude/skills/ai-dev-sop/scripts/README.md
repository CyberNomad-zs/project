# scripts/ — Harness 机械门禁

P1 起提供可执行校验；**不替代**人批准与 G3 升级。

## check-dor.sh

L1 Definition of Ready 机械检查。

```bash
# SOP_ROOT = 本包根（含 skills/ skill-pack/ templates/）
# 全局安装后可用绝对路径，不必在业务仓根执行
"$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh" path/to/SPEC.md
"$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh" path/to/SPEC.md path/to/ACCEPTANCE.md

# 在 SOP 仓根时也可：
./skills/ai-dev-sop/scripts/check-dor.sh docs/specs/SPEC-demo.md

# 可调阈值
MIN_OUT=3 MIN_EDGE=3 MAX_OPEN=2 \
  "$SOP_ROOT/skills/ai-dev-sop/scripts/check-dor.sh" docs/specs/SPEC-demo.md
```

| 检查 | 默认阈值 | 失败时 |
|------|----------|--------|
| Out of Scope 条目数 | ≥ 3 | exit 1 |
| 未关闭 Open Questions | ≤ 2 | exit 1 |
| Edge（SPEC 与/或 ACCEPTANCE） | ≥ 3 | exit 1 |
| 不可测/含糊措辞 | 0 hit | exit 1 |
| 模板占位符残留 | — | WARN |
| 用户批准签字 | — | WARN only（必须人确认） |
| 合规/发布边界（维 8）是否出现 | — | WARN |

退出码：`0` 通过 · `1` 未通过 · `2` 参数/文件错误。

### Agent 约定

- 输出 `SPEC READY` **之前**应运行本脚本；失败则不得声称 DoR 通过。
- 脚本 PASS ≠ 可以写码；仍须用户回复批准。

## 后续（未实现）

| 脚本 | 用途 |
|------|------|
| （可选）hook 集成 | 未出现哨兵句前拦截 Write |
| （可选）check-diff-secrets | Gate C 辅助扫密钥 |

原则：生成 Agent ≠ 校验脚本；脚本失败必须阻断。
