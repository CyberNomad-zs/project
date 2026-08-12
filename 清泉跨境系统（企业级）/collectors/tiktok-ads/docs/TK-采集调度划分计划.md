# TK 采集调度划分计划

> 日期：2026-08-07  
> 状态：**计划定稿（待采集机按表安装）**  
> 关联：[每日定时任务](./每日定时任务.md) · [整站路线图](./TK-整站运营数据采集路线图.md) · 仓库根 `docs/TK-整体开发计划.md`

---

## 0. 目标与约束

### 目标

1. **每天 17:20 必交一份广告日报**（已确定，同事机 / `TK-Ad-Daily-Report`）。  
2. **夜间整站**：把「当日要看的经营事实」一次采齐 → 规则 → 飞书。  
3. **白天空闲轮巡**：只补「变化快、幂等好」的域，不抢 17:20、不刷飞书。

### 硬约束

| # | 约束 |
|---|------|
| C1 | 紫鸟 **同时只跑一路** 开店/抓页；多任务必须错开 |
| C2 | **17:00–17:40** 为广告日报保护区（停轮巡、不开整站） |
| C3 | 生产事实以 **PG** 为准；飞书只经 post-collect / `feishu_tk_daily_sync` |
| C4 | 内容/达人页是 **近 7 天窗口**，一天 1 次主交数即可 |
| C5 | 投流/寄样金额 **禁止填 0**；affiliate **不**套 `opsExclude`（含 Pop） |
| C6 | POC（`run-*-poc`）默认 SkipIngest，**禁止**直接挂计划任务 |
| C7 | post-collect / 飞书：**不要**按轮巡心跳跑（配额 + 无收益） |

### 划分原则（一句话）

| 类型 | 放哪 | 判据 |
|------|------|------|
| **交数型 / 重 / 窗口型** | 夜间整站 · 固定钟点 | 要「今天有数」、全店翻页久、近 N 天窗 |
| **变化快 / 幂等增量** | 白天空闲轮巡 | 订单为主，商品次之 |
| **已钉死交数点** | 仅该点 | 广告 17:20 |
| **中心计算** | 夜间尾巴 · 不抢紫鸟 | 规则 + 飞书 |
| **研发探针** | 仅人工 | matrix / deep / 默认 SkipIngest 的 POC |

---

## 1. 总览时间表（推荐默认）

```text
┌─ 白天空闲轮巡（Bridge up 才跑）─────────────────────────────┐
│  09:00 ──16:50   night-loop 形态（见 §3）                     │
│                  主 orders · 次 products · 少 shop-modules     │
│                  SkipAds · 无 post-collect                     │
│  17:00 ──17:40   【保护区】停轮巡，给广告日报让路               │
└──────────────────────────────────────────────────────────────┘

┌─ 固定交数 + 夜间整站 ───────────────────────────────────────┐
│  17:20           广告日报 TK-Ad-Daily-Report（同事机）        │
│  19:45           店 KPI/健康/财务  TK-Shop-Modules-Daily      │
│  20:00           订单              TK-Orders-Daily            │
│  20:20           商品              TK-Products-Daily          │
│  20:40           内容+商品卡       TK-Content-Daily（可选装） │
│  20:55           联盟达人          TK-Affiliate-Daily（可选） │
│  21:00           规则+飞书         TK-P0-Post-Collect（中心机）│
└──────────────────────────────────────────────────────────────┘

  备选：不用拆分五段时，19:50 起 TK-Full-Site-Daily
        （shop→orders→products ± WithContent/WithAffiliate）
        与拆分任务【勿同时开】；21:00 尾巴仍建议单独装
```

**机器分工**

| 机器 | 跑什么 |
|------|--------|
| 紫鸟 Windows 采集机 | 17:20 广告（若同机）+ 夜间整站紫鸟段 + 白天轮巡 |
| 中心机（可连 PG+飞书） | **仅** 21:00 `tk-p0-post-collect`（及手工补推飞书） |
| 同事广告机 | 若广告不在采集机：只保证 17:20 日报 |

