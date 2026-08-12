# Phase 0 · 实施计划

> 周期：2–3 周  
> 目标：可运行的中心基座 —— 登录、店铺主数据、采集上报、任务状态机、飞书同步 MVP

---

## 1. 范围

### In Scope

- Docker Compose：API / PostgreSQL / Redis / Worker
- FastAPI 骨架 + JWT 登录（账号密码）
- 表结构：组织、店铺、采集原始、异常、任务、飞书映射
- `POST /api/v1/ingest/{source}` 幂等写入
- 任务引擎 MVP：去重键、创建/更新进度/闭环、列表查询
- 飞书 Bitable：create/update + record 映射（先通一张表）
- 简易 Web：登录、店铺列表、任务列表（可先接口 + 极简页）
- 采集 Agent SDK（Python）：签名、重试、心跳
- 文档与本地启动说明

### Out of Scope（Phase 1+）

- 三平台完整监控规则
- 亚马逊前台插件
- 采购供应商
- 飞书扫码登录 / 智能体对话
- 海外仓发货并入

---

## 2. 里程碑

| 日 | 里程碑 | 验收 |
|----|--------|------|
| D1–D2 | 仓库骨架 + Compose 起 PG/Redis/API hello | `curl /health` 200 |
| D3–D5 | migrations 001 + 用户/店铺 CRUD + JWT | 可登录拿 token |
| D6–D8 | Ingest API + 幂等 + 原始落库 | 重放同一 key 不重复 |
| D9–D11 | 任务状态机 + 异常建单服务 | 同 dedupe 不双开单 |
| D12–D14 | 飞书同步 Worker + 映射表 | 改任务 → 飞书行更新 |
| D15–D16 | Agent SDK + 模拟采集脚本 | 模拟 TK 行上报成功 |
| D17–D18 | 极简 Web 任务台 + 联调 | 演示闭环 |
| D19–D21 | 缓冲：权限修补、文档、演示给对接人 | Phase0 签字 |

---

## 3. 目录与模块

```
backend/
  app/
    main.py                 # FastAPI 入口
    config.py               # 环境变量
    api/
      health.py
      auth.py
      shops.py
      ingest.py
      tasks.py
      export_feishu.py
    domain/
      task_engine.py        # 去重/状态机
      anomaly.py
      notify.py             # 预留
    adapters/
      feishu/
        auth.py
        bitable.py
      sellfox/              # Phase1 再填
      mail/                 # 预留
    jobs/
      worker.py             # ARQ/Celery
      sync_feishu.py
    infra/
      db.py
      redis.py
      security.py
  migrations/
    001_init.sql
web/                        # Phase0 可先静态或 Vue 脚手架
collectors/agent-core/      # 上报 SDK
deploy/docker-compose.yml
```

---

## 4. 环境变量

```env
APP_ENV=dev
APP_SECRET_KEY=change-me
DATABASE_URL=postgresql+asyncpg://qingquan:qingquan@db:5432/qingquan
REDIS_URL=redis://redis:6379/0
JWT_EXPIRE_MINUTES=1440

# 采集
INGEST_DEFAULT_API_KEY=dev-ingest-key

# 飞书（与 TK 项目可共用应用，权限含 bitable:app）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BITABLE_APP_TOKEN=
FEISHU_BITABLE_TABLE_TASKS=

# 可选
TZ=Asia/Shanghai
```

---

## 5. 接口清单（Phase 0）

详见 [openapi-v1.yaml](./openapi-v1.yaml)。摘要：

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | 无 | 健康检查 |
| POST | `/api/v1/auth/login` | 无 | 用户名密码 → JWT |
| GET | `/api/v1/auth/me` | JWT | 当前用户 |
| GET/POST | `/api/v1/shops` | JWT | 店铺 |
| PATCH | `/api/v1/shops/{id}` | JWT | 改负责人等 |
| POST | `/api/v1/ingest/{source}` | API Key | 采集上报 |
| GET | `/api/v1/tasks` | JWT | 筛选列表 |
| POST | `/api/v1/tasks` | JWT | 手动建单 |
| POST | `/api/v1/tasks/{id}/progress` | JWT | 更新进度 |
| POST | `/api/v1/tasks/{id}/resolve` | JWT | 闭环 |
| POST | `/api/v1/export/feishu` | JWT | 触发同步 |
| POST | `/api/v1/collectors/heartbeat` | API Key | 边缘心跳 |

