---
name: no-channel-manual-assign
description: 无渠道包裹策略为人工在赛狐指派，不自动用 SKU 克重选渠道
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fcfa19b-fda8-4c80-8774-769aa775d09a
  modified: 2026-07-21T06:40:08.860Z
---

金猫 sellfox-bridge：无渠道单由人工在赛狐「待处理」指派渠道（2026-07-21 确认）。

**Why:** 无渠道占比低；避免强依赖未维护的 sku_weights/价卡；与 keep_existing_channel 第一期策略一致。

**How to apply:**
- 无渠道 → 告警/FAILED，不自动 selector 指派（业务上按人工补渠道理解）
- 人工补渠道后下一轮 dry-run/运行应「保留已有渠道」
- sku_weights 仅作以后称重回传兜底，观察期可不填
- 相关记录：[[对齐记录见仓库 对齐记录_业务语义.md]]