---

## 2. 脚本归属矩阵

### 2.1 夜间整站（一次交齐）

| 脚本 / 任务名 | 默认时刻 | 写入 | 优先级 | 备注 |
|---------------|----------|------|--------|------|
| `run-daily-report` → `TK-Ad-Daily-Report` | **17:20** | 飞书日报 + 宜双写 PG ads | **P0 钉死** | 不纳入「整站链」拼接，独立任务 |
| `run-shop-modules-daily` | 19:45 | shop/health/finance → PG | P0 | 错开广告 |
| `run-orders-daily` | 20:00 | orders → PG | P0 | 夜间再交一版全日 |
| `run-products-daily` | 20:20 | products → PG | P0 | 全店翻页重 |
| `run-content-daily` | 20:40 | content + traffic → PG | P1 | 业务批后装；强制入库 |
| `run-affiliate-daily` | 20:55 | affiliate shop+creator → PG | P1 | 含 Pop；强制入库 |
| `run-full-site-daily` | 19:50 档 | 上三者合并 | P0 备选 | 可 `-WithContent -WithAffiliate`；**勿与拆分并行** |
| `tk-p0-post-collect` | **21:00** | 规则 + T1/T2/T6/T7/异常 | P0 | **中心机**；含 affiliate 规则 |

**夜间整站成功标准（DoD）**

- [ ] 广告：日报任务 exit=0 或同事机确认；PG `fact_ads_campaign_daily` 最新 biz ≥ 昨天  
- [ ] shop_daily / orders / products：主配置店有当日或约定业务日行  
- [ ] 若已装 content/affiliate：对应 fact 有新窗锚点  
- [ ] post-collect exit=0；飞书 T1/T2（及 T6/T7）无大面积 failed  
- [ ] 日志：`logs/*-daily-*.log`、`logs/tk-p0-post-collect-*.log` 可追溯  

### 2.2 白天空闲轮巡

| 脚本 | 是否进入 | 建议间隔 | 说明 |
|------|:--------:|----------|------|
| `run-orders.ps1` | ✅ **主** | 30～60 min | 变化快、UPSERT 幂等、补漏价值最高 |
| `run-products.ps1` | ✅ 次 | 60～120 min 或隔轮 | 库存敏感；全店重，勿过密 |
| `run-shop-modules.ps1` | ⚠️ 少 | **≤2～3 次/日**（如 10:30、14:30） | 昨日/近 N 日卡片，狂刷收益低 |
| `run-multi-store` / 广告 | ❌ 默认否 | — | **只认 17:20**；事故才手工补采 |
| `run-content-daily` | ❌ 默认否 | 失败补 **1** 次 | 窗口型，交给夜间 |
| `run-affiliate-daily` | ❌ 默认否 | 失败补 **1** 次 | 同上 + 子域 CTA |
| `tk-p0-post-collect` | ❌ | 固定 21:00 | 可选早班 **09:30 补推 1 次**（仅当夜间失败） |
| `run-*-poc` / matrix / deep / click-poc | ❌ | 仅人工 | 研发 |

**白天轮巡成功标准**

- [ ] 17:00 前自动停或人工不启动，不与 17:20 冲突  
- [ ] Bridge down 时跳过，不打爆日志误报为采集失败  
- [ ] 无每轮飞书同步  
- [ ] 订单/商品有增量或 dup 刷新，而非长期 0 店  

### 2.3 明确不进调度的脚本

| 脚本 | 用途 | 调度 |
|------|------|------|
| `run-content-poc.ps1` | POC/单店补采 | 手工 `-SkipIngest:$false` |
| `run-affiliate-poc.ps1` | 同上 | 同上 |
| `run-video-url-matrix.ps1` 等 | URL/门禁研发 | 手工 |
| `run-content-click-poc` / `run-video-details-deep` | 点进深挖 | 手工 |
| `daily-analysis.ps1` | 日报分析（非整站采） | 按原日报文档，不并入本计划轮巡 |

