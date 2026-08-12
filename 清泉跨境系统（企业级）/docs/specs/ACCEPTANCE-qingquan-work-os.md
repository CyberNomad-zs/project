# ACCEPTANCE: 清泉运营工作操作系统 1.0（人与过程数据层）

| 字段 | 值 |
|------|-----|
| Spec ID | SPEC-20260728-qingquan-work-os |
| 状态 | ready |

---

## 约定

- 场景可在 <5 分钟内判定 pass/fail  
- 禁止不可测措辞  
- 主功能均含 ≥1 happy + ≥1 error  

---

## 功能 F1: 信号建案

### Happy

```gherkin
Scenario: F1-H1 Temu 告警建成 open Case
  Given 接入层收到一条 Temu 下架或限流告警且带稳定 source_ref
  When 系统处理该信号
  Then 存在一条 case_type=temu_alert 且状态为 open 的 Case
  And 时间线含一条 create 事件且带时间戳
```

```gherkin
Scenario: F1-H2 TK 风险行与仓例外可建案
  Given 接入层分别收到一条 tiktok_risk 信号与一条 fulfillment_exception 信号
  When 系统处理这些信号
  Then 各产生一条对应 case_type 的 open Case
```

### Error / 边界

```gherkin
Scenario: F1-E1 重复信号不产生第二个 open Case
  Given 已存在 case_type 与 source_ref 相同且状态为 open 的 Case
  When 接入层再次推送同一幂等键的信号
  Then open Case 总数不增加
  And 系统记录忽略或追加事件（二选一，行为在实现中固定并文档化）
```

---

## 功能 F2: 员工工作台闭环

### Happy

```gherkin
Scenario: F2-H1 认领并关闭且时间线完整
  Given 存在状态为 open 的 Case
  And 当前用户角色为 operator
  When 用户认领该 Case
  And 填写 disposition_code 与非空 rationale
  And 选择 outcome_label 后关闭
  Then Case 状态为 closed
  And 时间线按序包含 claim 与 close 事件
  And 每条事件含 actor_id 与 ts
```

### Error / 边界

```gherkin
Scenario: F2-E1 未认领不可关闭
  Given 存在状态为 open 且未被当前用户认领的 Case
  When 当前用户尝试直接关闭
  Then 关闭失败并显示明确错误
  And Case 状态仍为 open
```

```gherkin
Scenario: F2-E2 缺少处置字段不可关闭
  Given 当前用户已认领某 Case
  When 用户在未填 disposition_code 或 rationale 为空时关闭
  Then 关闭失败并提示必填字段
  And Case 状态仍为 claimed
```

---

## 功能 F3: 管理层监督台（B）

### Happy

```gherkin
Scenario: F3-H1 按人查看待办与超时
  Given 用户 A 有一条已超时未关闭的 Case
  And 当前用户角色为 manager
  When 经理在监督台按负责人筛选用户 A
  Then 列表包含该 Case
  And 该 Case 显示超时标识
```

```gherkin
Scenario: F3-H2 打开案件可见完整时间线
  Given 某 Case 已有 create、claim、close 事件
  When 经理打开该 Case 详情
  Then 页面按时间顺序展示上述事件及 disposition_code、rationale、outcome_label
```

### Error / 边界

```gherkin
Scenario: F3-E1 运营不可看全局监督台
  Given 当前用户角色为 operator
  When 用户访问管理层监督台路由或 API
  Then 请求被拒绝（403 或等价）
  And 不返回其他负责人的全量案件列表
```

---

## 功能 F4: 飞书群通知（P0 必做）与平台主体

### Happy

```gherkin
Scenario: F4-H1 新建案推到飞书群并带深链
  Given 已配置飞书群机器人与店铺到群的映射
  And 已配置该案应 @ 的相关人
  When 系统创建一条新 Case
  Then 向对应飞书群发送一条消息
  And 消息含平台深链与案件摘要
  And 消息尝试 @ 相关人（或飞书等价提醒）
```

```gherkin
Scenario: F4-H2 超时案再次群提醒
  Given 存在已超过关闭或认领 SLA 且未关闭的 Case
  And 飞书群通知已配置
  When 系统执行超时通知检查
  Then 向对应飞书群发送超时提醒（同一案在防刷窗口内不重复刷屏）
```

### Error / 边界

```gherkin
Scenario: F4-E1 飞书失败不影响建案与处理
  Given 飞书群机器人返回失败或超时
  When 系统创建 Case 且运营完成认领关闭
  Then Case 仍成功创建并关闭
  And 通知失败被记录可查
```

```gherkin
Scenario: F4-E2 本期不要求个人私聊路由
  Given 系统为 1.0 / MVP
  When 检查通知配置与发送逻辑
  Then 默认通知渠道为飞书群
  And 不存在「按级别自动改发个人」的必做验收项（属下版）
```

---

## 功能 F5: 自创字段与 C 预留

### Happy

```gherkin
Scenario: F5-H1 关闭时可标记误报并查询
  Given 运营已认领 Case
  When 运营关闭时设置 false_positive=true 并填写 rationale
  Then 该 Case 可被按 false_positive 筛选查出
```

```gherkin
Scenario: F5-H2 C 预留字段存在且无建议功能
  Given 系统已部署 1.0
  When 检查 Case 数据模型与产品 UI
  Then 存在 disposition_code、rationale、outcome_label 字段可读写
  And 不存在「智能建议处置」或自动执行写回电商平台的入口
```

### Error / 边界

```gherkin
Scenario: F5-E1 无权限用户不能改 SLA 配置
  Given 当前用户角色为 operator
  When 用户尝试修改默认 SLA
  Then 操作被拒绝
```

---

## Edge 清单（汇总，≥ 3）

| ID | 描述 | 期望行为 | 对应 Scenario |
|----|------|----------|---------------|
| E1 | 重复信号 | 不双开 open Case | F1-E1 |
| E2 | 未认领关闭 | 拒绝 | F2-E1 |
| E3 | 缺处置字段关闭 | 拒绝 | F2-E2 |
| E4 | 运营访问监督台 | 拒绝 | F3-E1 |
| E5 | 飞书失败 | 平台闭环仍成功 | F4-E1 |
| E6 | 通知渠道范围 | 本期群通知；个人路由非必做 | F4-E2 |

---

## 可勾选验收（发布/Demo 用）

### MVP Demo（与 `MVP-qingquan-work-os.md` Success check 对齐）

- [ ] Temu 告警或夹具 → Case → operator 认领关闭（disposition + rationale）→ 时间线完整
- [ ] manager 监督台按人筛到该案；另有 1 条超时 open 案显示超时标识
- [ ] **飞书群收到新建或超时通知（含深链）**
- [ ] UI 无「智能建议」；飞书失败时平台闭环仍可演示且有失败记录
- [ ] 原型对照：`docs/mocks/mvp-qingquan-work-os.html` 信息架构获确认

### P0

- [ ] F1-H1 / F1-E1
- [ ] F2-H1 / F2-E1 / F2-E2
- [ ] F3-H1 / F3-H2 / F3-E1
- [ ] F4-H1 / F4-E1
- [ ] F5-H1 / F5-H2

### P1（可选）

- [ ] F4-H2 超时二次群提醒
- [ ] F1-H2 三线均有真源接入（非夹具）

---

## 验证记录

| 日期 | 人/命令 | 结果 | 备注 |
|------|---------|------|------|
| | | pass/fail | |
