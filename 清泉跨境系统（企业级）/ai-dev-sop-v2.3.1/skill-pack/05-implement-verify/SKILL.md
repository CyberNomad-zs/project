---
name: implement-verify
description: >
  AI 开发 SOP 子技能：按批准的 MVP + ARCH + Plan 实现与验证。
  仅由总控 ai-dev-sop 在 PHASE 6 加载；不要单独作为主入口。
disable-model-invocation: true
metadata:
  parent: ai-dev-sop
  phase: "6"
---

# 05 — Implement + Verify

由总控在 **PHASE 6** 加载。前提：Gate A 已批；Gate B 已批或 N/A。

## 规则

1. 贴合 **MVP + ARCH + Plan**  
2. 范围外 → 停；补批对应节点制品  
3. 小步实现；对照 ACCEPTANCE MVP Demo  
4. 遵守 G0–G3  
5. 禁止密钥、吞错、顺手大重构  

完成后 → PHASE 7：`$SOP_ROOT/skill-pack/06-review-ship/SKILL.md`。
