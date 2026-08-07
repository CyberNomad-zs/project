# sellfox-bridge 后续开发计划

## Context

`sellfox-bridge` 已用赛狐开放 API + 双 WMS（金猫/黑猫）替换网页自动化的核心路径，并完成单店灰度：

| 已验证 | 状态 |
|---|---|
| dry-run / 渠道识别 / 双 WMS 路由 | ✅ |
| 无渠道 = 人工指派 | ✅ 业务已定 |
| G1 Agnis：认渠道 → `CHANNEL_ASSIGNED` | ✅ 样例 63996 |
| G2 Agnis：`applyTrackNo` 真推仓 | ✅ 63996 → 黑猫 WMS `orderStatus=0` |
| step3 返回值兼容 `successData: [str]` | ✅ 已修 |

**当前缺口**（决定后续开发优先级）：

1. **step4 回传未验收**：仓发出后称重可能因 `weight_g=0` / 无 `sku_weights` 失败；`quick` 模式未作为默认兜底。
2. **状态机毛刺**：`FAILED` 不复活；历史 `NEW` 每轮刷「跳过明细」；无 `track_no` 回填。
3. **运行与可观测性**：本机家宽、飞书未配、无健康检查/对账定时任务。
4. **范围未扩**：仅 Agnis G2；HomeCove/Twilight 未开自动下单。
5. **明确不做（一期）**：WMS 仓内改快递/批量发货（仍属 automation/人工）；Gardena 等非白名单店。

**目标**：在现有四步流水线（`bridge/pipeline.py`）上，把 **G2→闭环回传→三店稳跑→可部署** 走完，再考虑 step0 审核/拆包等重功能。

---

## 现状架构（复用，不大改）

```
main.py → Pipeline.run_once()
  step1_discover  赛狐 to_process → store NEW + _package_cache
  step2_assign    keep_existing_channel → CHANNEL_ASSIGNED（无渠道 FAILED）
  step3_order     auto_apply_track_no → applyTrackNo → ORDERED
  step4_close     WMS 已发货+运单 → weighing/quick → CLOSED
```

关键已有能力（计划内复用）：

- `Pipeline._wms_for_channel` / `_shop_allowed` / `_rows_for_step`
- `SellfoxClient.apply_track_no` / `weighing_shipment` / `quick_outbound`
- `WmsClient.query_order_status` / `query_tracking_number`
- 配置：`wms.profiles`、`channels[].wms_profile`、`order_channel_names`
- 脚本：`config.g2-agnis.yaml`、`run_g2_agnis.bat`、`recon.py`

---

## 推荐路线：四个阶段

### Phase A — G2 稳态与状态机修缮（优先，1～2 天开发）

**目的**：G2 可连续多天无人值守，少噪音、少卡死单。

| # | 项 | 改动要点 | 文件 |
|---|---|---|---|
| A1 | **FAILED 条件复活** | `to_process` 再次出现且**已有可用渠道** → 重置为 `NEW`（或直接走保留渠道）；无渠道仍 FAILED | `pipeline.step1` / `step2`、`store.py` |
| A2 | **陈旧 NEW 清理** | 连续 N 轮（或 >X 天）不在 to_process → `CLOSED`/`STALE` 或忽略不再刷日志 | `pipeline` + 可选 `store` 新状态 |
| A3 | **step3 幂等** | 赛狐已是 `apply_track_no` 的单：本地同步为 `ORDERED`，避免重复下单/误报 | `step1` 可扩拉状态 或 step3 前查赛狐 |
| A4 | **回填 track_no** | step4 成功时 `store.track_no`；ORDERED 轮询时也可写运单（若已生成） | `pipeline.step4`、`store.set_state` |
| A5 | **step4 重量策略** | `weight_g` 为空/0 时：优先 `sku_weights` 估重；仍无则 **fallback `quick_outbound`**（可配置 `ship_confirm_mode: auto`） | `pipeline.step4`、`config` |
| A6 | **下单成功后日志/通知** | 飞书可选：下单成功/失败各一条（`notify.py` 已有骨架） | `notify.py`、`config.g2` |

**验收**：

- 再跑 3+ 单 Agnis 自动下单成功进对应 WMS。
- 63996 黑猫发货后，step4 能 CLOSED（quick 或有重量）。
- 日志无每轮 10 条「跳过明细」刷屏。
- 63872 人工选渠道后能自动复活并进入下单（若开 G2）。

---

### Phase B — G3 回传闭环验收（依赖仓内发货，0.5～1 天）

**目的**：证明「下单 → WMS 出库 → 回传赛狐」全自动。

| # | 项 | 说明 |
|---|---|---|
| B1 | 跟完 63996 | 黑猫仓发出 → 观察 step4 日志与赛狐 `has_shipped` |
| B2 | `ship_confirm_mode` | 默认建议 `auto`：有重量 weighing，无重量 quick；核对 `isOversea`（文档 weighing 与 quick 取值可能不同） |
| B3 | 承运一致性 | 已有 `hold_on_channel_mismatch`；确认 BLACKCAT 黑猫 express 与 RM/DPD/EH 匹配规则（`expected not in actual`） |
| B4 | 失败重试 | step4 已「不置 FAILED」；加连续失败 N 次告警升级 |

