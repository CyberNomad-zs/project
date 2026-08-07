# 亚马逊 ASIN 健康度监控与运营闭环 — 第一期开发计划

## Context

业务目标：把赛狐（Sellfox）里的亚马逊店铺/ASIN 经营数据**每日自动同步到飞书多维表格**，按可配置阈值生成黄/橙/红异常任务，推动负责人处理与复查，并给老板看「异常驾驶舱」——不重做赛狐分析，不算利润，不自动操作亚马逊后台。

当前状态：
- 有完整需求：`亚马逊ASIN健康度监控与运营闭环系统需求说明.docx`
- 有运营填报模板：`日报提交.xlsx` / `日报提交2.xlsx`（人工过渡，非系统代码）
- 有旧版物流向 API 笔记：`赛狐开放API.md`（**不可直接用于驾驶舱**，仅可复用鉴权经验）
- **无应用代码**；官方 OpenAPI 已确认产品分析 V2 等可覆盖大部分一期字段
- 决策已定：**Python**、**飞书多维表格 API 直写**、**先本地联调**、**仅有赛狐凭证（飞书待申请）**

一期范围（验收口径）：
- 赛狐日同步 → 规则配置 → 异常任务 → 提醒升级 → 动作记录 → 老板视图  
- 不含：利润数据、自动运营决策、亚马逊后台操作、AI 日报/周报（二期）

---

## 推荐架构

```text
                    ┌─────────────────┐
  cron / 手动触发   │  Python 服务     │
  (本地先跑)    ──► │  sellfox-feishu  │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    赛狐 OpenAPI        本地 SQLite         飞书开放平台
    productAnalyze V2   (同步日志/         多维表格 API
    FBA库存/评价...     任务幂等/缓存)     机器人消息
           │                 │                 │
           └────────► 规则引擎 ◄───────────────┘
                         │
              异常任务 / 动作表 / 老板视图
```

**原则：**
1. **赛狐只读**：只拉数据，不写赛狐、不改广告/库存。
2. **飞书是业务系统**：底表 + 任务 + 动作 + 配置都在多维表格；人工字段同步时不覆盖。
3. **本地 SQLite 作运行态**：token 缓存、同步批次、接口原始快照（可选）、幂等键，避免飞书偶发失败丢状态。
4. **规则与阈值外置**：存在飞书「配置表」或本地 `config/rules.yaml`，不写死在代码里。
5. **限流意识**：赛狐 **约 1 次/秒**、`pageSize≤100`，同步器必须限速分页。

---

## 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | 与赛狐官方签名示例一致 |
| HTTP | `httpx` | 同步客户端即可（日批任务） |
| 配置 | `pydantic-settings` + `.env` + `config.yaml` | 密钥不进仓库 |
| 本地库 | SQLite（`sqlite3` / SQLAlchemy） | 同步日志、token、幂等 |
| 定时 | 本地先用 APScheduler 或 Windows 任务计划；上线再 cron | 需求点：每日 ~10:00 |
| 飞书 | 飞书开放平台：多维表格（bitable）+ 机器人 | 应用凭证第 0 周并行申请 |
| 部署 | 先本机联调 → 再固定 IP 主机（白名单） | 无固定 IP 时赛狐会 `40005` |

**项目目录（建议新建于当前工作区）：**

```text
E:\project\亚马逊平台驾驶舱-店铺数据\
  app/
    __init__.py
    main.py                 # CLI: sync / rules / notify / once
    config.py
    clients/
      sellfox.py            # token + HMAC + 限速请求
      feishu.py             # bitable CRUD + 机器人
    sync/
      product_analyze.py    # 产品分析 V2
      inventory.py
      reviews.py
      shop_stats.py
      writer.py             # 写飞书底表（不覆盖人工列）
    rules/
      engine.py             # 黄橙红判定
      tasks.py              # 任务生成/防重复/升级
    notify/
      daily_digest.py
      escalate.py
    store/
      db.py                 # SQLite schema
  config/
    config.example.yaml
    rules.default.yaml      # 一期默认阈值（来自需求）
  scripts/
    init_feishu_tables.py   # 建多维表字段（或文档化手工建表）
    smoke_sellfox.py
  tests/
  requirements.txt
  README.md
  .env.example
```

保留现有业务文档；可将 `赛狐开放API.md` 后续改写为「驾驶舱数据接口版」（实现阶段做）。

---

## 数据与飞书表设计

### 主键

`date + marketplace/site + shop + asin`（同 ASIN 不同店铺必须分行）

