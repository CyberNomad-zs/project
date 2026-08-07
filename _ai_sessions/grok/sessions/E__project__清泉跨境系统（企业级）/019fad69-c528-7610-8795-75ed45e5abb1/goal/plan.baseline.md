# Plan: Ops knowledge slice — structured action/effect close + A+B guidance (history stats + published playbooks)

## Goal kind
code-change

## Acceptance criteria
1. For the three skeleton pairs (`amazon`/`link_wow_units_drop`, `tiktok`/`low_roi`, `temu`/`listing_off`), a task can be progressed with an optional known action code and resolved with a required known effect code; unknown codes and missing effect on those types are rejected; non-skeleton types still close with note-only; free-text note remains supported.
2. A guidance query by `platform` + `anomaly_type` returns (a) history aggregates of action codes with effect distributions from structured closes (empty array allowed when none) and (b) playbooks limited to published status only.
3. A draft can be generated from history without appearing in guidance playbooks; after publish it appears; if status returns to draft it disappears again (A live stats still available without published playbooks).
4. Dual-track effect: effect labels persist on close; metric backfill for `amazon`/`link_wow_units_drop` writes metric outcome when `fact_amz_link_daily` data exists, and returns a non-error skipped result when fact data is absent.
5. Task detail UI shows both labeled blocks 「历史参考」and 「已发布剧本」from guidance, and the close form can supply action + effect for skeleton types (minimal UI is enough).
6. At least four automated tests exercise the real write/guidance/publish paths with zero skips; no code path auto-executes platform ops (price/budget changes).

## Verification plan
1. `gating`: From `backend` using `backend/.venv` (install deps/pytest if needed), run the real test suite (`pytest -q`). Observe: ≥4 tests collected, 0 skipped, all pass; failures cover or include legal structured resolve, missing effect_code → client error, unknown action → client error, and draft excluded vs published included in guidance. Capture full output to `{SCRATCH}/pytest.txt`.
2. `gating`: Exercise the shipped HTTP API (TestClient or live app against real DB if tests already do): for each of the three skeleton types, create/open a task, resolve with valid action+effect, then call guidance. Observe: resolve succeeds; guidance `history` non-empty after ≥1 structured close per exercised type (or after seed of ≥2 closes); at least one published playbook reachable via guidance for at least one type. Capture responses to `{SCRATCH}/api-guidance.json`.
3. `gating`: Run generate-draft then guidance, then publish then guidance (and reverse: demote published→draft then guidance). Observe: draft never listed under guidance playbooks; after publish it is listed; after demote it is absent. Capture to `{SCRATCH}/playbook-lifecycle.log`.
4. `gating`: Invoke metric backfill for `amazon`/`link_wow_units_drop` twice if possible: once with fact rows present (assert metric written or explicit success body), once without (assert skipped-style success, not 5xx). Capture to `{SCRATCH}/metric-backfill.log`.
5. `gating`: Static check of `web/src` — source contains guidance fetch usage and the literal labels 「历史参考」「已发布剧本」, plus close/progress UI fields for action and effect. Capture grep/read evidence to `{SCRATCH}/web-ui-check.txt`.
6. `evidence`: `git diff --name-only` vs start; only allowed paths (migrations next-id, domain/api/scripts/tests, web/src, openapi, requirements test lines, PROGRESS.md, BLOCKED.md). Capture to `{SCRATCH}/diff-names.txt`. BLOCKED.md present (may say 无).
7. `evidence`: Grep workspace for auto platform-mutation helpers (e.g. change price/budget APIs); expect none added for this feature. Capture to `{SCRATCH}/no-g3-ops.txt`.

## Non-goals
- LLM, RAG chat knowledge base, or mining historical free-text notes into actions
- Auto-executing platform operations (price/budget/listing changes)
- Full multi-anomaly dictionaries beyond the three skeleton types plus seed counts stated in the goal brief
- Feishu field sync changes, AMZ mom scan batch fixes, large nav redesign
- New auth/permission systems beyond existing `get_current_user`
- Changing semantics of migrations 001–003 (extensions only via new migration)

## Assumed scope
- New SQL migration after `003_tiktok_ads_p1_fields.sql` for action/effect dictionaries, structured columns on progress/task, playbook storage, optional metric storage
- `backend/app/domain` task engine + knowledge domain logic; `backend/app/api` task write extensions + guidance/playbook/backfill routes registered in `main.py`
- Optional seed script updates; `backend/tests` new suite; `web/src` App/api minimal; `docs/openapi-v1.yaml`; `backend/requirements.txt` test deps only; root `PROGRESS.md` / `BLOCKED.md`
- Runtime: PostgreSQL as used by app; `backend/.venv`; FastAPI + SQLAlchemy async already in tree

## Implementation approach
Keep pure aggregation/publish state transitions and code validation separable from HTTP so tests can hit domain functions and/or API with a real session. Prefer small write path that persists structured codes on progress/resolve, then read path that aggregates SQL and filters playbook status. Seed minimal dictionaries and one published playbook per skeleton type so guidance is demoable without production data. Web only binds the existing task drawer to guidance + two form fields.

## Task checklist
- [ ] Task 0: verify `backend/.venv` imports FastAPI; install requirements/pytest if needed; write ≤10-line PROGRESS.md start receipt
- [ ] Add migration + seeds: action/effect dicts, structured progress fields, playbook table, ≥3 actions / ≥4 effects / 3 published skeleton playbooks
- [ ] Extend progress/resolve write path for optional action + required effect on skeleton types; illegal/missing → 400; keep note compatibility
- [ ] Implement guidance (history + published only), generate-draft, publish, and metric-backfill (write or skip)
- [ ] Minimal web: fetch guidance, show both section titles, action/effect on close for skeleton types
- [ ] Add ≥4 real tests (resolve happy path, missing effect, unknown action, draft vs published guidance); run pytest; capture logs under `{SCRATCH}`; update PROGRESS/BLOCKED

## Risks / Contradictions
- Local default Python may lack FastAPI/pytest; goal allows venv install — tests require DB; if Postgres unavailable, implementer must use the project’s existing DB config or record BLOCKED with evidence rather than fake green tests.
- Metric dual-track for non-Amazon skeleton types has no fact table in scope; only amazon/link_wow backfill is required; others remain label-only.
