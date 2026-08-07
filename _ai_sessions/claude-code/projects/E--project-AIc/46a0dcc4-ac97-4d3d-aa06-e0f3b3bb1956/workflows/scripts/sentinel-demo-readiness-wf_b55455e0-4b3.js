export const meta = {
  name: 'sentinel-demo-readiness',
  description: '发货哨兵参赛就绪：引擎正确性审计 + 评委三视角批评 + 现场演示脚本',
  phases: [
    { title: '审计' },
    { title: '评委' },
    { title: '复核' },
    { title: '综合' },
  ],
}

const CONTEXT = `项目：发货哨兵 FulfillSentinel —— 公司「AI自动化场景创意比赛」参赛作品（2026-07-31 周五下午 四楼会议室 现场演示；限单人独立原创；评分口号「简单好用=高分」，偏「业务落地价值」；评委为技术/开发/产品岗）。
定位：只读聚合 赛狐ERP(订单主干) + Temu(库存) + 海外仓WMS(商品主数据) 的统一发货看板 + 履约异常预警。自包含单文件 HTML，断网可演示，全程无写操作。
真实脱敏数据快照：2026-07-16 14:31。505 单，赛狐已聚合 4 平台(Amazon176 / TikTok165 / Temu半托管154 / SHEIN10) × 10 店铺，全英国站。480 已发货、9 作废、16 待处理。当日发货率 99.6%(中位 6.4h / P90 13.4h / 超24h 仅 2 单)。
异常引擎命中：due_soon(临期<24h)=4；master_missing(主数据缺失, 已降级为提示级)=12；stuck_virtual(卡虚拟仓)=1；no_channel(缺渠道)=1；overdue=0、no_tracking=0、stockout=0、stuck_pending=0。需立即处理 actionable=4(权重>=40)。库存侧 2 个 Temu 断货货号(VIP2WCX / VIPR956, 均未被待发订单命中)。跨系统匹配键=内部货号(JMCAT*/VIP*)，已打通 7 个货号。
明星案例：包裹 P2AL6TCD63005 同时命中「卡虚拟仓 + 缺渠道」→ 未分配实仓且无物流渠道，将无法出库。
已知张力：快照是午间、运营健康 → 演示戏剧性偏弱；master_missing=12 是样例 WMS 主数据仅覆盖 160 货号导致的误报，已降级、不计入头条 KPI。
源码文件（可直接读取）：
  E:\\project\\AIc\\ship-sentinel\\backend\\build.py       —— ingest+统一模型+8类异常引擎+PII脱敏
  E:\\project\\AIc\\ship-sentinel\\backend\\xlsx_reader.py  —— 零依赖 xlsx 读取器
  E:\\project\\AIc\\ship-sentinel\\backend\\unified.json    —— 构建产物(脱敏)
  E:\\project\\AIc\\ship-sentinel\\frontend\\index.html     —— 看板(内联JS渲染逻辑)`;

const AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    overall_risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string', description: '短稳定标识, 如 ENG-01' },
          area: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          evidence: { type: 'string', description: '具体函数/行/逻辑证据' },
          suggested_fix: { type: 'string' },
        },
        required: ['id', 'area', 'severity', 'title', 'detail', 'evidence', 'suggested_fix'],
      },
    },
  },
  required: ['summary', 'overall_risk', 'findings'],
};

const JUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    persona: { type: 'string' },
    score_1_10: { type: 'number' },
    top_objections: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          objection: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          rebuttal_or_fix: { type: 'string' },
        },
        required: ['objection', 'severity', 'rebuttal_or_fix'],
      },
    },
    likely_questions: { type: 'array', items: { type: 'string' } },
    gaps: { type: 'array', items: { type: 'string' } },
    what_would_make_it_win: { type: 'string' },
  },
  required: ['persona', 'score_1_10', 'top_objections', 'likely_questions', 'gaps', 'what_would_make_it_win'],
};

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'partial', 'refuted'] },
    reasoning: { type: 'string' },
    real_demo_impact: { type: 'string' },
  },
  required: ['verdict', 'reasoning', 'real_demo_impact'],
};

