# PROGRESS — TK 整站采集

## 口径
整站有用运营数据。广告日更由**同事本机定时**承担。

## 2026-07-31 Bridge 恢复后实跑（生产）

### 数据快照
| 域 | 结果 |
|----|------|
| **订单** | **~582 行，null_biz≈0**（仅删掉 smoke 测试单）；future=0；时间粘连解析生效 |
| **商品** | Gardena **~104**（2 页翻页 +48），Deal **~55**；多数有 price |
| **shop_daily** | Gardena + Deal 均有（首页近 7 天卡片） |
| **health_daily** | Gardena + Deal 均有（health-center） |
| **finance_daily** | Gardena + Deal 均有 |

### 本轮关键
1. **订单翻页**：`orders-click-next.js` 与 products 同逻辑（arco/页码+1）→ Gardena **8 页 400 行**
2. **商品翻页**：Gardena 50→**98**；Deal 50→**51**
3. **shop-modules 全通**：homepage / health-center / finance，单条 ingest `dup/accepted` 正常
4. **粘连时间**：`订单号+今天/分钟前` 可解析；Deal null_biz=0

### 入口
```powershell
cd collectors/tiktok-ads
.\scripts\run-orders.ps1
.\scripts\run-products.ps1
.\scripts\run-shop-modules.ps1
```

### 日更任务矩阵（采集机 Windows）
| 任务 | 默认时间 | 安装脚本 |
|------|----------|----------|
| 广告 | 17:20 | `install-daily-task.ps1`（同事机已有） |
| 店 KPI/健康/财务 | 19:45 | `install-shop-modules-daily-task.ps1` |
| 订单 | **20:00** | `install-orders-daily-task.ps1` |
| 商品 | **20:20** | `install-products-daily-task.ps1` |
| 内容+商品卡（经营 P2） | **20:40** | `install-content-daily-task.ps1`（**可选**；业务批后） |
| 联盟达人（经营 P3） | **20:55** | `install-affiliate-daily-task.ps1`（**可选**；含 Pop） |
| 合并链 shop→orders→products | 19:50 | `install-full-site-daily-task.ps1`；可 `-WithContent`/`-WithAffiliate`（勿与拆分同时开） |
| 规则+飞书尾巴（中心机） | **21:00** | 仓库根 `install-tk-p0-post-collect-daily-task.ps1` |

- 文档：`collectors/tiktok-ads/docs/每日定时任务.md`  
- `night-loop.ps1`：ads + shop-modules + orders + products（内容/达人另任务）  
- 商品 open 后 **warm 轮询**（最多 8 次）减轻 Bridge 抖  

### 2026-08-03 实跑验收 + Pop exclude
- **Pop 策略**：`modules.opsExcludeStoreIds=[27758103898326]` + `opsExcludePlatformContains=[欧盟]`；orders/products/shop-modules 共用；**广告仍可采 Pop**；**affiliate 日更不应用 opsExclude**（含 Pop）
- ListOnly：三模块均 `opsExclude removed Pop` → 仅 Deal + Gardena
- shop-modules 全店实跑：6/6 scrape OK；2 次偶发 SSL 已 curl 补写；生产 shop/health/finance 有 **08-02** 日
- products 全店：Deal 76（+26）、Gardena 98（dup 刷新）；warm 轮询生效

### 2026-08-07 采集收尾（产品化）
- ✅ `run-content-daily.ps1` / `install-content-daily-task.ps1`（强制 SkipIngest false；modules=video_list,product_traffic）
- ✅ `run-affiliate-daily.ps1` / `install-affiliate-daily-task.ps1`（enter_center+performance）
- ✅ `run-full-site-daily.ps1 -WithContent -WithAffiliate`
- ✅ post-collect 增加 `tk_affiliate_anomaly_eval`；`feishu-tk-daily-sync.ps1 -AffiliateOnly`
- 生产新鲜度抽查（约 08-07）：shop max~08-05；ads max~08-02（同事机）；content/traffic 有窗；affiliate 单窗偏少 → **装任务或手动日更攒数**

### 可选后续
- 采集机业务批后装 Content/Affiliate 日更；盯 ads 同事机  
- 欧盟 Pop 若广告也要停，再进 `filter.excludeStoreIds`  
- 合 PR
