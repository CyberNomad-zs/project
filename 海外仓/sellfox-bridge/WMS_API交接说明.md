# WMS 客户 API 交接说明

> 更新：2026-08-04  
> 适用项目：`sellfox-bridge`（赛狐 ↔ 海外仓 WMS 发货桥接）  
> 代码位置：`bridge/clients/wms.py`  
> 相关总文档：`项目说明.md`、`业务层说明.md`、`对齐记录_业务语义.md`

---

## 1. 一句话定位

本项目使用的是 **WMS 对客户开放的 remote 接口**（只读查询为主），不是网页后台接口，也不是仓内作业接口。

| 做 | 不做 |
|---|---|
| 查订单出库状态 | 改快递方 |
| 查运单号 / 承运商 | 批量发货 / 预发货 |
| 查库存 / 商品信息（辅助） | 拣货、打单、偏远筛选 |
| 按双客户账本对账 | 重建赛狐→WMS 推单通道 |

**推单到 WMS 不走本 API**：赛狐侧 `applyTrackNo` 经内置三方仓通道把包裹推进 WMS。  
**仓内发货仍由 WMS 网页/仓内作业完成**（旧 `automation/wms.py` 是网页自动化，与本 API 无关）。

---

## 2. 环境与账号

### 2.1 服务地址

```text
http://193.112.93.60:9999
```

同机部署时可改为 `http://127.0.0.1:9999`（见 `部署_固定IP清单.md`）。

### 2.2 双客户账本（关键）

同一 `base_url`，**两套 key / api_secret**，账本完全隔离：

| profile 名 | 业务含义 | 对应赛狐渠道后缀 | 网页登录习惯名 |
|---|---|---|---|
| `jinmao` | 金猫商贸 WMS | `昇新海外仓-昇新海外仓-RM/DPD` | JMSM / 金猫商贸 |
| `blackcat` | 黑猫 WMS | `昇新海外仓-BLACKCAT-RM/DPD/EH` | JMCAT / 黑猫 |

**交叉查询一定查无**：BLACKCAT 单用金猫 key 查 = 正常无单；昇新单用黑猫 key 查也一样。  
排错时先确认用对了 profile，再谈「漏推仓」。

### 2.3 密钥存放

真实密钥在配置文件（**已 gitignore，勿提交、勿外传**）：

- 生产常用：`config/config.g2-3shops.yaml`
- 模板：`config/config.example.yaml`
- 结构：

```yaml
wms:
  base_url: http://193.112.93.60:9999
  profiles:
    jinmao:
      key: <客户 key，整数>
      api_secret: "<密钥>"
    blackcat:
      key: <客户 key，整数>
      api_secret: "<密钥>"
  default_profile: jinmao
```

渠道上通过 `wms_profile: jinmao|blackcat` 指定 step4 / recon 用哪把 key。

---

## 3. 鉴权（已实测，必须严格按此）

实现见 `bridge/clients/wms.py`。

### 3.1 请求方式

- 方法：`POST`
- Content-Type：`application/json`
- 路径前缀：`{base_url}{path}`
- HTTP 客户端：`requests.Session()`，且 **`trust_env = False`**（直连，不走系统代理）

### 3.2 签名字段（每个 remote 接口统一）

| 字段 | 说明 |
|---|---|
| `key` | `wms_user_account_info.id`（整数） |
| `timestamp` | **秒级** Unix 时间戳 |
| `sign` | `MD5(key + api_secret + timestamp)` 的 **大写** hex |

伪代码：

```python
import hashlib, time

ts = int(time.time())
sign = hashlib.md5(
    f"{key}{api_secret}{ts}".encode()
).hexdigest().upper()   # 必须大写！

body = {
    "key": int(key),
    "timestamp": ts,
    "sign": sign,
    # ... 业务字段
}
```

### 3.3 服务端约束

- 时间窗约 **±300 秒**，机器时间不准会签名失败。
- 服务端 `Common.MD5` 返回大写并区分大小写比对 → **小写 sign 必失败**。
- 业务字段与签名字段放在**同一个 JSON body**。

### 3.4 统一响应结构

```json
{
  "success": true,
  "message": "...",
  "systemCode": 0,
  "data": ...
}
```

注意：

1. `success=false` 时抛 `WmsError`，日志带 `message` + `systemCode`。
2. **`data` 有时是 JSON 字符串**（服务端 `JSONArray.toString`），客户端会再 `json.loads` 一次；解析失败则原样返回字符串。
3. 业务代码拿到的是「已解包后的 `data`」，不是整包响应。

---

## 4. 已封装接口清单

客户端类：`bridge.clients.wms.WmsClient`

