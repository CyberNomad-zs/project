export const meta = {
  name: 'review-crosschannel-fix',
  description: 'Adversarially review the cross-channel courier-mis-assignment fix across erp.py/wms.py/run_shipping.py',
  phases: [
    { title: 'Review', detail: 'independent reviewers per dimension read the changed functions' },
    { title: 'Verify', detail: 'adversarially verify each finding by re-reading the code' },
  ],
}

const ROOT = 'E:/project/海外仓/automation'

const CONTEXT = `
背景：修复一个跨渠道快递方误改漏洞。同一个 WMS 账号(JMCAT=黑猫)服务多个 ERP 渠道
(BLACKCAT-RM/DPD/EH)，被 CHANNEL_ORDER 连续处理3次；WMS「平台订单·未发货」是共享池。
旧代码 process_shop 无差别【全选】未发货列表 -> 上一渠道发货失败遗留的单会被下一渠道全选卷入、
改成错误快递方并误发(如 DPD 遗留单在 EH 阶段被改成 EH)。

修复方案（方案一，精确按订单号勾选）已实现，改动如下：
1) erp.py: 新增 read_order_ids(page) 读 vxe 表格订单号；place_logistics_orders 在渠道筛选后、
   点物流下单前读下本渠道订单号，随结果返回 channel_orders（所有返回路径都带；含分页告警）。
2) wms.py: 新增 select_orders(page, order_set) 只勾选属于本渠道订单号的行(Element el-table 每行有
   selection 复选框；固定列致行重复，按订单号去重、每单点一次；Playwright 真实点击)。
   process_shop 新增 target_orders 参数：传入=精确模式(只勾/改/发本集合)，None=旧全选模式(自测/手动)。
   精确模式：present=当前页∩target；本渠道单一个都没读到时重试等同步；left/fail 只统计 target 内的单
   (其它渠道遗留单不算本渠道失败)；before 用 work_count；空 target 直接跳过+留存(绝不回退全选)。
   ship_shop 新增 target_orders 透传。
3) run_shipping.py: run_pipeline 把 ERP 返回的 channel_orders 传给 ship_shop；channel_orders 为空
   则跳过+留存(不让 WMS 退回全选)；WMS 返回 error 也纳入 failures 汇总。
4) capture/wms_rotation_selftest.py: mock 支持精确选择；新增2个跨渠道回归用例，全部8个通过。

安全底线设计：任何读取失败/为空/选不中，都【跳过并留存交人工】，绝不回退全选、绝不误改其它渠道单。
`

