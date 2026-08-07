# temu-monitor: division of labor & packaging findings

## Current split

| Lane | Where | What | Entry |
|------|-------|------|-------|
| Sellfox delist/onshelf | Fixed-IP Linux server | selectStatus 12 set-diff | `node src/sellfox/cli.js start` / systemd `temu-sellfox` |
| Playwright traffic | Colleague local PCs | 待关注 / 近期下降 / 在售 / multi-store | `npm run once|start` via 启动.bat / gui.py |
| Chrome plugin | (docs say optional/off) | Originally traffic; PLUGIN_PARITY claimed full replace | — |

## Recommendation when restoring plugin traffic

- **KEEP** server sellfox (primary delist/onshelf)
- **RETIRE as primary** local Playwright traffic packaging for colleagues
- **KEEP as fallback/dev** `once`/`start` + code, not day-to-day ops
- **Avoid dual-run** plugin + local traffic (duplicate Feishu)
