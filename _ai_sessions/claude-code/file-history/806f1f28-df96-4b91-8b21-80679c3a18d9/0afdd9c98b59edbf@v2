# TK 广告采集 · 中心化改造方案

> 目标：现有「紫鸟抓取 → 直写飞书」改为「紫鸟抓取 → **清泉中心** → 飞书」  
> 原则：**旁路上报、开关切换、不打断 17:20 生产任务**

源项目：`E:\project\海外TK店铺广告投流数据自动化监测`

---

## 1. 现状链路

```
计划任务 17:20
  → run-multi-store.ps1
      → ziniao store open / page exec (scrape-ads-page.js)
      → 直接 Feishu batch_create
      → daily-analysis.ps1 → 本地日报
```

并行：Chrome 扩展 Popup / alarms → service-worker → feishu/bitable.js

**问题：** 飞书为事实源、仅 append 易重复、无任务引擎、数据不进企业库。

---

## 2. 目标链路

```
计划任务 17:20
  → run-multi-store.ps1
      → ziniao 抓取（不变）
      → [新] POST 清泉 /api/v1/ingest/tiktok_ads
      → [开关] 可选仍直写飞书（过渡）
      → daily-analysis 可改为读中心 API（Phase1 后）

中心
  → 幂等落 fact_ads_campaign_daily
  → Outbox → 飞书 Sync（create/update，按映射表）
  → 规则（低 ROI 等）→ anomaly/task（可二期）
```

扩展路径同步：service-worker 写飞书前先 report 中心。

---

## 3. 改造阶段

### Stage A — 旁路上报（推荐先做，零停机）

| 项 | 做法 |
|----|------|
| 配置 | `stores.config.json` 增加 `qingquan` 节点 |
| PS | 抓取成功后调用 `Report-ToQingquan`；失败打日志 **不阻断** 原飞书写入 |
| 扩展 | `DEFAULT_CONFIG` 增加中心 URL + API Key；先 report 再 feishu |
| 中心 | Phase0 Ingest 已就绪 |
| 飞书 | 仍由 TK 脚本直写（双写） |

**验收：** 中心库有当日广告行；飞书与现网一致；中心挂掉不影响飞书。

### Stage B — 中心同步飞书

| 项 | 做法 |
|----|------|
| 中心 | 配置 TK 多维表 app_token/table_id；Sync Worker 开启 |
| 映射 | 用 `biz_date+storeId+campaign` 做业务键生成稳定 local_id/hash |
| 开关 | `feishu.writeMode = "center"` 时 PS/扩展 **停止直写** |
| 去重 | 首次切流前跑「重建同步」作业，按业务键绑定已有 record_id（或清空测试表） |

**验收：** 同日重跑不产生重复飞书行；改 spend 后飞书数值更新。

### Stage C — 收尾

- 日报改为中心 API 聚合（或 SQL）生成  
- 低 ROI / 零销花费 → 自动 task  
- 扩展 alarms 降级为开发调试，生产只保留 schtasks  
- 密钥仅留在中心与采集配置，去除 dist with-secrets 包

---

## 4. 配置变更

### 4.1 `config/stores.config.json` 增加

```json
{
  "qingquan": {
    "enabled": true,
    "baseUrl": "http://127.0.0.1:8000",
    "apiKey": "dev-ingest-key",
    "source": "tiktok_ads",
    "failOpen": true,
    "timeoutSec": 30
  },
  "feishu": {
    "writeMode": "direct",
    "comment": "direct | center | dual"
  }
}
```

| writeMode | 行为 |
|-----------|------|
| `direct` | 仅直写飞书（现状） |
| `dual` | 中心 + 直写（Stage A） |
| `center` | 只上报中心，飞书由中心同步（Stage B） |

### 4.2 扩展 `DEFAULT_CONFIG` 增加

```js
qingquan: {
  enabled: false,
  baseUrl: "",
  apiKey: "",
  failOpen: true,
}
```

options 页增加表单项，存 `chrome.storage.local`。

---

## 5. 上报报文映射

现网 `normalizeRow` → Ingest envelope：

```json
{
  "source": "tiktok_ads",
  "platform": "tiktok",
  "shop_id": "<紫鸟 storeId>",
  "shop_name": "<storeNameMap 展示名>",
  "biz_date": "2026-07-26",
  "collected_at": "2026-07-27T17:25:01+08:00",
  "idempotency_key": "tiktok_ads:27501502216807:拖把7/13:2026-07-26",
  "payload": {
    "campaign_name": "拖把7/13",
    "spend": 187.79,
    "orders": 121,
    "roi": 9.9,
    "revenue": 1872.64,
    "row_status": "success",
    "source_url": "https://seller-uk.tiktok.com/...",
    "currency": "GBP"
  }
}
```

**批量：** 一店多系列时用

```http
POST /api/v1/ingest/tiktok_ads
Content-Type: application/json
X-Api-Key: ...

{
  "items": [ { /* envelope without source */ }, ... ]
}
```

中心对每个 item 独立幂等。

**汇总行：**  
- Stage A：仍可由 PS 写飞书 `【店铺汇总】`  
- Stage B：中心根据事实表聚合后同步，PS 不再写汇总

---

## 6. 代码改动清单（补丁级）

### 6.1 新建 `scripts/qingquan-client.ps1`