| 方法 | Path | 入参 | 用途 | 主调用方 |
|---|---|---|---|---|
| `query_order_status` | `/orderInfo/remote/queryOrderStatus.html` | `platformOrderNo` | 查出库状态 | `pipeline.step4`、`recon` |
| `query_tracking_number` | `/orderInfo/remote/queryTrackingNumber.html` | `platformOrderNo` | 查运单号 + 承运商 | `pipeline.step4`、`recon` |
| `query_inventory` | `/customer/remoteQueryInventory.html` | 可选 `page`,`size` | 客户库存列表 | 联调/辅助 |
| `query_product_info` | `/customer/remoteQueryProductInfo.html` | 可选 `page`,`size` | 商品信息 | 联调/辅助 |

### 4.1 关联键（最重要业务字段）

```text
赛狐 packageSn  ==  WMS platformOrderNo
```

例：`P2AS6TCD63996`  
**不要**用亚马逊平台单号（`204-xxxx`）当 `platformOrderNo` 去查——那是另一列。

### 4.2 出库状态 `orderStatus`（Constants.java 实测）

| 值 | 含义 |
|---|---|
| `0` | 待发货 |
| `1` | 预发货 |
| `2` | 已发货 |
| `4` | 平台已发货 |

闭环判定（代码常量 `WMS_SHIPPED_STATUSES`）：

```text
orderStatus ∈ {2, 4}  AND  trackingNumber 非空
```

原因：存在 **状态已是 2，但运单尚未生成** 的中间态；只看状态会误回传。

### 4.3 运单查询返回字段（业务用到的）

| 字段 | 含义 | 用法 |
|---|---|---|
| `trackingNumber` | 运单号 | 回传赛狐 / 对账 |
| `express` | 实际承运商，如 `RM`/`DPD`/`EH` | 与赛狐渠道 `expected_carrier` 比对 |

### 4.4 库存查询返回字段（辅助）

```text
[{ code(sku), num, boxNum, name }, ...]
```

---

## 5. 在业务流水线里怎么用

### 5.1 整体不碰 WMS 写接口

```text
step1 发现待处理     → 只调赛狐
step2 认/保留渠道    → 只调赛狐（当前主路径：保留已有渠道）
step3 物流下单       → 赛狐 applyTrackNo（赛狐内部推 WMS）
step4 出库回传闭环   → ★ 这里才查 WMS API
recon 每日对账       → ★ 只读查 WMS API
```

### 5.2 step4 逻辑摘要（`bridge/pipeline.py`）

对本地状态 `ORDERED` 的每一单：

1. 按渠道名选 WMS profile（`_wms_for_channel`）
2. `query_order_status(packageSn)`  
   - 文案含「未查询/不存在/no order」→ **正常延迟**，下轮再查，不算失败  
   - 状态不在 `{2,4}` → 下轮再查
3. `query_tracking_number(packageSn)`  
   - 无运单 / 「未生成」→ 下轮再查
4. **渠道一致性**（`hold_on_channel_mismatch: true`）：  
   赛狐 `expected_carrier`（RM/DPD/EH）须被 WMS `express` 包含；不一致 → **暂停回传 + 飞书告警**，人工在 WMS 改回正确快递方后自动恢复
5. 回传赛狐（非 WMS API）：  
   - 有重量 → `weighingShipment`  
   - 无重量 → `quickOutbound`（`ship_confirm_mode: auto`）

### 5.3 渠道 → WMS profile 映射

| 赛狐 channelName（完整） | config.name | expected_carrier | warehouse_id | wms_profile |
|---|---|---|---|---|
| 昇新海外仓-BLACKCAT-RM | BLACKCAT-RM | RM | 187323 | **blackcat** |
| 昇新海外仓-BLACKCAT-DPD | BLACKCAT-DPD | DPD | 187323 | **blackcat** |
| 昇新海外仓-BLACKCAT-EH | BLACKCAT-EH | EH | 187323 | **blackcat** |
| 昇新海外仓-昇新海外仓-RM | 昇新海外仓-RM | RM | 180617 | **jinmao** |
| 昇新海外仓-昇新海外仓-DPD | 昇新海外仓-DPD | DPD | 180617 | **jinmao** |

匹配规则：`channelName.endswith(config.name)`。  
兜底：渠道名含 `BLACKCAT` → `blackcat`，否则 `default_profile`（jinmao）。

### 5.4 对账 `recon.py`

- 拉赛狐近 N 天 `has_shipped`
- 白名单店铺逐单按渠道选正确 WMS key
- 核对：是否存在、运单号、承运商、双边运单是否一致
- 高优告警示例：  
  - `WMS_MISSING` / `WMS_MISSING_BLACKCAT`：正确账本仍查无 → 疑似未推仓  
  - `CARRIER_MISMATCH`：快递方不一致  
  - `TRACKING_MISMATCH`：双边运单号不一致

本机：

```powershell
cd E:\project\海外仓\sellfox-bridge
.\run_recon_now.ps1
# 或
python recon.py --config config\config.g2-3shops.yaml
```

---

## 6. 最小可跑通示例（同事自测）

**不要把 secret 写进聊天/文档。** 从本机 config 读。

