# Feishu Capability Audit — temu repo

## Goal
Map existing Feishu/Lark integration vs. needed "sync to Feishu spreadsheet + todo/bitable table".

## Verdict (one line)
**Today = outbound group-bot webhook cards only.** No Feishu app auth, no Sheets/Bitable/Task/Todo APIs, no record write-back, no spreadsheet sync.

---

## 1. What exists today

### 1.1 Auth / transport model
| Item | Status |
|------|--------|
| Custom bot webhook (`/open-apis/bot/v2/hook/{token}`) | YES — used everywhere |
| Optional bot **sign** (`feishuSecret` HMAC-SHA256) | YES — monitor only |
| Multi-webhook fan-out | YES — monitor (`feishuWebhooks[]`); plugin = single `webhook` |
| Feishu **app** `app_id` / `app_secret` | NO (for Feishu) |
| `tenant_access_token` / `user_access_token` | NO — zero hits |
| open.feishu.cn API beyond bot webhook | NO — only webhook POST |
| Lark international host | Plugin host_permissions allow `open.larksuite.com/*` but code uses Feishu CN URLs |

**Note:** `appKey` / `appSecret` / `accessToken` in `openapi.config*.json` are **Temu OpenAPI** credentials, not Feishu.

### 1.2 Message capability
Shared pattern: `msg_type: "interactive"` card with:
- `header.title` + `template` color (`red` / `orange` / `blue` / `green` ...)
- one `div` element, `lark_md` body (`lines.join('\n')`)

**Files:**
- `E:\project\temu\temu-monitor\src\feishu.js` — canonical server/monitor sender
- `E:\project\temu\temu-plugin\background.js` (`sendFeishu`) — plugin sender (no secret/sign)

### 1.3 Who sends what

| Source | Path | Alert types (card titles) |
|--------|------|---------------------------|
| Chrome plugin | `temu-plugin/background.js` | traffic alerts, SKU spec gone, front variants, must-remind, test |
| Playwright traffic | `temu-monitor/src/run.js` | onSale drop / traffic anomaly (emergency) |
| Login watch | `temu-monitor/src/cli.js` | login expiry interrupt |
| Sellfox (server) | `temu-monitor/src/sellfox/monitor.js` | delist / onshelf |
| OpenAPI path | `temu-monitor/src/openapi/monitor.js` | OpenAPI monitor alerts |
| fullRun combo | `temu-monitor/src/fullRun.js` | combined |

Production split (`PLUGIN_PARITY.md` / `deploy/README-SERVER.md`):
- **Plugin** -> traffic wait-attention / recent-decline + must-remind
- **Server sellfox** -> delist / onshelf
- Both can share the **same webhook group**

### 1.4 False positives in search
- "表格" = Temu goods list DOM / calibrate waits — not Feishu Sheets
- "待办" in `popups.js` = Temu seller-center modal dismiss text — not Feishu Tasks
- "多维" in plugin comment = multi-dim SKU specs join with `/` — not bitable
- `app_secret` / MD5 sign in openapi client = Temu signature scheme

### 1.5 Repo search nulls
No matches for: `bitable`, `spreadsheet`, `tenant_access_token`, `sheets/v`, `drive/v`, `task/v`, `wiki/v`, `docx`, Feishu todo APIs.

---

## 2. Config examples (current)

### Plugin (chrome.storage via options page)
```
webhook: https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
```
UI: `temu-plugin/options.html` — single field, no secret, no app credentials.

### Monitor main — `temu-monitor/config.example.json`
```json
{
  "feishuWebhooks": [
    "https://open.feishu.cn/open-apis/bot/v2/hook/替换成你的webhook"
  ],
  "feishuSecret": ""
}
```

### Sellfox — `sellfox.config.example.json` / `sellfox.config.json`
```json
"feishuWebhooks": []
```
Merged with main `config.json` hooks in `src/sellfox/config.js` (dedupe Set).

### OpenAPI — `openapi.config.example.json`
```json
"feishuWebhooks": []
```
Same merge pattern in `src/openapi/config.js`.

### Deploy notes
- `deploy/README-SERVER.md`: chmod 600 configs with secrets + webhooks; troubleshooting "飞书没消息" = first round no alert / check webhooks / dry-run.

---

## 3. Auth patterns (as implemented)

