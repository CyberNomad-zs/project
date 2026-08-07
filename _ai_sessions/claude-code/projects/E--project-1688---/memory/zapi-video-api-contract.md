---
name: zapi-video-api-contract
description: zapi生视频真实契约(与交接文档§7-A3不同)
metadata: 
  node_type: memory
  type: reference
  originSessionId: b88122c6-fc18-43c5-a7b3-3099a1cd10d8
---

zapi 生视频 `POST /v1/videos`（模型 `grok-imagine-video-1.5-preview`）实测契约，**与交接文档 §7-A3 写的不一致**（文档说 image 传 `{"url":...}` 对象最稳——那是错的）：

- `image` 字段必须是**字符串**（公网 URL 或 data URI），传 `{"url":...}` 对象报 `invalid_json`。
- `seconds` 必须是**字符串** `"5"`，传数字报 `invalid_json`。
- 该模型**不支持文生视频**，必须给首帧做 i2v（t2v 报 `Text-to-video is not supported`）。
- 提交成功返回 `{id, task_id, status:"queued", progress}`；轮询 `GET /v1/videos/{id}`，取 `GET /v1/videos/{id}/content`。

已在 `src/generate/zapi_client.py` 的 `submit_video` 按此实现。相关 [[main-image-pipeline]]。