---

## 3. 白天轮巡推荐命令（采集机）

载体：已有 `scripts/night-loop.ps1`（间隔循环 + Bridge 检测）。

### 3.1 推荐：订单+商品+偶尔店模块（默认 Skip 广告）

```powershell
cd collectors\tiktok-ads

# 间隔 30min；不跑广告；不跑 post-collect
# 注意：请在 17:00 前停掉本进程（任务计划结束时间或人工）
powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1 `
  -SkipAds `
  -IntervalSec 1800
```

### 3.2 更轻：几乎只跑订单

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\night-loop.ps1 `
  -OrdersOnly `
  -IntervalSec 1200
```

### 3.3 不推荐的白天参数

```text
❌ 不带 -SkipAds          → 与 17:20 抢店、双通道广告
❌ -RunPostCollect        → 每 15～30 分钟打飞书/规则
❌ IntervalSec 过小（<600）且全模块全开 → 紫鸟打满、页面风控
```

### 3.4 与计划任务的互斥

| 若已安装 | 白天 loop 应 |
|----------|----------------|
| 拆分 Orders/Products 日更 | 可继续 loop（幂等）；接受「晚间再全量」 |
| Full-Site 19:50 | 16:50 停 loop 即可 |
| 未装任何日更 | **必须**至少装夜间整站或手工晚间 full-site，单靠白天 loop 不够交内容/达人/飞书 |

---

## 4. 夜间整站安装清单（采集机 + 中心机）

### 4.A 方案 A — 拆分（推荐排障）

在 **紫鸟采集机** `collectors\tiktok-ads`：

```powershell
# 广告若在本机（同事机已有则跳过）
# powershell -File .\scripts\install-daily-task.ps1 -Time "17:20"

powershell -File .\scripts\install-shop-modules-daily-task.ps1 -Time "19:45"
powershell -File .\scripts\install-orders-daily-task.ps1 -Time "20:00"
powershell -File .\scripts\install-products-daily-task.ps1 -Time "20:20"

# 业务批准后：
powershell -File .\scripts\install-content-daily-task.ps1 -Time "20:40"
powershell -File .\scripts\install-affiliate-daily-task.ps1 -Time "20:55"
```

在 **中心机** 仓库根：

```powershell
powershell -File .\scripts\install-tk-p0-post-collect-daily-task.ps1 -Time "21:00"
```

### 4.B 方案 B — 合并链

```powershell
# 先卸载 Shop/Orders/Products 三个拆分任务，再：
powershell -File .\scripts\install-full-site-daily-task.ps1 -Time "19:50"
# 内容/达人：要么装独立 20:40/20:55，要么改 full-site 包装传入 -WithContent -WithAffiliate
# （若 install-full-site 未透传开关，用拆分 content/affiliate 任务更简单）
```

中心机 21:00 post-collect 同 4.A。

### 4.C 白天 loop 计划任务（可选）

| 项 | 建议 |
|----|------|
| 任务名 | 如 `TK-Daytime-Idle-Loop` |
| 触发 | 每天 09:00 启动 |
| 结束 | 16:50 终止进程 / 或脚本内壁钟判断（**当前 night-loop 无结束钟点，需外部结束或后续加参**） |
| 操作 | §3.1 命令 |
| 与 17:20 | 必须 16:50 前停 |

> 缺口（已知）：`night-loop.ps1` **尚无** `-UntilTime 16:50` / `-SkipContent` 等参数。  
> **本期计划**：用「计划任务结束时间」或人工停；若要脚本自治，另开一小改（见 §7）。

---

## 5. 决策树（新脚本往哪挂）

```text
新采集脚本？
  ├─ 是否仅研发/门禁？ → 手工，不进调度
  ├─ 是否 17:20 广告日报链路？ → 固定点，唯一
  ├─ 是否中心规则/飞书？ → 夜间 post-collect，不进紫鸟轮巡
  ├─ 是否近 N 天窗口快照（内容/达人）？ → 夜间 1 次 daily
  ├─ 是否全店重翻页（商品/大批订单）？ → 夜间主交 + 白天低频补
  └─ 是否高频变化且幂等（订单）？ → 白天轮巡主路径 + 夜间再交
