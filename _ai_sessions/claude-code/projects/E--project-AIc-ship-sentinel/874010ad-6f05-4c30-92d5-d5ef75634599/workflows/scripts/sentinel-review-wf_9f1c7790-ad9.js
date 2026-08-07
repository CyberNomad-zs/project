export const meta = {
  name: 'sentinel-review',
  description: 'Adversarially review the 发货哨兵 anomaly engine + parsing, critique as a competition judge, and draft a demo script',
  phases: [
    { title: 'Review', detail: '3 independent lenses: engine correctness, parsing/PII/join, judge critique' },
    { title: 'Synthesize', detail: 'prioritized fixes + data strategy + demo script + judge Q&A' },
  ],
}

const FACTS = `
项目：跨境电商 AI 比赛作品「发货哨兵/FulfillSentinel」——只读聚合三系统、抓履约异常的单页看板（2026-07-31 现场演示，单人，"简单好用=高分"，评分偏业务落地价值）。
工程根目录：E:/project/AIc/ship-sentinel
关键文件（用 Read 直接看，绝对路径，正斜杠可用）：
  - backend/xlsx_reader.py  零依赖 xlsx 读取器（绕过赛狐/Temu 导出里错误的 <dimension ref="A1"/>，直接流式解析 sheetN.xml）
  - backend/build.py        ingest 适配器 + 统一订单模型 + 8 类异常引擎 + PII 脱敏 -> unified.json
  - backend/unified.json    构建产物（脱敏后）
  - frontend/index.html     真实数据看板

真实数据事实（2026-07-16 快照）：
  - 赛狐"包裹导出" 505 单 72 列，已聚合 4 平台：Amazon 176 / TikTok 165 / Temu半托管 154 / SHEIN 10；站点全英国。
  - 状态：包裹状态 已发货480/待处理16/已作废9/物流下单少量；订单状态 Shipped/Unshipped/Completed/Canceled。
  - 480 单已发货，当日发货率 99.6%（中位 6.4h，P90 13.4h，仅 2 单>24h）。
  - 16 单待处理里 4 单命中可执行异常；1 单同时"卡虚拟仓+缺发货渠道"。
  - "剩余发货时间"文本形如 "4天15小时26分" / "已超期：0天8小时33分"（超期=负）。仅未发货单有该值。
  - 3 个负值(已超期)单其实都已作废，故 overdue 引擎结果=0（正确）；所有 480 已发货单都有跟踪号，故 no_tracking=0（正确）。
  - Temu 库存表(仓库和库存数据.xlsx 第2个sheet '库存设置'：row0表头、row1是"必填…"说明行需跳过)含"SKU货号/仓库名称/当前库存"，同一货号可能多仓；发现 2 个断货货号 VIP2WCX、VIPR956。
  - WMS 商品导出.xlsx = 商品主数据（SKU/仓库代码/关联ASIN 等 132 行），不是出库单。
  - 跨系统匹配键=内部货号：赛狐 SKU/MSKU ↔ Temu SKU货号 ↔ WMS 仓库代码（样例仅重合 7 个货号，机制成立但覆盖少）。
  - 8 类异常权重：overdue100/stockout95/due_soon80/no_tracking70/stuck_virtual65/stuck_pending50/no_channel40/master_missing20。
  - master_missing=12 是"样例库存仅索引 160 货号"导致的误报，已降级为提示级、不计入 actionable/头条 KPI。
  - PII 已在 build.py 的 KEEP/PII_DROP 层剔除；unified.json 扫描无 email/phone。
`;

const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['lens','findings','verdict'],
  properties: {
    lens: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['severity','title','detail','fix'],
      properties: {
        severity: { type: 'string', enum: ['high','med','low'] },
        title: { type: 'string' },
        detail: { type: 'string', description: '具体证据/失败场景，引用文件与行为' },
        location: { type: 'string' },
        fix: { type: 'string' },
      } } },
    verdict: { type: 'string', description: '总体判断：引擎/解析是否可信、演示是否会翻车' },
  },
};