const auditEnginePrompt =
`你是一名挑剔的资深工程师，在这件参赛作品上台前做正确性/健壮性审计。目标：找出会在技术评委面前翻车的引擎缺陷。
请实际读取并分析：
  E:\\project\\AIc\\ship-sentinel\\backend\\build.py
  E:\\project\\AIc\\ship-sentinel\\backend\\xlsx_reader.py
并抽查 E:\\project\\AIc\\ship-sentinel\\backend\\unified.json 里的真实订单记录以验证判断。
重点排查：
- 异常判定的假阳/假阴（overdue/due_soon/stockout/stuck_virtual/no_channel/stuck_pending/no_tracking/master_missing）；
- "剩余发货时间"文本解析 parse_remaining 的边界（跨天、"已超期"、空值、异常格式）；
- 用「最近下单时间」当作"现在(now)"的隐患（会不会误判临期/滞留/时效）；
- 跨系统货号匹配（SKU/MSKU/订单商品编码 ↔ 库存索引）的漏配/错配；
- 状态归类 classify 对边界状态（物流下单中/部分发货/退款中等）的处理；
- 时区、数值解析、多仓库存累加、PII 脱敏是否有遗漏列；
- 任何"看板显示 vs 真实业务含义"的偏差。
${CONTEXT}
每条发现给出 area/severity/title/detail/evidence(具体函数或逻辑)/suggested_fix。只报真问题，宁缺毋滥，但别放过会被评委当场戳穿的点。按 schema 返回。`;

const auditDataPrompt =
`你是一名数据分析师，审查这块看板的 KPI 与叙事是否内部自洽、经得起追问。
请实际读取 E:\\project\\AIc\\ship-sentinel\\backend\\build.py 与 E:\\project\\AIc\\ship-sentinel\\backend\\unified.json。
重点：
- KPI 定义是否诚实（actionable=4 的推导、当日发货率的口径、critical=0 的含义）；
- master_missing 降级处理是否恰当、会不会仍在某处误导；
- 有没有指标夸大或缩小、口径含糊、可能被评委指为"误导"的地方；
- "reference_now 用最近下单时间"对时效/临期统计的影响；
- 断货货号未被订单命中却单独报警，叙事上是否讲得通；
- 数据故事是否连贯（健康运营 + 精准揪出少数问题单）。
${CONTEXT}
按 AUDIT schema 返回（findings 里 area 用"数据/叙事"，suggested_fix 给可执行改法）。`;

const judgePrompt = (persona, lens) =>
`你是这场公司AI比赛的评委，视角=${persona}。这是一件 3–5 分钟现场演示的参赛作品。
${lens}
${CONTEXT}
请以你的视角严格但公允地评估，按 schema 返回：score_1_10、top_objections(每条含 severity 与"如何反驳或修补")、likely_questions(你现场最可能追问的问题)、gaps、what_would_make_it_win(要它拿一等奖还差什么)。`;

const verifyPrompt = (f) =>
`请以怀疑态度，针对真实源码核验下面这条"缺陷指控"是否成立。
必读：E:\\project\\AIc\\ship-sentinel\\backend\\build.py（必要时读 xlsx_reader.py / unified.json 佐证）。
缺陷指控：
  id: ${f.id}
  area: ${f.area}
  severity: ${f.severity}
  title: ${f.title}
  detail: ${f.detail}
  evidence: ${f.evidence}
  suggested_fix: ${f.suggested_fix}
请尽力"证伪"它：若代码里其实已处理、或前提不成立，判 refuted；若确实存在但影响被夸大，判 partial；确凿则 confirmed。
给出 reasoning 与 real_demo_impact(现场演示时它真会造成什么后果)。按 schema 返回。`;

