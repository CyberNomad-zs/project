---
name: sellfox-server-deploy
description: 赛狐上下架监测部署到清泉固定公网 IP 服务器（解决白名单）
metadata: 
  node_type: memory
  type: project
  originSessionId: 2fcab51f-d98e-4a95-a0bd-c99cd9b9b50b
  modified: 2026-07-30T09:14:45.860Z
---

2026-07-30 已上线。

服务器：腾讯云新加坡 `43.156.50.38` / `qingquan.jmzlai.com`
- SSH：`ssh -i E:\project\清泉跨境系统（企业级）\keys\qingquan_sg_ed25519 ubuntu@43.156.50.38`（或别名 `qingquan-sg`）
- 安装目录：`/opt/temu-monitor`，系统用户 `temu`
- systemd：`temu-sellfox`（enabled + active），每 15 分钟一轮
- 出口 IP = `43.156.50.38`（已在赛狐白名单；probe 成功）
- 首轮基准：Agnis 13 / HomeCove 15 / Twilight Cove 13；第二轮「本轮无上下架」
- 日志：`journalctl -u temu-sellfox -f` 或 `/opt/temu-monitor/data/monitor.log`
- 偶发 `40019` 限流，代码退避重试可过

本机/同事隔离（重要）：
- `config.fullRun` **默认 false** → `npm run once/start` **只跑浏览器流量**，不调赛狐
- 同事电脑不要放 `sellfox.config.json`、不要开 fullRun
- 上下架只在服务器 `sellfox` 服务；联调全量才用 `FULL_RUN=1`

部署包：`temu-monitor/deploy/`（pack-sellfox.ps1 / install-sellfox-linux.sh / sellfox.service / README-SERVER.md）

**Why:** 固定出口免反复申白名单；避免同事本机无白名单报错。
**How to apply:** 更新后 pack → scp zip+config → install → `systemctl restart temu-sellfox`。见 [[sellfox-delist-monitor]]。