### 表 1：ASIN每日数据表（系统写）

| 分组 | 字段示例 | 来源 |
|---|---|---|
| 维度 | 日期、站点、店铺、ASIN、SKU、父ASIN、品名、品牌、上架时间、负责人、产品等级 | 产品分析 V2 `PRODUCT_INFO` + 配置表映射 |
| 销售 | 销售额、订单量、销量、均价、7 日/对比字段 | `SALE_INFO` + 环比 |
| 流量 | Sessions、PV 及变化 | `SESSION_PERFORMANCE_INFO` |
| 转化 | 转化率、BuyBox | `PERFORMANCE_INFO` |
| 广告 | 曝光、点击、CTR、CPC、花费、广告销额、ACOS、TACOS 及变化 | `AD_INFO` |
| 库存 | FBA可售、在途、可售天数、库龄、断货标记 | `FBA_INVENTORY_INFO` / FBA 库存接口 |
| 评价 | 星级、Review 数、低星数、变化 | `REVIEW_PERFORMANCE_INFO` + 评价明细补全 |
| 同步元数据 | 同步批次号、同步时间、数据状态 | 本地生成 |

**人工列（若放在同表）同步时 skip**；更干净的做法是人工信息只在「动作表/配置表」。

### 表 2：异常任务表（系统生成）

异常编号、日期、店铺、ASIN、产品、异常指标、等级、当前值、对比值、变化幅度、负责人、审核人、状态、截止时间、连续异常次数、需要老板决策(否)、最新数据刷新时间。

**防重复：** 同一 `店铺+ASIN+异常类型` 且状态未关闭 → 不新建，只更新最新值/等级/连续次数。

### 表 3：运营动作记录表（人填）

关联异常编号、是否属实、原因、依据、动作、执行日、执行人、需审核事项、复查日、动作前/后数据、是否有效、下一步、闭环状态。

### 表 4：配置表（管理员）

店铺→负责人/审核人、产品等级（S/A/B/C/D）、各指标黄/橙/红阈值、提醒时限。

需求默认阈值见需求文档第六节（销售下降、订单、流量、转化、ACOS、广告花费、库存、评价等）；关键词排名一期 **降级为可选/暂缓**（官方产品分析未见完整自然词排名）。

### 老板视图（飞书视图，非单独库）

过滤/分组实现，不必新表：
1. 店铺健康总览  
2. 今日红色异常  
3. 待老板决策  
4. 逾期与未闭环  
5. 动作效果统计（可周汇总公式/第二张统计视图）  
6. 店铺下钻  

---

## 赛狐接口对接清单（一期）

| 优先级 | 接口 | Path | 用途 |
|---|---|---|---|
| P0 | Token | `GET /api/oauth/v2/token.json` | 鉴权 |
| P0 | 产品分析 2.0 | `POST /api/productAnalyze/V2/pageList.json` | ASIN 日数据主源；`dimType=1`；`compareTypeList=[1]` 环比 |
| P1 | FBA 库存 | `POST /api/inventoryManage/fba/pageList.json` | 可售/在途/库龄补全 |
| P1 | 评价明细 | `POST /api/review/pageDetailList.json` | 新增差评/低星明细 |
| P2 | 店铺表现按天 | `POST /api/stats/getShopDataByDay.json` | 老板店铺汇总 |
| P2 | 在线产品 V2 | `POST /api/order/api/product/v2/pageList.json` | Listing 状态异常 |
| 暂缓 | 利润类 | 财务 V2 等 | 一期不做 |
| 暂缓 | 关键词自然排名 | — | 一期不做或人工 |

鉴权要点（与官方一致）：
- Query：`access_token, client_id, timestamp(ms), nonce, sign`
- Sign：`HMAC-SHA256(client_secret, sorted query string)`，body 不参与
- 错误：`40001` 刷 token；`40005` 白名单；`40019` 限流 sleep 重试

---

## 实现阶段（里程碑）

### Phase 0 — 前置（并行，阻塞联调）

**工期：3–5 天（含等待）**

- [ ] 赛狐：确认 client_id/secret、所需接口权限（数据/产品分析/库存/评价）、出口 IP 白名单（本机动态 IP 可能不稳 → 记录当前 IP 临时加白或用能上白的机器）
- [ ] 飞书：创建企业自建应用；开通多维表格读写、机器人发消息；建「ASIN 健康度」知识库/多维表；拿到 `app_id/app_secret`、表格 `app_token`/`table_id`
- [ ] 业务：确认店铺列表、负责人/审核人映射（需求示例：马文静/潘启豪/梦晴等）、S/A 核心 ASIN 名单或产品等级来源
- [ ] 仓库：初始化 Python 项目、`.env.example`、README 环境说明

