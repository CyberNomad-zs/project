---
name: traffic-plugin-primary
description: 2026-07-31 起日常流量用 Chrome 插件 v14，上下架服务器赛狐，本机 Playwright 流量退役
metadata: 
  node_type: memory
  type: project
  originSessionId: ad6ff4ce-4a19-4911-88e9-23af5c453e9e
  modified: 2026-08-06T10:43:01.877Z
---

主路径（2026-07-31 定）：

| 通道 | 职责 |
|------|------|
| **temu-plugin v19.3+**（同事日常 Chrome） | 限流分级（VIP/JM+热销）+ **在售 A+B 上下架兜底**（count 按 mallId 归属 + 防抖确认数量 + 清单点名；上架二次确认；6h 冷却）+ 09:30/16:30 汇总列链接；切店限流静默吸收 |
| **服务器 temu-sellfox** | 赛狐 `selectStatus=12` 上下架（可能滞后于 Temu 后台） |
| **本机 Playwright temu-monitor** | 代码保留作应急/DOM 回归；**停发** traffic-local 给同事日常；勿与插件双开 |

插件 bgVersion：`v19.3-mallId绑店`；manifest `0.2.8`。升级须 chrome://extensions **关开开关**重建 SW。

分发包：`temu-plugin-v19.3-mallId绑店.zip` 或加载已解压 `temu-plugin/`。

**Why:** 本机第二套 `.userdata` Chrome 与日常同账号双端易互踢。2026-08-06 实锤赛狐对平台下架不同步（茶蜡 SKC 7636599333 后台已下架仍 12）→ v19 插件以 agentseller 后台为兜底，卡片标「插件·后台」；赛狐保留作服务器通道。限流逻辑仍 v15–v18。v19.2 防抖不够；v19.3 根因是切店串店（inject mallId 未转发，DOM 店名滞后把 A 店 count 记到 B）。
**How to apply:** 同事装 v19.3 + 关开开关；服务器 sellfox 不动。改监测优先 `temu-plugin/`。相关 [[temu-plugin-versions]] [[sellfox-server-deploy]] [[temu-monitor-project]]。
