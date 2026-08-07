---
name: m4-browser-env
description: M4发布层：.venv-m4(Py3.12)+Playwright；cookie半自动刷新；需企业卖家号；SDK混合模式
metadata: 
  node_type: memory
  type: project
  originSessionId: d065a8b1-9689-4179-9be0-6e168c205efe
---

M4 发布层环境与 2026-07-20 结论：

- **环境**：`E:\project\1688自动化\.venv-m4`（Python 3.12 + Playwright）；主仓 3.14 不跑浏览器。需 VC++ 运行库。
- **Cookie**：`config/1688_cookies.json` 会过期。刷新：`.venv-m4\Scripts\python.exe refresh_cookies.py`（有头登录回写）。复验：`test_m4_login.py`。
- **账号注意**：默认常落**买家工作台**；点 **「切为卖家」**（文案不是「切换为卖家」）。个人号会弹「非企业账号」——发商品必须用**企业卖家主账号**（常州易之来照明）登录。
- **发布模式**：**混合** — 浏览器注入 `alife-open-sdk` → `pcAlgorithmSdk.PcAlgorithmInit/Execute` 出风控参数 + 后端 Open API（`alibaba.new.product.add` / `getSchema` / photobank / video）。详见 `docs/m4_findings.md`。
- **代码**：`src/publish/session.py`、`sdk.py`、`probe.py`。API 清单 `docs/m4_api_inventory.md`。
- **未闭合**：`PcAlgorithmInit` 现返回 `getModelInfo error`；需企业号 + 发布页上下文。相关 [[main-image-pipeline]]。