```powershell
function Send-QingquanIngest {
  param($Config, $Items)
  if (-not $Config.qingquan.enabled) { return @{ ok = $true; skipped = $true } }
  $headers = @{
    "X-Api-Key" = $Config.qingquan.apiKey
    "Content-Type" = "application/json"
  }
  $url = "$($Config.qingquan.baseUrl)/api/v1/ingest/$($Config.qingquan.source)"
  try {
    $body = @{ items = $Items } | ConvertTo-Json -Depth 8 -Compress
    $resp = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $body -TimeoutSec $Config.qingquan.timeoutSec
    return @{ ok = $true; resp = $resp }
  } catch {
    if ($Config.qingquan.failOpen) {
      Write-Warning "qingquan ingest failed: $_"
      return @{ ok = $false; error = "$_" }
    }
    throw
  }
}
```

### 6.2 修改 `scripts/run-multi-store.ps1`

在「单店 scrape 成功 → 写飞书」之间插入：

```powershell
# 1) 组装 $qingquanItems（字段按字典）
# 2) Send-QingquanIngest -Config $cfg -Items $qingquanItems
# 3) switch writeMode:
#      direct/dual → 原 Write-FeishuRecords
#      center     → 跳过直写
```

保持：失败重试、关店、日报逻辑不变。

### 6.3 修改扩展

| 文件 | 改动 |
|------|------|
| `lib/constants.js` | DEFAULT_CONFIG.qingquan |
| `options/*` | 中心配置 UI |
| `background/service-worker.js` | `reportQingquan(rows)`；按 writeMode 分支 |
| `feishu/bitable.js` | 不删，center 模式跳过调用 |
| 新建 `lib/qingquan.js` | fetch ingest + 错误 failOpen |

### 6.4 中心侧（本仓库）

| 文件 | 改动 |
|------|------|
| `backend/.../ingest.py` | 解析 tiktok_ads items → UPSERT fact |
| `migrations` | `fact_ads_campaign_daily` |
| `jobs/sync_feishu.py` | 表键 `tk_ads_daily` |
| 字段别名 | 与现网一致：日期/店铺/店铺ID/品名/花费/销量/ROI/销售额… |

### 6.5 不改动（Stage A）

- `scrape-ads-page.js` 抓取逻辑  
- ziniao 开店/关店  
- `install-daily-task.ps1` 时间  
- `daily-analysis.ps1`（Stage C 再改）

---

## 7. 幂等与去重

| 层 | 键 |
|----|----|
| Ingest | `tiktok_ads:{storeId}:{campaign}:{biz_date}` |
| PG UPSERT | `UNIQUE(shop_id, campaign_name, biz_date)` |
| 飞书 | `sync_feishu_map` + content_hash；或飞书侧预建「业务键」文本列供对账 |

同日重跑：PG 更新数值；飞书 update 同行。

---

## 8. 回滚方案

1. `qingquan.enabled=false` → 回到纯直写  
2. `writeMode=direct` → 停止依赖中心同步  
3. 中心故障 + `failOpen=true` → 采集与直写不受影响  
4. 保留 `logs/multi-store-*.json` 可补报中心：`scripts/replay-to-qingquan.ps1`（建议 Stage A 一并做）

---

## 9. 安全

- API Key 仅配置在 `stores.config.json`（已 gitignore）与扩展 storage  
- 中心 Ingest 仅内网或 mTLS/IP 白名单  
- 切 Stage B 前轮换曾进入 `dist/*with-secrets*` 的飞书 Secret  
- 日志禁止打印 apiKey / appSecret  

---

## 10. 实施顺序（建议 3–5 天）

| 日 | 任务 |
|----|------|
| D1 | 中心 fact 表 + ingest 解析 tiktok_ads；本地 mock 通过 |
| D2 | qingquan-client.ps1 + run-multi-store 旁路；dryRun 联调 |
| D3 | 扩展 qingquan.js + options；单店 Popup 验证 |
| D4 | 17:20 灰度 dual 一天；对账 PG vs 飞书 |
| D5 | （可选）Sync Worker + 测试表 center 模式；生产 dual 观察 |

生产切 `center` 建议单独变更窗口，先克隆飞书表做影子同步 3 天。

---

## 11. 对账 SQL 示例

```sql
-- 某日中心汇总
SELECT shop_name, COUNT(*), SUM(spend), SUM(revenue)
FROM fact_ads_campaign_daily f
JOIN shop s ON s.id = f.shop_id
WHERE biz_date = DATE '2026-07-26'
GROUP BY 1;
```

与 `日报/日报-2026-07-26.json` 的 `storeRollups` 对比 spend/orders/revenue。

---

## 12. 验收清单

- [ ] dual 模式：中心与飞书行数、金额一致（汇总行策略已约定）  
- [ ] 同日重跑：PG 行数不变，数值可更新  
- [ ] 中心停机 + failOpen：飞书仍写入  
- [ ] center 模式：关闭直写后飞书仍由 Worker 更新  
- [ ] 密钥不出现在日志与公开 zip  
- [ ] 原 17:20 任务无需改触发器  

---

## 13. 后续（Phase 1+）

- 低 ROI / 零销花费自动建任务并推智能体  
- 日报 md 改为中心出  
- 欧盟/英区 URL 与 shop 主数据统一由中心下发，减少本地 config 分叉  
