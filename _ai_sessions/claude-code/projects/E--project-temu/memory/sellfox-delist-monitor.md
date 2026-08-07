---
name: sellfox-delist-monitor
description: temu-monitor 基于赛狐 OpenAPI 的 Temu 下架监测
metadata: 
  node_type: memory
  type: project
  originSessionId: a4e09619-43de-4c7b-9c4c-1a79355fc2d2
  modified: 2026-07-31T10:04:15.969Z
---

在 `E:\project\temu\temu-monitor\src\sellfox\` 用赛狐多平台 API 做**上下架**监测（与 sellfox-bridge 共用 client 凭证思路）。

- 接口：`POST /api/multiplatform/temu/product/getParentPageList.json`，`dateType=updateDate`，窗口≤30天滑窗。
- 在售：`selectStatus=12`；已下架常见 `13`。首轮建 `data/sellfox-state.json` 基准不告警。
- **下架** = 上轮在售∖本轮；**上架** = 本轮在售∖上轮（`events.type=onshelf`，绿卡；混合橙）。`alerts.delist`/`onshelf` 默认 true。
- 配置：`sellfox.config.json`（gitignore），shopId 396706/398202/398203。
- 命令：`npm run sellfox:probe|once|start|dry`。限流 40019 需退避。
- 限流/待关注仍用 Chrome 插件；赛狐无流量标签字段。
- 实调：三店在售 13/15/13，unique 父体约 948（30d updateDate）。

- **2026-07-31 误报根因与修复**：`getParentPageList` 偶发漏拉（日志 unique 954→918），HomeCove 在售被算 15→10，飞书假下架 5；下一轮拉全又假上架 5。旧护栏只挡「在售腰斩 50%」。新规则：①全量 unique / 本店 allCount 骤降 skip；②「下架」须本轮 allMap 仍有该 SKC 且 status≠12；③失踪 SKC 当漏数 carry 基准不告警。已部署服务器 + `diff.selftest.js`。见 [[sellfox-server-deploy]]。

**Why:** 半托管店 Partner Local 商品权限不确定；赛狐已授权三店且字段对齐。
**How to apply:** 上下架主路径优先 sellfox 模块；限流继续插件。服务器常驻见 [[sellfox-server-deploy]] / `deploy/README-SERVER.md`。改 diff 后 scp `diff.js`+`monitor.js` 到 `/opt/temu-monitor/src/sellfox/` 并 `systemctl restart temu-sellfox`。
