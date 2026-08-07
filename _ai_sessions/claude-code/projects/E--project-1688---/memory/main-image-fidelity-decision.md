---
name: main-image-fidelity-decision
description: 1688主图必须精确还原真实产品，不能用AI重画产品
metadata: 
  node_type: memory
  type: project
  originSessionId: b88122c6-fc18-43c5-a7b3-3099a1cd10d8
---

用户决定（2026-07-06）：1688 主图必须**精确还原真实产品**，不允许 AI 重新演绎造型/场景。

**Why:** 灯具目录主图必须与真实产品一致，否则货不对板。冒烟测试证实 grok 图生图会把 A60 灯泡"演绎"成另一种爱迪生灯丝灯——AI 生成会重画产品像素，无法保真。

**How to apply:** 核心白底主图走**非生成式**路线，已在 `src/generate/image.py` 实现（`make_main_image`：提纯近白底+裁切居中+缩放；`is_clean_white_bg` 分类）——规范常量见 `src/generate/specs.py` 与 `docs/主图规范.md`。grok 生成只用于「允许 AI 发挥」的场景图/卖点图，不用于核心白底主图。真实产品图源在 `文件/易之来灯具/<型号>/`，但每个型号目录混有两类图：干净白底产品图(可做主图)与带文字/场景的卖点海报(归详情/卖点，不做主图)。
