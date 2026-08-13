# TikTok shop 需求 · 上线验收清单

> 日期：2026-08-12  
> 口径：**只群发**（`TK_NOTIFY_IM=false`）；私信不做  
> 自动检查脚本：`scripts/_prod_acceptance_check.sh`

---

## A. 生产后端（已自动核对 2026-08-12）

| # | 检查项 | 结果 |
|---|--------|------|
| A1 | API `/health` | ✅ ok |
| A2 | `TK_NOTIFY_IM=false` | ✅ |
| A3 | `TK_NOTIFY_WEBHOOK=true` | ✅ |
| A4 | `FEISHU_BOT_WEBHOOK_TK_HEALTH` | ✅ SET |
| A5 | 体验分飞书表 id `tbl9CYd8vb4DJaGN` | ✅ |
| A6 | 代码文件 notify_dual / experience / creator rules | ✅ 在 `/opt/qingquan` |
| A7 | 表行数 experience / creator_health | ✅ **2026-08-12 关口**：真店体验分 3 行（Deal/INOUT/Gardena）；creator 真店弱（INOUT default 仅） |
| A8 | 规则 dry-run 能命中下降 | ✅ 体验分 + 达人 Grace |

**结论 A：** 中心服务与「群提醒 + 体验表 + 规则」链路 **可上线使用**；缺 **真店采集进数**。

---

## B. 采集机（需你在本机/同事机勾选）

前置：紫鸟客户端已登录 + ziniao-cli doctor 通过 + 清泉 ingest 指向 `https://qingquan.jmzlai.com`

### B1 配置

- [x] `collectors/tiktok-ads/config/stores.config.json` 含店铺 filter（三店，无 Pop 特殊排除）  
- [x] 已补 `experienceUrl` / `creatorHealthUrl` 的 **UK + EU byPlatform**（2026-08-12；否则 Pop 误开 seller-uk）  
- [x] `qingquan.enabled=true` 且 baseUrl 生产  

### B2 单店冒烟（推荐先 1 店）

```powershell
cd E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads

# 体验分
powershell -ExecutionPolicy Bypass -File .\scripts\run-shop-modules.ps1 `
  -Modules experience_daily -DryRun false

# 达人健康（含切换账号）
powershell -ExecutionPolicy Bypass -File .\scripts\run-shop-modules.ps1 `
  -Modules creator_health -DryRun false
```

勾选：

- [x] 日志 `module experience_daily` ok（三店 OK；Pop EU URL 后 accepted=1）  
- [ ] 日志 `creator multi-account: switch N account(s)` — **未过**：页面无账号列表 / no creator health  
- [ ] 日志 `with healthScore` 中 X≥1 — **弱**：INOUT 仅 `default` 分数 99（页面解析不稳）  

**2026-08-12 采集汇总（第二轮，补 EU URL 后）：** experience 4/3 店 OK；creator_health 仅 INOUT 弱成功。

**紫鸟注意：** 若出现「网页未予显示 / 申请加白」页（常见跳到 `www.tiktok.com` 消费站），需在紫鸟侧加白或 bypass；成员账号无访问策略 API 权限时需老板/管理员操作。

### B3 日更任务

- [x] 计划任务 `TK-Shop-Modules-Daily` 已装（默认 19:45；wrapper 含 `experience_daily,creator_health`）

---

## C. 数据与飞书（采完再勾）

在生产 PG 或 Navicat（SSH 隧道）执行：

```sql
-- 真店体验分（不应只有 smoke-shop-exp）
SELECT shop_name, biz_date, experience_score, updated_at
FROM tk.fact_tiktok_experience_daily
WHERE shop_external_id <> 'smoke-shop-exp'
ORDER BY updated_at DESC LIMIT 10;

SELECT shop_name, creator_key, biz_date, health_score
FROM tk.fact_tiktok_creator_health_daily
WHERE shop_external_id <> 'smoke-shop-exp'
ORDER BY updated_at DESC LIMIT 20;
```

- [x] 真店体验分行出现（Deal 3.9 / INOUT 4.3 / Gardena 3.8，biz=2026-08-11；三模块分齐全）  
- [ ] 同店 ≥2 个 creator_key — **未过**（仅 INOUT/default）  
- [x] 飞书「体验分日」同步 success：含 Gardena 新建行（scanned=5 created=1 unchanged=4）  

手动 sync（服务器）：

```bash
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python /tmp/run_exp_sync.py
# 若无：用 scripts/_prod_run_exp_sync.py 再 scp
```

---

## D. 群提醒（采完 / 或对 smoke 实跑）

**注意：** 实跑会往业务群发消息，建议先 dry-run，再选非高峰实发。

```bash
# 服务器：样例店会推群（确认群 webhook 正确）
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_experience_anomaly_eval --shop-external-id smoke-shop-exp
# 不要加 --dry-run / --no-notify
```

- [x] 飞书群 webhook HTTP 200；smoke 体验分下降 + 分项变差 **notified=2**（2026-08-12 15:29）  
- [x] **没有**私信（`TK_NOTIFY_IM=false`，`FEISHU_IM_RECEIVE_ID` 未配）  
- [x] 异常任务：`shop_experience_drop` / `shop_experience_metric_worse` open（smoke-shop-exp）

健康分/差评：沿用原日更，群提醒应仍工作。

---

## E. 需求完成度（验收口径）

| 原文需求 | 验收通过条件 | 当前 |
|----------|--------------|------|
| 健康分下降群提醒 | 现网链路 + 群 webhook | ✅ 能力在；靠日更数据 |
| 体验分下降群提醒 | 真店数 + 规则 + 群 | ✅ 真店 3 店有数；群实发 smoke 通过 |
| 达人健康多账号下降提醒 | 多账号采集 + 规则 + 群 | ⚠️ 规则/群能力在；**多账号采集未过** |
| 1–2 星差评提醒 | 现网 reviews | ⚙️ 能力在；库内 review=0 待采 |
| 达人新违规提醒 | creator_violation | ⚠️ 行数 0；随 creator_health 页面 |
| 三模块进飞书表 | 表+sync | ✅ 真店三店已进飞书 |
| 私信宋敏 | — | ❌ **明确不做** |

---

## 一键复检生产

```bash
ssh -i keys/qingquan_sg_ed25519 ubuntu@43.156.50.38 \
  'bash /tmp/_prod_acceptance_check.sh'
```

---

## 建议执行顺序（你）

1. **B2** 本机紫鸟跑体验分 + 达人（1 店）  
2. **C** 查 PG 是否有真店行  
3. **D** 确认群消息（可用 smoke 先测 1 次）  
4. 打开日更任务含新模块  

做完 B2 后把日志关键几行发我，我可以帮你看是否采集成功。