### A. Custom bot webhook (only real Feishu auth)
1. Create group custom bot -> copy hook URL
2. Optional: enable signature verification -> put secret in `feishuSecret`
3. Sign (monitor only):
   - `stringToSign = timestamp + "\n" + secret`
   - `sign = base64(HMAC-SHA256(stringToSign, empty body))`
   - POST body includes `timestamp` + `sign`
4. POST JSON card to webhook; success when `code === 0` (plugin also accepts `StatusCode === 0` / missing code)

### B. No Feishu Open Platform app
Missing for Sheets/Bitable/Tasks:
- Create Feishu app -> `app_id` + `app_secret`
- `POST /open-apis/auth/v3/tenant_access_token/internal`
- Scopes: e.g. bitable/sheets/task/drive (exact set TBD by product)
- Target IDs: spreadsheet token / bitable `app_token` + `table_id` / task list id
- User/bot must be added to the doc or bitable as collaborator

### C. Confusable: Temu OpenAPI
`openapi.config.json` uses Temu `appKey`/`appSecret` + per-store `accessToken` with Temu MD5 request signing — unrelated to Feishu token flow.

---

## 4. Gap analysis: "sync to Feishu spreadsheet + todo table"

| Needed capability | Today | Gap |
|-------------------|-------|-----|
| Push alert text to group | YES | — |
| Persist structured rows (SKU, store, event, time, link) | NO | No Sheets API write |
| Bitable records create/update | NO | No Bitable client |
| Todo / Task list items for follow-up | NO | No Task/Todo API; "待办" only Temu UI |
| Idempotent upsert (avoid dup rows on re-alert) | NO | No record keys / query API |
| App token refresh + retry | NO | No token layer |
| Config for spreadsheet/bitable IDs | NO | Only webhook fields |
| Permission model beyond group bot | NO | Bot cannot write sheets/bitable without app |

**Webhook bots cannot write spreadsheets or bitable.** Need a Feishu **enterprise app** (or user OAuth) with document scopes.

---

## 5. Minimal build path (if implementing later — not in this audit)

1. New Feishu app in open.feishu.cn; enable bot + bitable/sheets scopes; publish for tenant.
2. Config extension example:
   ```json
   "feishuApp": {
     "appId": "",
     "appSecret": "",
     "bitableAppToken": "",
     "alertTableId": "",
     "todoTableId": ""
   }
   ```
   Keep existing `feishuWebhooks` for realtime cards.
3. Module e.g. `temu-monitor/src/feishuBitable.js`:
   - get/cache `tenant_access_token`
   - batch_create records on alert events
   - optional: Task API, or Bitable status column as todo board
4. Call sites: after successful `sendFeishu` in sellfox/plugin/openapi.
5. Plugin constraint: MV3 extension should not hold `app_secret`; prefer server-side sync; plugin stays webhook-only.
6. Security: never commit app_secret; chmod 600; mirror sellfox deploy pattern.

---

## 6. Key absolute paths

| Path | Role |
|------|------|
| `E:\project\temu\temu-monitor\src\feishu.js` | Server/monitor Feishu card sender + sign |
| `E:\project\temu\temu-plugin\background.js` | Plugin `sendFeishu` + alert call sites |
| `E:\project\temu\temu-plugin\options.html` / `options.js` | Webhook UI |
| `E:\project\temu\temu-plugin\manifest.json` | host_permissions open.feishu.cn / open.larksuite.com |
| `E:\project\temu\temu-monitor\config.example.json` | feishuWebhooks + feishuSecret template |
| `E:\project\temu\temu-monitor\src\config.js` | Normalize multi-webhook |
| `E:\project\temu\temu-monitor\src\sellfox\monitor.js` | Delist/onshelf -> sendFeishu |
| `E:\project\temu\temu-monitor\src\openapi\monitor.js` | OpenAPI alerts -> sendFeishu |
| `E:\project\temu\temu-monitor\deploy\README-SERVER.md` | Ops + dual-channel design |
| `E:\project\temu\temu-monitor\PLUGIN_PARITY.md` | Plugin vs server duty split |

---

## 7. Conclusion for parent agent

**Feishu today = fire-and-forget interactive cards via custom robot webhooks.**

**Missing for spreadsheet + todo/bitable sync = entire Open Platform stack** (app credentials, tenant token, Sheets/Bitable/Task clients, target table config, upsert semantics).

Realtime group alerts can stay as-is; structured sync would be a **new vertical**, best on `temu-monitor` server (not plugin), reusing alert event objects already formatted for cards.
