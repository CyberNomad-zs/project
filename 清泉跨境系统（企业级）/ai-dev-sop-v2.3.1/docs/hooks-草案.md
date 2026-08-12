# Hooks 草案（可选增强 · 非投产阻塞）

> 现状门禁是 **Prompt + 哨兵句 + 人批**。  
> 本文件描述「机械防呆」的推荐方向，**默认未实现**。  
> 实现前勿宣称「系统级不可绕过」。

---

## 目标

| 风险 | Hook 意图 |
|------|-----------|
| 未批 Spec 就写业务代码 | PreToolUse：拦截 Write/Edit |
| 未批 Plan 就大面积改文件 | 同上 + 允许名单 |
| 未批 Diff 就 push | 拦截 `git push` / 危险 Bash |
| 误触 G3 | 匹配路径/命令关键字则拒绝并提示升级 |

---

## 状态机（逻辑）

用会话旁路文件（示例）记录门禁：

```text
docs/specs/.sop-state.json
{
  "spec_approved": false,
  "plan_approved": false,
  "findings_approved": false,
  "diff_approved": false
}
```

人回复「批准」且 Agent 更新状态后，才放行下一档工具。

| 状态 | 允许 |
|------|------|
| 仅启动 | Read、Grep、Glob |
| spec_approved | + 写 `docs/specs/**` 以外仍慎；业务代码仍禁 |
| plan_approved | + 写 Plan 列表内文件 |
| diff_approved | + commit；push 仍建议 G2 再确认 |

> 实现时注意：状态文件被 Agent 自己改写的信任问题 → 应用 **人侧确认命令** 或 IDE 批准 UI 更新状态。

---

## Agent 客户端 PreToolUse（伪代码，按工具能力裁剪）

```text
on PreToolUse(tool, input):
  if tool in [Write, Edit, MultiEdit]:
    if not state.spec_approved and path_is_business_code(input.path):
      return deny("⛔ SPEC not approved — wait for SPEC READY + 人批准")
    if state.spec_approved and not state.mvp_approved and not state.mvp_skipped \
       and path_is_business_code(input.path):
      return deny("⛔ MVP not approved — wait for MVP READY + 人批准")
    if state.mvp_ok and not state.plan_approved and path_is_business_code(input.path):
      return deny("⛔ PLAN not approved — wait for PLAN READY + 人批准")
  if tool == Bash and looks_like_git_push(input.command):
    if not state.diff_approved:
      return deny("⛔ DIFF not approved")
  if tool == Bash and looks_like_g3(input.command):
    return deny("⛔ G3 — escalate to approver")
  return allow
```

---

## 与 check-dor 的关系

| 组件 | 时机 |
|------|------|
| `check-dor.sh` | SPEC READY 前，输入门 |
| Hooks | 写码/push 时，执行门 |
| 人批哨兵句 | 决策门（优先级最高） |

---

## 落地优先级建议

1. **P-hook-1**：仅拦截 `git push` / `git reset --hard`（收益高、误伤少）  
2. **P-hook-2**：未 plan_approved 禁止写 `src/`（按仓配置路径）  
3. **P-hook-3**：G3 命令关键字黑名单  

---

## 明确不在草案范围

- 替代合规审计  
- 保证模型 100% 遵守（无状态机外的旁路仍可能）  
- 多 Agent 分布式锁  

试点投产 **不依赖** 本草案已实现。
