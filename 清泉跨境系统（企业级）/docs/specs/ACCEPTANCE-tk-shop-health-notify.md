# ACCEPTANCE: TK 店铺健康/体验/达人 飞书双通道提醒与体验分进表

| 字段 | 值 |
|------|-----|
| Spec ID | SPEC-20260811-tk-shop-health-notify |
| 状态 | ready |

---

## 功能 F1: 账号健康分双通道提醒

### Happy

```gherkin
Scenario: F1-H1 健康分任意下降触发任务+群+私信
  Given 店铺 S 在 stores.config 中且上次健康分快照为 200
  And 群 webhook 与私信 user_id 均已配置
  When 当日采集健康分为 199 并完成评估
  Then 存在 anomaly_code=shop_health_drop 的 open 任务
  And 群机器人收到含店铺名与 199/200 的消息
  And 宋敏飞书私信收到同类内容（或测试环境等价 mock 成功回执）
```

```gherkin
Scenario: F1-H2 健康分≤150 触发低分规则
  Given 店铺 S 当日健康分=150
  When 评估运行
  Then 存在 anomaly_code=shop_health_low 的任务
  And 通知标题或正文含红线 150
```

### Error / 边界

```gherkin
Scenario: F1-E1 无私信配置时不阻断群与任务
  Given FEISHU 私信 user_id 未配置
  And 健康分触发下降
  When 评估运行
  Then 异常任务已写入
  And 群消息仍发送（webhook 已配时）
  And 日志记录私信跳过原因
```

---

## 功能 F2: 店铺体验分与三模块进表

### Happy

```gherkin
Scenario: F2-H1 体验分总分下降提醒
  Given 店铺 S 上次体验分总分=3.9
  When 采集到总分=3.8 并评估
  Then 产生体验分下降类异常任务
  And 群与私信双通道均尝试发送
```

```gherkin
Scenario: F2-H2 三模块写入飞书新表
  Given TK 驾驶舱 Base 已建体验分日表且 table_id 已配置
  When 店铺 S 当日体验分三模块采集成功并同步
  Then 飞书新表存在 S 当日一行
  And 行内含商品满意度、履约物流、客户服务分数（或约定字段名）
```

### Error / 边界

```gherkin
Scenario: F2-E1 飞书同步失败 PG 仍有事实
  Given bitable token 无效
  When 体验分采集 Ingest 成功后同步飞书
  Then PG 体验分事实表已有当日行
  And 同步错误可观测（日志或任务标记）
  And 不删除已写入的 PG 行
```

---

## 功能 F3: 达人健康多账号

### Happy

```gherkin
Scenario: F3-H1 切换账号列表内每个达人采集健康分
  Given 店铺 S 达人切换列表含 N 个账号（N≥2）
  When 达人健康模块跑完
  Then PG 中该店当日至少 N 条达人健康快照（账号标识可区分）
```

```gherkin
Scenario: F3-H2 单达人分数下降提醒
  Given 达人账号 C 上次健康分=200
  When 采集到 170
  Then 任务/通知正文可区分店铺 S 与达人 C
```

### Error / 边界

```gherkin
Scenario: F3-E1 达人列表为空
  Given 页面未展示任何达人账号
  When 模块执行
  Then 模块结果为可识别失败或 skip
  And 不写入虚假达人行
```

---

## 功能 F4: 差评与达人违规

### Happy

```gherkin
Scenario: F4-H1 新增 1★ 或 2★ 差评双通道提醒
  Given 评价 R 首次进入系统且 rating≤2
  When 差评评估运行
  Then 产生差评类异常任务
  And 群与私信均尝试通知
```

```gherkin
Scenario: F4-H2 达人新增违规提醒
  Given 达人 C 出现此前未见的违规记录 V
  When 违规评估运行
  Then 任务绑定达人 C 与违规摘要
  And 双通道尝试通知
```

### Error / 边界

```gherkin
Scenario: F4-E1 重复差评不重复刷屏
  Given 评价 R 已建 open 任务且指标未继续恶化
  When 再次日更评估
  Then 不重复发送群/私信（仅刷新任务允许）
```

---

## 功能 F5: 全店范围与通道并存

### Happy

```gherkin
Scenario: F5-H1 stores.config 多店均调度
  Given 主配置含至少 2 个 enabled 店
  When 日更 shop 健康相关模块执行
  Then 每个 enabled 店都有尝试记录（成功或失败日志）
```

### Error / 边界

```gherkin
Scenario: F5-E1 单店失败不阻断他店
  Given 店 A 采集超时失败
  And 店 B 正常
  When 批任务结束
  Then 店 B 事实与评估仍完成
```

---

## Edge 清单（≥3）

| ID | 描述 | 期望行为 | Scenario |
|----|------|----------|----------|
| E1 | 无上次快照 | 不报下降类；可报 ≤150 / 新增差评违规 | F1/F2 隐含 |
| E2 | 私信失败 | 任务+群保留 | F1-E1 |
| E3 | 飞书表失败 | PG 保留 | F2-E1 |
| E4 | 达人列表空 | 不写假数据 | F3-E1 |
| E5 | 重复评估 | 不重复刷通知 | F4-E1 |
| E6 | 单店失败 | 他店继续 | F5-E1 |

---

## 可勾选验收（Demo）

### MVP Demo

- [ ] 配置 1 店完整跑通：体验分入 PG + 飞书新表可见  
- [ ] 人为或样例触发 1 次下降类告警：任务 + 群 + 私信三路证据  
- [ ] 达人 ≥2 账号快照进 PG  
- [ ] Secret 未出现在仓库 diff  

### 回归

- [ ] 现网账号健康 ≤150 与任意下降行为仍符合 SPEC §3.3  
- [ ] 关闭私信开关后仅群+任务  
- [ ] 关闭群 webhook 后仅私信+任务  