**退出标准：** `smoke_sellfox.py` 能拉到至少 1 页产品分析 V2；飞书能用 API 写 1 行测试记录。

### Phase 1 — 赛狐客户端 + 日同步骨架

**工期：约 1 周**

1. `clients/sellfox.py`：token 缓存（SQLite/文件）、签名、全局限速器（≥1s/接口）、统一 `request(path, body)`、分页迭代器
2. `sync/product_analyze.py`：按店铺或全量分页，`startDate/endDate=昨日`，`fieldModules` 拉  
   `PRODUCT_INFO, SALE_INFO, SESSION_PERFORMANCE_INFO, PERFORMANCE_INFO, AD_INFO, FBA_INVENTORY_INFO, REVIEW_PERFORMANCE_INFO`  
   （**不拉** `PROFIT_INFO`）
3. 原始结果落本地 `sync_runs` + 可选 JSON 快照，便于对账
4. CLI：`python -m app.main sync --date YYYY-MM-DD`

**退出标准：** 指定日期能完整拉完配置内店铺 ASIN，日志有 totalSize/页数/耗时/失败重试。

### Phase 2 — 飞书写入 + 字段映射

**工期：约 1 周（可与 Phase 1 后半重叠；飞书凭证到位后启动）**

1. `clients/feishu.py`：tenant_access_token、多维表 batch create/update、按主键查询
2. `sync/writer.py`：赛狐字段 → 飞书列映射表（代码常量 + 文档）；upsert 策略  
   - 有则更新「系统列」  
   - 永不覆盖「人工列」
3. `scripts/init_feishu_tables.py` 或 README 建表清单（字段类型：文本/数字/日期/单选）
4. 同步失败写「同步状态」并预留通知钩子

**退出标准：** 昨日数据在飞书底表可查；重跑同一天不产生重复主键行。

### Phase 3 — 规则引擎 + 异常任务

**工期：约 1 周**

1. `rules/engine.py`：读取配置表/YAML 默认阈值，对底表当日行打标黄/橙/红
2. `rules/tasks.py`：  
   - 黄：仅标记，不建任务（连续 2 次或达橙则升级，按需求）  
   - 橙：建任务，1 个工作日核实  
   - 红：高优任务，当天反馈，提醒负责人+审核人+老板  
3. 防重复与连续异常次数更新  
4. 单元测试：用需求第六节样例阈值写固定 fixture 断言

**退出标准：** 对历史/样例数据跑规则，任务表数量与等级符合预期；同一未关闭异常不重复建。

### Phase 4 — 提醒升级 + 动作闭环

**工期：约 1 周**

1. 飞书机器人：10:15 摘要（新增橙/红/逾期 + 视图链接）
2. 升级：橙超时 → 审核人；红当日未反馈 → 17:00 再提醒；复查日 9:30 提醒
3. 动作表：关联异常编号；闭环状态机 `待核实 → 处理中 → 待复查 → 已关闭 / 继续整改`
4. 同步失败：通知 IT 配置接收人

**退出标准：** 人为造 1 条红任务能收到消息；动作填写后状态可流转（可用飞书自动化辅助，核心状态仍由字段表达）。

### Phase 5 — 老板视图 + 定时 + 验收

**工期：约 1 周**

1. 飞书多维表视图/仪表盘按需求第十节配置
2. 本地定时：Windows 任务计划或 APScheduler 模拟 10:00 同步链路
3. 验收对照需求第十三节 checklist（见下）
4. 文档：运行手册、字段映射、阈值说明、故障处理（40005/40019）

**退出标准：** 需求验收标准 10 条可演示通过（关键词相关可标「一期暂缓」并书面确认）。

### Phase 6 — 试运行（业务）

**工期：2–4 周（与开发收尾可重叠）**

- 阈值按真实误报率调整（需求：试运行 2–4 周）
- 收敛负责人配置与 S/A 级 ASIN 清单
- 再决定是否启动二期（AI 日报/周报）

---

## 关键路径与调度

```text
Day 0–3   飞书应用申请 + 表结构确认 + 赛狐白名单/权限核对
Week 1    Sellfox client + 产品分析同步
Week 2    飞书写入 + 映射 + 幂等
Week 3    规则引擎 + 任务
Week 4    提醒 + 动作闭环
Week 5    老板视图 + 定时 + 验收演示
Week 6–8  试运行调阈值（业务主导）
```

