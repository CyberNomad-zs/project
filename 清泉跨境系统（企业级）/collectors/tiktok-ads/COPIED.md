# 本目录说明（副本）

| 项 | 内容 |
|----|------|
| 来源 | `E:\project\海外TK店铺广告投流数据自动化监测` |
| 复制日期 | 2026-07-29 |
| 位置 | `清泉跨境系统（企业级）/collectors/tiktok-ads` |
| 原则 | **只在本副本上改**；不要回写/覆盖源项目 |

## 复制范围

- 已包含：`extension/`、`scripts/`、`config/`、`docs/`、`gui.py`、启动器等  
- 已排除：`__pycache__`、`.git`、`.playwright-mcp`、`node_modules`

## 安全提示

`dist/` 中若存在带 `with-secrets` 的压缩包，含密钥风险，**勿提交 Git、勿外传**。后续改进请用无密钥配置（`stores.config.example.json` + 本机 `stores.config.json`）。

## 与清泉中心

- 旁路上报：见 `scripts/qingquan-client.ps1`、`config/stores.config.example.json` 中 `qingquan`  
- 中心 Ingest：`POST /api/v1/ingest/tiktok_ads`（广告）、`POST /api/v1/ingest/tiktok_orders`（订单 P2a）  
- 改造方案文档：仓库根 `docs/TK中心化改造方案.md`  
- **整站路线图**：`docs/TK-整站运营数据采集路线图.md`（广告只是第一域）

## 后续改进

### 已做

1. **P0 dual**：`qingquan-client.ps1` + multi-store 旁路上报；`writeMode=dual`  
2. **P1 同页扩列**：预算/目标ROI/净成本/CPA/状态 + 原有核心字段  
3. **中心库**：`003_tiktok_ads_p1_fields.sql`；**订单** `005_tiktok_orders.sql`  
4. **API 常驻脚本**（仓库根）：`scripts/start-api.ps1` 等  
5. **整站 P2a 骨架**：`scrape-orders-page.js` + `run-orders.ps1` + ingest `tiktok_orders`  
6. **飞书**：运营表「TK广告日报」`tblmr3ayTmWF3G7J`（本机 config，勿提交）

### 已知阻塞

- **欧盟店 Pop/Gardena**：代理易断 / about:blank  
- 订单表头需紫鸟实页校准（脚本用别名匹配，未实抓前可能 0 行）  
- 部分英区店页加载慢时需重试（ads 已加强 reopenOnBlank）

### 待做

1. 紫鸟在线：ads 日更 + orders 实页校准  
2. P2b 商品 / P2c 店级 KPI / P3 健康·财务  
3. `stores.config.json` 勿提交密钥  
4. 扩展路径旁路上报清泉  