---

## 6. 任务引擎伪代码

```python
async def upsert_task_from_anomaly(ev: AnomalyEvent) -> Task:
    dedupe = f"{ev.platform}:{ev.biz_id}:{ev.anomaly_type}"
    existing = await repo.find_open_task(dedupe)
    if existing:
        existing.progress_note = ev.detail
        existing.source_event_id = ev.id
        existing.updated_at = now()
        await repo.save(existing)
        await outbox.feishu_sync(existing.id)
        return existing

    task = Task(
        dedupe_key=dedupe,
        status="open",
        owner_user_id=await resolve_owner(ev.shop_id, ev.biz_id),
        due_at=now() + timedelta(days=settings.default_due_days),
        title=ev.title,
        ...
    )
    await repo.insert(task)  # 唯一约束兜底并发
    await notify.task_created(task)  # Phase0 可只打日志
    await outbox.feishu_sync(task.id)
    return task
```

并发：依赖 PG 部分唯一索引；冲突则转 update。

---

## 7. 飞书同步 MVP

1. Outbox 表或 Redis 队列写入 `entity=task, id=...`
2. Worker 拉取 → 读 task → 算 content_hash
3. 查 `sync_feishu_map`  
   - 无 record_id → batch_create → 存映射  
   - 有且 hash 变 → batch_update  
   - hash 同 → skip
4. 字段映射配置 JSON（中文列名 ↔ 内部字段）
5. Phase0 只同步 **任务表** 一张，验证链路

复用点：TK 项目 `extension/feishu/bitable.js` 与 PS 写飞书逻辑 → 移植为 `backend/app/adapters/feishu/bitable.py`。

---

## 8. 采集 Agent SDK（最小）

```python
# collectors/agent-core/qingquan_agent.py
class AgentClient:
    def __init__(self, base_url: str, api_key: str): ...
    def report(self, source: str, envelope: dict) -> dict: ...
    def heartbeat(self, node_id: str, meta: dict) -> None: ...
```

Phase0 附带 `scripts/mock_ingest_tiktok.py`：读样例 JSON 上报，验证幂等。

---

## 9. 数据迁移 / 种子

- 创建管理员 `admin / 首次登录改密`
- 种子店铺：Agnis、HomeCove、Twilight Cove、Deal to deal、Gardena、TikTok - Pop
- 角色：`admin` / `operator` / `viewer`（Phase0 RBAC 可简化为 is_admin）

---

## 10. 测试计划

| 用例 | 期望 |
|------|------|
| 重复 ingest 同 idempotency_key | 200 + 同一内部 id，表行不增 |
| 两次同 dedupe 异常 | 仅 1 条 open 任务，progress 更新 |
| resolve 后再异常 | 新任务 id |
| 飞书改列名（加别名） | 同步仍成功 |
| 错误 API Key | 401 |
| 任务列表按店铺筛选 | 只返回授权店（Phase0 可全量） |

---

## 11. 演示脚本（Phase0 完成时）

1. 启动 `docker compose up -d`
2. 登录 Web / 拿 JWT
3. 跑 mock 采集 → 任务台出现记录
4. 更新进度 → 飞书对应行变化
5. 闭环 → 状态变更；再次 mock 同异常 → 新单

---

## 12. 人员与依赖

| 依赖 | 负责人/来源 |
|------|-------------|
| 服务器 / 固定 IP | 基础设施 |
| 飞书应用与测试多维表 | 复用 TK 或新建「清泉-任务」 |
| 管理员账号 | 实施时创建 |
| 阈值规则 | Phase2 与陈梦晴等对接（Phase0 用手动/mock） |

---

## 13. 退出标准（Definition of Done）

- [ ] `docker compose up` 一键起全套
- [ ] 001_init.sql 迁移成功
- [ ] 登录 + 店铺 API 可用
- [ ] Ingest 幂等验证通过
- [ ] 任务去重 / 闭环 / 重建验证通过
- [ ] 至少 1 张飞书表 create+update 打通
- [ ] mock 采集脚本与 README 可复现
- [ ] 架构/字段/改造文档齐套