phase('Review');
const lenses = [
  { key: 'engine', label: 'review:engine', prompt:
    `你是对抗式代码审查者，专攻**异常引擎正确性**。Read backend/build.py（尤其 classify()/parse_remaining()/detect_anomalies()/severity_of() 与 RULES_META）与 backend/unified.json 抽样核对。目标：找出会导致**误报/漏报**或现场演示被评委当场质疑的逻辑问题。逐条检查 8 类规则是否只对正确的订单状态触发；parse_remaining 对 "已超期/超时/天/小时/分" 与空值的鲁棒性；void/shipped/pending 归类是否覆盖"物流下单""Completed""Canceled"等全部真实取值；断货规则 temu_stock<=0 与 matched_code 的耦合；stuck_pending 用"最近下单时间"当 now 是否合理。只报真问题，给可落地修法。` },
  { key: 'parse', label: 'review:parse-join', prompt:
    `你是对抗式审查者，专攻**解析/脱敏/跨系统匹配正确性**。Read backend/xlsx_reader.py 与 backend/build.py 的 build_inventory()/lookup_stock()/build_orders()。检查：错误 <dimension> 绕过是否真的读全行；共享字符串/inlineStr 处理；Temu 两张表的表头行/说明行偏移（'库存设置' 跳 row1、'商品库存列表' 表头在 row1）是否会串列；同一货号多仓库存累加是否正确、会不会把"选填空库存"当 0；PII 剔除是否**彻底**（KEEP/PII_DROP 是否漏了买家留言/收件人等，或订单备注可能含 PII）；匹配键优先级 SKU>MSKU>订单商品编码 是否会误配。只报真问题。` },
  { key: 'judge', label: 'review:judge', prompt:
    `你是比赛评委视角的**业务价值批评者**。基于 FACTS 与 Read frontend/index.html 的看板结构，评估这份作品在 "简单好用=高分、偏业务落地价值" 评分下的强项与硬伤。重点回答：①快照"太平静"(仅4单需处理、0严重)会不会让演示缺乏冲击力？如何在**只读、不写生产**约束下把真实价值讲清楚而不显单薄。②master_missing=12 这类样例误报会不会被评委抓？③哪些**额外导出/数据**能最大提升业务说服力（如早晨/积压快照、全量WMS主数据、WMS出库单、Temu订单、历史超时罚款）。④现场最可能被问的 3 个尖锐问题。findings 里给"如何变成明显冠军"的可执行建议。` },
];

const reviews = await parallel(lenses.map(l => () =>
  agent(FACTS + '\n\n=== 你的任务 ===\n' + l.prompt, { label: l.label, phase: 'Review', schema: REVIEW_SCHEMA })
));

phase('Synthesize');
const SYNTH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['confirmed_fixes','data_strategy','demo_script','judge_qa','pitch'],
  properties: {
    confirmed_fixes: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['priority','title','why','how'],
      properties: { priority: { type: 'integer' }, title: { type: 'string' }, why: { type: 'string' }, how: { type: 'string' } } } },
    data_strategy: { type: 'string', description: '推荐的数据策略（用现快照/换快照/加导出），一段话说清取舍' },
    demo_script: { type: 'array', items: { type: 'string' }, description: '90秒现场演示逐步脚本' },
    judge_qa: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['q','a'], properties: { q: { type: 'string' }, a: { type: 'string' } } } },
    pitch: { type: 'string', description: '一句话作品定位' },
  },
};

const synth = await agent(
  FACTS + '\n\n=== 三份评审结论(JSON) ===\n' + JSON.stringify(reviews.filter(Boolean)) +
  '\n\n=== 你的任务 ===\n综合三份评审，去重并只保留**真问题**，产出：按优先级排序的可执行修复清单（priority 1 最高）；一段推荐数据策略；一份 90 秒现场演示脚本；3-5 条评委问答；一句话作品定位。务必贴合"只读不写生产、单人、简单好用"的约束与真实数据事实。',
  { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, effort: 'high' }
);

return { reviews: reviews.filter(Boolean), synthesis: synth };
