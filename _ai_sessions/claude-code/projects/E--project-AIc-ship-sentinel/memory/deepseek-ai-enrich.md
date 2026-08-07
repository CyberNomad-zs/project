---
name: deepseek-ai-enrich
description: ai_enrich.py 用 DeepSeek 兼容接口跑，需覆盖模型且不支持 output_config
metadata: 
  node_type: memory
  type: project
  originSessionId: a58b4d49-d7b7-4256-af33-0cf3da5c29f8
---

发货哨兵演示机上生成 AI 处置建议卡（`backend/ai_enrich.py`）时，用的是 **DeepSeek** 的 Anthropic 兼容接口，不是官方 Anthropic。

跑之前需设三个环境变量（Key 是 DeepSeek 的，不要提交/外传）：
- `ANTHROPIC_API_KEY` = DeepSeek 的 Key（`sk-...` 32位十六进制，非 `sk-ant-`）
- `ANTHROPIC_BASE_URL` = `https://api.deepseek.com/anthropic`
- `SENTINEL_AI_MODEL` = `deepseek-chat`（实际路由到 `deepseek-v4-flash`）

**关键坑：** DeepSeek 兼容层不支持 Anthropic 的 `output_config` 结构化输出——会静默忽略、返回非 JSON。所以 `ai_enrich.py` 已从 `output_config` 结构化输出改为「提示词要求纯 JSON + `extract_json()` 稳健解析（去代码围栏、抓首个 `{...}`）」，官方接口和 DeepSeek 都兼容。改前若有人把它退回 `output_config` 写法，DeepSeek 就会全部跳过、生成 0 条卡。

**Why:** `.bat` 默认模型是 `claude-opus-4-8`，直接跑会 404/参数不匹配；必须覆盖模型名和 base_url。
**How to apply:** 重跑演示机时先 `set` 上述三个变量，或 `演示机-生成AI并打包.bat deepseek-chat`（模型可作首个参数，但 Base URL 仍需先 set）。
