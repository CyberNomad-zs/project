# BLOCKED

无

## 备注（非阻塞）
- 本地表 `task`/`task_progress` 属主为 `postgres`，应用用户 `qingquan` 无 ALTER 权；迁移 `004_ops_knowledge.sql` 需用超级用户执行一次（本机用 postgres/postgres 已执行并 GRANT）。部署时注意同样权限。
- 预存在未纳入本切片的脏文件：`backend/app/api/ingest.py` 等，未改动。
