# PROGRESS — ops knowledge A+B

## 开工回执（Task 0）
- **目标**：结构化 action/effect 闭环 + guidance(history+published) + 草稿发布 + 指标回填 + 最小 Web + ≥4 测试
- **顺序**：venv/DB → migration 种子 → task_engine 写路径 → kb domain/API → Web → pytest 取证
- **最大风险**：Postgres 属主权限；async 引擎与 pytest 事件循环
- **环境**：backend/.venv fastapi 0.140.0；pytest 已装；DB 可用
- **日期**：2026-07-29

## 进度
- [x] Task 0 环境核对
- [x] Task 1 迁移与种子（004_ops_knowledge.sql；actions=7 effects=5 published=3）
- [x] Task 2 写路径（progress/resolve 结构化；骨架必填 effect）
- [x] Task 3 guidance / generate-draft / publish / demote / metric-backfill
- [x] Task 4 Web 抽屉双块 + action/effect
- [x] 测试与验收证据（6 passed；scratch 下 pytest/api/playbook/metric/web/diff）

## 完成摘要
- 硬指标1：三骨架 resolve+guidance history + published playbook — 通过测试与 api-guidance 证据
- 硬指标2：无 G3 自动改价/预算；核心改动在白名单路径
- 测试：`backend` 下 `pytest -q` → **6 passed**