```python
import yaml
from bridge.clients.wms import WmsClient

cfg = yaml.safe_load(open("config/config.g2-3shops.yaml", encoding="utf-8"))
base = cfg["wms"]["base_url"]
p = cfg["wms"]["profiles"]["jinmao"]  # 或 blackcat

wms = WmsClient(base, p["key"], p["api_secret"])

# 1) 连通性：库存
inv = wms.query_inventory(page=1, size=5)
print("inventory sample:", inv[:1] if isinstance(inv, list) else inv)

# 2) 用已知 packageSn 查状态/运单（昇新单用 jinmao，BLACKCAT 单用 blackcat）
sn = "P2AS6TCD63996"  # 换成真实单号
print(wms.query_order_status(sn))
print(wms.query_tracking_number(sn))
```

或走项目入口只读演练：

```powershell
python main.py --config config\config.g2-3shops.yaml --dry-run --once
```

---

## 7. 与「网页 WMS / 旧 automation」边界

| 能力 | API（本交接） | 网页 automation（`E:\project\海外仓\automation\`） |
|---|---|---|
| 登录 | key+sign | 账号密码登录页 |
| 查状态/运单 | ✅ remote | DOM 读表 |
| 改快递方 | ❌ | ✅ 批量修改快递方 |
| 偏远=否筛选 | ❌ | ✅ |
| 批量发货/预发货 | ❌ | ✅ |
| 金猫/黑猫隔离 | 两把 key | 独立 browser context（曾踩串会话坑） |

**三店 G2 已上 API 桥接后**：Agnis / HomeCove / Twilight Cove **不要再对这三店跑 automation 全流程真跑**，防双下单。其它店可照旧。

网页侧曾抓到但 **bridge 未用** 的后台接口（cookie 会话，非 remote 签名）：

- `POST /orderInfo/searchByPage.html`
- `POST /loginIn.html`
- `POST /expressInfo/getWmsExpressInfos.html`
- `POST /customer/getStoreList`

这些不能当客户 API 文档用；客户侧只认 §4 的 remote 路径。

---

## 8. 排错速查

| 现象 | 原因 / 处理 |
|---|---|
| 签名失败 / systemCode 异常 | sign 是否**大写**；本机时间是否在 ±300s；key/secret 是否配错 profile |
| BLACKCAT 单「查无」 | 是否误用 `jinmao` key → 改 `blackcat` |
| 昇新单「查无」 | 是否误用 `blackcat`；或刚下单同步延迟（step4 会自动下轮重试） |
| 状态=2 但一直不闭环 | 看 `trackingNumber` 是否仍空；等运单生成 |
| 承运商不一致暂停回传 | 赛狐渠道末段 vs WMS 实际 express；仓内改回一致后自动恢复 |
| 走了系统代理连不上/怪错 | 确认 `Session.trust_env = False` |
| 用 `204-` 平台单号查无 | 必须用赛狐 `packageSn`（`P…`） |

---

## 9. 代码与文档索引

| 路径 | 内容 |
|---|---|
| `bridge/clients/wms.py` | 客户端全文（鉴权 + 4 个方法） |
| `main.py` → `build_wms_clients` | 从 config 构建 `{profile: WmsClient}` |
| `bridge/pipeline.py` | step4 闭环、状态常量、profile 选择 |
| `recon.py` | 只读对账 + classify 规则自测 |
| `config/config.example.yaml` | 配置模板（无真密钥） |
| `config/config.g2-3shops.yaml` | 生产三店配置（有密钥，gitignore） |
| `项目说明.md` | 总交接 |
| `业务层说明.md` | 流水线业务规则 |
| `对齐记录_业务语义.md` | 双账本实测结论 |
| `部署_固定IP清单.md` | 迁服务器时 WMS/赛狐 IP 事项 |

---

## 10. 交接 checklist（给同事）

- [ ] 能读到本机/服务器上的 `config.g2-3shops.yaml`（含双 profile 密钥）
- [ ] 用 `jinmao` / `blackcat` 各跑通一次 `query_inventory` 或已知单号查询
- [ ] 理解 `packageSn == platformOrderNo`
- [ ] 理解 `orderStatus` + 运单号双条件闭环
- [ ] 理解五渠道 → 两 profile 映射，交叉查无是正常现象
- [ ] 知道 **API 不负责仓内改快递/批量发货**
- [ ] 知道密钥不得进 Git / 聊天明文
- [ ] 需要扩接口时：优先让 WMS 方（供应商）补 remote 文档；网页 XHR 仅作参考

---

## 11. 已知缺口 / 不要误以为 API 已覆盖

1. **无 remote 写接口**：改快递、批量发货、设偏远等仍不在客户 API 范围。  
2. **`sku_weights` 可为空**：不影响查 WMS；只影响赛狐称重回传是否走 quick。  
3. **推仓延迟**：下单后数分钟内查无是常态，不要当成漏单刷告警。  
4. **店铺白名单外的店**（如未授权 Amazon）禁止接入 bridge。  
5. 若 WMS 方后续新增 remote 接口，在 `WmsClient` 按同样签名方式加方法即可，流水线按需接入。