// ---- 审计 + 评委 并行（后续 综合 需要全部结果） ----
phase('审计');
const [audEngine, audData, jTech, jBiz, jUx] = await parallel([
  () => agent(auditEnginePrompt, { label: '审计:引擎正确性', phase: '审计', schema: AUDIT_SCHEMA, agentType: 'general-purpose' }),
  () => agent(auditDataPrompt, { label: '审计:数据与叙事', phase: '审计', schema: AUDIT_SCHEMA, agentType: 'general-purpose' }),
  () => agent(judgePrompt('技术/开发评委', '你在意：正确性、健壮性、跨系统匹配是否真的对、离线单文件是否可信、有没有硬编码/造假、能否复用到别的系统。'), { label: '评委:技术', phase: '评委', schema: JUDGE_SCHEMA }),
  () => agent(judgePrompt('业务/运营评委', '你在意：是否真解决跨境自发货每天的痛（超时罚款、卡仓、漏发、断货）、ROI、值不值得推广、比现有人工核对省多少事。'), { label: '评委:业务', phase: '评委', schema: JUDGE_SCHEMA }),
  () => agent(judgePrompt('产品/易用性评委', '你在意"简单好用=高分"：一眼看懂吗、演示流畅吗、操作直觉吗、视觉是否专业、有没有多余复杂度。'), { label: '评委:易用', phase: '评委', schema: JUDGE_SCHEMA }),
]);

const audits = [audEngine, audData].filter(Boolean);
const allFindings = audits.flatMap((a, i) => (a.findings || []).map(f => ({ ...f, src: i === 0 ? 'engine' : 'data' })));
log(`审计得到 ${allFindings.length} 条待核验发现；开始对抗式复核。`);

// ---- 复核：逐条对真实代码证伪 ----
phase('复核');
const toVerify = allFindings.slice(0, 16);
const verdicts = await parallel(toVerify.map(f => () =>
  agent(verifyPrompt(f), { label: '复核:' + f.id, phase: '复核', schema: VERDICT_SCHEMA, agentType: 'general-purpose' })
    .then(v => ({ finding: f, verdict: v }))
    .catch(() => null)
));
const confirmed = verdicts.filter(Boolean)
  .filter(x => x.verdict && x.verdict.verdict !== 'refuted')
  .map(x => ({ ...x.finding, verify: x.verdict }));
log(`复核完成：${confirmed.length}/${toVerify.length} 条成立(含 partial)。`);

const judges = [jTech, jBiz, jUx].filter(Boolean);

// ---- 综合：赛前行动清单 + 现场演示脚本 + 评委问答预案 ----
phase('综合');
const synthPrompt =
`你是这件参赛作品的操盘手。基于以下"已核验的工程缺陷"和"三位评委的批评"，产出一份可直接执行的中文交付物（Markdown）。
${CONTEXT}

【已核验成立的工程缺陷（按需修）】
${JSON.stringify(confirmed, null, 2)}

【评委批评（技术/业务/易用）】
${JSON.stringify(judges, null, 2)}

请输出三部分，务实、具体、可落地：
## 一、赛前必修行动清单
按「必修 / 建议 / 可选」三档，每条：做什么、为什么(对应哪条缺陷或评委意见)、预计改动位置(文件/函数)。把会被评委当场戳穿的排在最前。

## 二、现场演示脚本（3–5 分钟，逐步、可照着念）
- 用"确定性叙事"化解"数据太平静"：在 505 单 × 4 平台的洪流里，哨兵先给你"确定性"(501 单没问题)，再精准揪出真正要你动手的少数单——含 1 个「卡虚拟仓+缺渠道、会悄悄发不出去」的明星案例。
- 给出开场钩子、每一步点哪里/说什么/预期屏幕反应、时间分配、以及那个"wow 时刻"如何铺垫与引爆。
- 结尾落到"业务落地价值 + 只读零风险 + 断网可用 + 可复制到别的系统"。

## 三、评委问答预案（Q&A）
把三位评委最可能追问的问题各列成 Q→A，答案要短、自信、有依据（尤其：数据是不是真的/造的？只读怎么证明？为什么不直接连系统？master_missing 为何 12？这么平静有什么可看的？能不能推广？）。

只输出这份 Markdown，不要额外解释。`;

const synth = await agent(synthPrompt, { label: '综合:行动清单+演示脚本+问答', phase: '综合' });

return {
  findings_total: allFindings.length,
  confirmed_count: confirmed.length,
  confirmed,
  judges,
  audit_summaries: audits.map(a => ({ summary: a.summary, overall_risk: a.overall_risk, n: (a.findings || []).length })),
  synth,
};