```

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 白天 loop 拖进 17:20 | 16:50 硬停；保护区 17:00–17:40 |
| 拆分 + full-site 双开 | 文档红线；安装时互斥检查 |
| content/affiliate 未装导致 D3/D4 空 | 业务批后装；或夜间手工 `run-*-daily` |
| post-collect 每轮跑 | 禁止 loop `-RunPostCollect`；只 21:00 |
| ads PG 陈旧（同事机断） | 新鲜度告警；事故补采 `run-multi-store`，不改划分 |
| Pop 欧盟 | shop/orders/products 可 exclude；**affiliate 含 Pop** |
| 飞书配额 | 日更 sync 1 次为主；ContentOnly/AffiliateOnly 仅补推 |

---

## 7. 实施阶段

| 阶段 | 动作 | 完成定义 |
|------|------|----------|
| **S0 已具备** | 各 `run-*-daily` / install / post-collect / night-loop 脚本在仓库 | 文档与脚本齐（2026-08-07） |
| **S1 采集机** | 按 4.A 或 4.B 安装夜间任务；确认 17:20 广告在 | schtasks 列表与试跑 log |
| **S2 中心机** | 21:00 post-collect | 次日 T1/T2/异常有更新 |
| **S3 白天** | 09:00–16:50 loop `-SkipAds`（外部结束） | 不与 17:20 冲突；orders 有白天刷新 |
| **S4 可选** | 装 Content/Affiliate 日更 | D3/D4 连续窗 |
| **S5 可选增强** | `night-loop` 增加 `-UntilTime`、默认文档化白天预设 | 无需外部杀进程 |

**不在本计划内：** 广告创意细粒度、AI 素材、投流/寄样金额、把 POC 改成默认入库。

---

## 8. 一页纸对照（给值班）

| 时段 | 做什么 | 不做什么 |
|------|--------|----------|
| 09:00–16:50 | 空闲：orders（主）、products（次）、shop 少次 | 不跑广告主路径；不跑飞书心跳；不跑 POC |
| 17:00–17:40 | 停紫鸟其它任务 | — |
| **17:20** | **广告日报** | 其它开店 |
| 19:45–20:55 | 夜间整站（店→单→品→内容→达人） | 不开第二路紫鸟 |
| **21:00** | 规则 + 飞书（中心） | 不依赖紫鸟 |
| 深夜 | 可选 loop 兜底且 SkipAds、无 post | 不与次日 09:00 配置打架 |

---

## 9. 相关路径速查

```text
collectors/tiktok-ads/scripts/
  run-daily-report.ps1 / install-daily-task.ps1          # 17:20 广告
  run-shop-modules-daily.ps1 / install-shop-modules-...
  run-orders-daily.ps1 / install-orders-daily-task.ps1
  run-products-daily.ps1 / install-products-daily-task.ps1
  run-content-daily.ps1 / install-content-daily-task.ps1
  run-affiliate-daily.ps1 / install-affiliate-daily-task.ps1
  run-full-site-daily.ps1 / install-full-site-daily-task.ps1
  night-loop.ps1                                         # 白天轮巡载体
  run-*-poc.ps1                                          # 仅手工

仓库根 scripts/
  tk-p0-post-collect.ps1
  install-tk-p0-post-collect-daily-task.ps1
  feishu-tk-daily-sync.ps1
```

---

**签署用途：** 采集机排班 / 计划任务安装对照 / 与「只改代码不装任务」的边界说明。  
**变更：** 若 17:20 改点或广告迁机，先改 §1 时间表与 C2 保护区，再改 install 默认时刻。