const DIMENSIONS = [
  {
    key: 'wms-precise-selection',
    prompt: `${CONTEXT}
请仔细阅读 ${ROOT}/wms.py 里的 select_orders、process_shop（精确模式相关全部逻辑）。
以【对抗找 bug】的心态审查正确性：
- select_orders 的行去重、复选框定位(.el-table-column--selection .el-checkbox / .el-checkbox)、
  is-checked 跳过、findall 挑 want 中的订单号——有没有会导致【误选其它渠道单】或【漏选本渠道单】的情形？
- process_shop 精确模式下 present/work_count/all_orders/left_orders/remote 的 target 过滤是否自洽？
  偏远筛选后重新选择、_recheck_unshipped 后按 tset 过滤 left 是否会误报/漏报本渠道失败？
- 同步重试循环(while not present)会不会死循环/误触发/在 target 部分缺失时表现异常？
- 有没有任何路径会退化成全选或误改/误发其它渠道遗留单（这是必须为零的）？
只报你能给出【具体触发输入/状态 -> 错误结果】的真实问题。没有就报空。`,
  },
  {
    key: 'erp-capture-pagination',
    prompt: `${CONTEXT}
请阅读 ${ROOT}/erp.py 里的 read_order_ids 和 place_logistics_orders（本次改动部分）。
对抗审查：
- read_order_ids 用 .vxe-body--row + 正则 P[0-9A-Z]{9,15} 去重读订单号，会不会读到订单号以外的串、
  或漏读、或在固定列/虚拟滚动下只读到部分？
- place_logistics_orders 是否在【渠道筛选之后、点物流下单之前】读取，确保 channel_orders 确是本渠道的单？
  所有返回路径(0单/全选失败/DRY/按钮未找到/点击异常/正常)是否都带 channel_orders，且值正确？
- 分页时 channel_orders 少于 n 只是告警不阻断，会不会造成 WMS 精确模式漏发且无人知？告警是否足够？
只报具体的真实问题（给出触发场景）。没有就报空。`,
  },
  {
    key: 'runshipping-control-flow',
    prompt: `${CONTEXT}
请阅读 ${ROOT}/run_shipping.py 的 run_pipeline（本次改动部分）与它如何消费 ERP/WMS 返回。
对抗审查：
- channel_orders 为空时跳过+留存的判断，会不会误伤【本就 0 单】的正常渠道（把 0 单当异常留存）？
  注意上游 placed(success/count) 的判断顺序：placed 为真但 channel_orders 空 才进这个分支——是否正确？
- ship_shop(target_orders=channel_orders) 透传是否正确？res.get('error') 纳入 failures 是否与
  process_shop 的各种 error 返回(无快递方/登录失败/查询失败/无本渠道订单号)一致、不重复不遗漏？
- failures 里空 orders 的条目在 write_failures/_fmt_failures/notify_shipping 是否安全、可见？
只报具体真实问题（给出触发场景）。没有就报空。`,
  },
  {
    key: 'regression-and-legacy',
    prompt: `${CONTEXT}
请阅读 ${ROOT}/wms.py(process_shop/ship_shop)、${ROOT}/capture/wms_rotation_selftest.py，
并结合其它调用方(full_loop.py/shipping_loop.py/capture/wms_fix_verify.py)。
对抗审查【本次改动是否引入回归】：
- target_orders=None 的旧全选模式行为是否与改动前【完全一致】？(自测6个legacy用例的语义)
- 新增参数 target_orders 插在 already_logged_in 之前，会不会打乱任何位置传参的调用方？
- 自测 mock 的 select_orders/batch_ship/courier_of 建模是否真实反映生产逻辑、
  两个新回归用例是否真的能在【旧全选逻辑下失败】(即测试有效)？
- 有没有生产调用路径没传 target_orders 而应该传（导致精确修复在某条路径上失效、仍会误发）？
只报具体真实问题（给出触发场景）。没有就报空。`,
  },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          detail: { type: 'string' },
          trigger: { type: 'string', description: '具体触发输入/状态 -> 错误结果' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['title', 'file', 'detail', 'trigger', 'severity'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    real: { type: 'boolean', description: 'true=确认是真bug/真回归；false=不成立或误报' },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['real', 'reason', 'severity'],
}

const results = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }),
  (review, d) => parallel((review.findings || []).map(f => () =>
    agent(
      `对抗验证以下疑似问题是否【真实成立】。请【亲自重新阅读相关源码】(${ROOT} 下对应文件)再下结论，
默认怀疑、能证伪就证伪。特别注意本修复的安全底线：任何读取失败/为空都会【跳过+留存、绝不回退全选】，
所以「可能漏发但会留存告警」通常是【设计内的安全行为】而非 bug；只有【会误发/误改其它渠道单】或
【静默漏发且无任何留存/告警】才算 high。\n\n疑似问题：\n标题：${f.title}\n文件：${f.file}\n描述：${f.detail}\n触发：${f.trigger}`,
      { label: `verify:${d.key}:${(f.title || '').slice(0, 20)}`, phase: 'Verify', schema: VERDICT_SCHEMA }
    ).then(v => ({ dimension: d.key, finding: f, verdict: v }))
  ))
)

const all = results.flat().filter(Boolean)
const confirmed = all.filter(x => x.verdict && x.verdict.real)
return {
  total_findings: all.length,
  confirmed: confirmed.map(x => ({
    dimension: x.dimension,
    title: x.finding.title,
    file: x.finding.file,
    severity: x.verdict.severity,
    trigger: x.finding.trigger,
    reason: x.verdict.reason,
  })),
  dismissed: all.filter(x => !(x.verdict && x.verdict.real)).map(x => ({ title: x.finding.title, why: x.verdict && x.verdict.reason })),
}
