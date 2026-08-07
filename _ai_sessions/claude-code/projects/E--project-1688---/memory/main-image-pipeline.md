---
name: main-image-pipeline
description: M1每商品出5张主图的混合分工方案(白底非生成式+场景grok)
metadata: 
  node_type: memory
  type: project
  originSessionId: b88122c6-fc18-43c5-a7b3-3099a1cd10d8
---

用户决定（2026-07-06）：M1 主图走**混合分工**，每个商品产出 **5 张主图**（占满 1688 上限）：
- **2 张白底主图** → 非生成式（`src/generate/image.py` 的 `make_main_image`，真实产品像素保真）
- **2 张场景/卖点主图** → grok 图生图生成（`zapi_client.edit_image`）
- **1 张纯白底主图**（第5张，1688 强制最后一张白底）→ 非生成式

**Why:** 白底主图要绝对保真+纯白（[[main-image-fidelity-decision]]）；场景/卖点主图要氛围感，grok 名正言顺（规划文档 §6-M1 本就要求 grok 生图）。实测：grok 用"强制保持产品外形一致"的严格 prompt 能保住产品身份（之前重画是因 prompt 诱导改造）。

**How to apply:** grok 生成场景图时 prompt 必须强约束"保持产品外形/结构/颜色/比例完全一致，只改背景环境"。所有主图最终套 `specs.py`（800×800 正方形、≤500KB、纯白 RGB、禁词）。待验证：真实产品目录是否每型号都有 ≥2 张干净白底图可做非生成式主图。