**验收**：至少 1 单（建议 63996 或新单）本地 `CLOSED`，赛狐已发货/已回传平台。

---

### Phase C — 运行与灰度扩面（1～2 天 + 观察）

| # | 项 | 说明 |
|---|---|---|
| C1 | **飞书 webhook** | 填 `notify.feishu_webhook`；G2 下单/回传/FAILED 推送 |
| C2 | **固定 IP 部署** | 迁 `193.112.93.60`（或固定出口）；赛狐白名单；计划任务/NSSM/systemd 常驻 G2 配置 |
| C3 | **扩店 G4** | 白名单加 HomeCove → Twilight；每店观察 1 天；automation 对应店停真跑 |
| C4 | **配置收敛** | 生产只用一份 `config.yaml`（或 `config.prod.yaml`），G1/G2 专用文件作文档模板 |
| C5 | **每日对账** | 整理现有 `recon.py`：白名单店 has_shipped × 双 WMS 运单；cron/计划任务；差异进飞书 |

**验收**：三店 G2 稳定 ≥3 天；家宽调试机可下线主路径。

---

### Phase D — 增强（有业务数据再做，不挡主路径）

| # | 项 | 依赖 | 优先级 |
|---|---|---|---|
| D1 | `sku_weights` 补录 | 业务提供克重（清单已有） | 称重回传要准时 |
| D2 | 渠道价卡 | 业务提供 | 仅无渠道自动选时需要；当前人工指派可缓 |
| D3 | step0 待审核 SOP | 品类映射、地址策略 | 高价值高成本 |
| D4 | Amazon 店入白名单 | WMS 平台授权 | 业务触发 |
| D5 | 调研赛狐内置自动交运 | — | 可能瘦身 bridge |

**明确不在本计划实现**：WMS「改快递方 + 批量发货」API 化（继续 WMS 网页/automation）。

---

## 实施顺序（建议 sprint）

```
现在（G2 挂着）
  │
  ├─ Phase A：状态机 + step4 重量兜底     ← 先开发
  ├─ Phase B：跟 63996 闭环验收            ← 与仓内并行
  ├─ Phase C：飞书 + 部署 + 扩店 + recon
  └─ Phase D：克重/step0/…（按业务排期）
```

**推荐首个开发切片（可一次 PR）：A1 + A2 + A5 + A4**  
（复活、减噪音、回传能成、运单落库）

---

## 关键文件（Phase A/B）

| 文件 | 角色 |
|---|---|
| `bridge/pipeline.py` | A1–A5、B2–B4 主逻辑 |
| `bridge/store.py` | 复活/陈旧状态、可选 `mark_stale` |
| `bridge/selector.py` | 估重已有；step4 复用 `estimate_weight_g` |
| `bridge/notify.py` | A6 下单/回传通知 |
| `config/config.g2-agnis.yaml` / `config.example.yaml` | `ship_confirm_mode: auto`、复活/陈旧参数 |
| `灰度_G2_Agnis.md` / `项目说明.md` | 同步 G2/G3 验收与范围 |
| `recon.py` | Phase C5 定时化 |

---

## 风险与约束

| 风险 | 缓解 |
|---|---|
| 重复 `applyTrackNo` | A3 幂等；下单前看赛狐状态 |
| step4 重量 0 导致回传失败 | A5 quick fallback |
| 与 automation 双真下单 | 扩店时书面约定停真跑；白名单隔离 |
| 动态 IP 40005 | C2 固定 IP |
| BLACKCAT 仅黑猫账本 | 已双 WMS；step4 必须走 `wms_profile`（已实现） |

---

## Verification（按阶段）

**Phase A**

```text
python main.py --config config/config.g2-agnis.yaml --once
# 期望：无「跳过明细」刷屏（或明显减少）
# FAILED+有渠道单 → CHANNEL_ASSIGNED/ORDERED
# 人为 weight 空的 ORDERED+WMS 已发货 → quick 或估重回传成功
```

**Phase B**

- 63996 黑猫 `orderStatus=2` + 有运单后：本地 `CLOSED`，赛狐可查已发货。

**Phase C**

- 服务器常驻；飞书收到下单/失败卡片；recon 日报无系统性差异。

**回归**

- Agnis 仅白名单；Gardena 等不进 step3。
- 金猫 key 查不到 BLACKCAT 单、黑猫 key 查不到纯昇新单（隔离）。

---

## 成功标准（整体）

1. 白名单店：待处理有渠道单 → 自动下单进正确 WMS → 出库后自动回传赛狐。  
2. 无渠道：告警 + 人工指派后能自动续跑。  
3. 本机/服务器可切换；主路径不依赖 Playwright automation。  
4. 文档（`项目说明.md` / 灰度文档）与真实开关一致。