**较可能日历：5–7 周到可验收；含试运行约 2 个月稳定给老板用。**  
前置不齐（飞书/白名单）时 Week 1 可先做客户端与本地落库，不阻塞写代码。

---

## 规则引擎设计要点

- 输入：当日 ASIN 行 + 环比/对比字段 + 产品等级 + 配置阈值  
- 输出：`list[Anomaly{type, level, current, baseline, delta, ...}]`  
- 等级冲突：同一 ASIN 多指标取**最高等级**展示，任务可按「异常类型」多条或合并策略（建议**按类型分条**，便于动作记录）  
- 金额门槛：销售下降等要求「前 7 天销售额 ≥ 3000 元」等，单位与币种在同步时统一（建议配置默认币种 CNY 换算或按站点本币+配置）  
- 工作日：橙「1 个工作日」需简单工作日历（可先按周一至五）

默认阈值来源：需求文档第六节；落地为 `config/rules.default.yaml`，运行时优先飞书配置表。

---

## 风险与一期砍刀

| 风险 | 处理 |
|---|---|
| 本机 IP 动态导致 40005 | 临时加白 + 记录；上线必须固定 IP |
| 飞书凭证未就绪 | Phase1 先写 SQLite，writer 接口抽象 `DataSink` |
| 关键词自然排名无 API | 一期不做；验收项标注暂缓 |
| 限流 + ASIN 量大 | 限速队列；可按店铺串行；必要时「有动销/有库存」筛选（`isNewOrMovingOrInStock`） |
| 字段名与后台不一致 | smoke 拉真实 JSON 再定映射，不假设 |
| 人工改表结构 | 映射层集中维护；飞书字段用「字段名/field_id」配置化 |

---

## 验收标准（对照需求 §13）

1. 每日可自动（或一键）同步赛狐数据，记录成功/失败  
2. 主键区分日期、站点、店铺、ASIN，同 ASIN 多店铺不混淆  
3. 黄/橙/红按配置触发  
4. 橙/红生成任务并匹配负责人  
5. 红任务提醒负责人、审核人、老板（机器人）  
6. 未关闭异常不重复建任务  
7. 助理可记原因/动作/复查；系统列不覆盖人工列  
8. 逾期与未复查可提醒升级  
9. 老板视图：店铺健康、红色、逾期、待决策、动作有效率  
10. 底表长期累加，可按店铺/月份/负责人/等级/状态筛选  

---

## 验证方式（开发过程）

| 层级 | 方法 |
|---|---|
| 单元 | 规则引擎 fixture 测试（pytest） |
| 集成 | `smoke_sellfox.py` 真网拉 1 页；飞书写删测试行 |
| 端到端 | `sync --date 昨日` → 底表有数 → `rules run` → 任务表有橙红 → 机器人测试群收到消息 |
| 回归 | 同日重跑：行数不爆增、任务不重复 |

---

## 关键文件（实现阶段将创建/修改）

| 路径 | 作用 |
|---|---|
| `app/clients/sellfox.py` | 赛狐鉴权与请求 |
| `app/clients/feishu.py` | 多维表与机器人 |
| `app/sync/*` | 拉数与写入 |
| `app/rules/*` | 异常与任务 |
| `app/notify/*` | 提醒升级 |
| `app/store/db.py` | 本地状态 |
| `config/rules.default.yaml` | 默认阈值 |
| `requirements.txt` / `README.md` / `.env.example` | 工程基线 |
| （可选）重写 `赛狐开放API.md` | 改为驾驶舱数据接口说明 |

现有 `.docx` / `.xlsx` 只作需求与业务对照，不作为运行时依赖。

---

## 二期预留（不在本 plan 实施）

- AI 日报/周报（基于日记录 + 动作表）  
- 关键词排名监控  
- 利润看板  
- 更复杂的老板仪表盘（飞书仪表盘/自建 Web）

---

## 实施顺序（批准后立即执行）

1. 初始化 Python 项目骨架与配置模板  
2. 实现 Sellfox client + smoke 脚本（用已有赛狐凭证）  
3. 抽象 `DataSink`：先 SQLite，飞书凭证到后接 bitable  
4. 产品分析 V2 日同步  
5. 规则引擎 + 任务  
6. 飞书写入 + 机器人  
7. 视图说明与验收脚本/清单  

**不在一期写：** 利润接口、亚马逊后台写操作、关键词排名强依赖、完整 Web 前端。
