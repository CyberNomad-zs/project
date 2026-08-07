---
name: sellfox-bridge-api
description: API 模式桥接程序 sellfox-bridge（赛狐↔WMS 官方API替代网页自动化）的状态与环境
metadata: 
  node_type: memory
  type: project
  originSessionId: aa066cc0-2f4a-4f01-a9b4-06d37573a1ef
---

海外仓发货的 **API 模式**（替代 Playwright/扩展的网页自动化）——供应商(WMS方,Mac开发者zavier)已打通赛狐开放API+WMS客户API，交付独立常驻程序 `E:\project\海外仓\sellfox-bridge\`（Python，requests+PyYAML）。用户负责中间业务层对接、可安排 IP 白名单。相关：[[haiwaicang-fahuo-flow]]。

**架构**：不参与货流，只做 触发/渠道决策/闭环回传/对账。四步幂等流水线 `bridge/pipeline.py`：step1_discover(拉赛狐to_process包裹)→step2_assign(选渠道updatePackageDetail)→step3_order(applyTrackNo推WMS)→step4_close(轮询WMS出库状态→称重发货weighingShipment回传赛狐)。本地状态机 SQLite `bridge.db`：NEW→CHANNEL_ASSIGNED→ORDERED→WMS_SHIPPED→CLOSED，失败→FAILED。客户=金猫商贸(1赛狐账号↔1WMS客户)。交接文档 `sellfox-bridge/项目说明.md`（详尽，含双边API/签名/对账结论/待办）。

**✅本机环境已就绪并实测通过(2026-07-16)**：
- Python 3.12.10；已 `pip install requests PyYAML`。
- **真实配置在项目根 `E:\project\海外仓\config.yaml`**（含双边密钥+渠道表+店铺白名单），bridge 读 `config/config.yaml`——已拷贝一份进去。改配置改哪个都行但注意两份。
- **⚠️赛狐IP白名单：这台Windows机器【已放行】**——业务接口 queryShipChannel 实测返回5渠道(未放行会报 code=40005)，故当前无需为本机加白。token接口不校验IP、业务接口才校验。（项目说明里白名单写的是供应商Mac家宽49.77.234.254等，会变；正式部署建议迁 WMS 服务器193.112.93.60固定IP。）
- **三边连通实测OK**：赛狐token✅、赛狐业务(渠道5条)✅、赛狐拉包裹(当时to_process=3单)✅、WMS签名(查库存)✅。
- **DRY端到端跑通**：`python -X utf8 main.py --dry-run --once` 正常，3待处理单都自带可用渠道→keep_existing_channel保留(BLACKCAT-RM/昇新-RM×2)，无写操作。

**当前灰度安全档位(config.run)**：`auto_apply_track_no:false`(step3物流下单关闭)、`keep_existing_channel:true`(已有渠道不动)、`hold_on_channel_mismatch:true`(渠道以赛狐为基准，WMS不一致则暂停+告警)。→ **写操作(step2指派/step3下单/step4回传)从未真跑过**。放开写=灰度上线，属外向不可逆(真下物流单)，须用户确认。

**关键业务事实(项目说明§6实测)**：双边关联键 赛狐packageSn==WMS platformOrderNo。金猫授权店铺白名单=Temu三店 Agnis(396706)/HomeCove(398202)/Twilight Cove(398203)，Amazon两店WMS未授权。渠道映射5条(BLACKCAT-RM/DPD/EH→仓187323、昇新-RM/DPD→仓180617)。**BLACKCAT渠道单不进金猫WMS账**(对账47单查无)→闭环只对昇新渠道有效，BLACKCAT归属待确认。WMS orderStatus:0待发/1预发/2已发/4平台已发，存在"状态2但运单未生成"故闭环用双条件(状态+运单号)。

**主要缺口/待办**：①`sku_weights:{}`空→无渠道的包裹算不出重量、称重发货无兜底重量(可改 ship_confirm_mode:quick 用 quickOutbound 免重量)；②渠道价卡 cost_* 全0→selector 只能"保留现有渠道"；③写操作全未验证；④待审核阶段SOP(地址修剪/审核/拆包)未实现；⑤部署迁WMS服务器+飞书webhook。
