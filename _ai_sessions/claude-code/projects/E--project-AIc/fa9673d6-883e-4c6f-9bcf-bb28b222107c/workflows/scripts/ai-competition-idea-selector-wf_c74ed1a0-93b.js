export const meta = {
  name: 'ai-competition-idea-selector',
  description: 'Brainstorm, score, and recommend a winning entry for the company AI automation competition (tech/dev/product entrant)',
  phases: [
    { title: 'Ideate', detail: '6 idea-generators, distinct lenses' },
    { title: 'Consolidate', detail: 'dedupe + shortlist to ~10 distinct ideas' },
    { title: 'Judge', detail: '3-judge panel scores every shortlisted idea' },
    { title: 'Synthesize', detail: 'rank + detailed build/demo plan for the winner' },
  ],
}

const CONTEXT = `
【比赛背景】公司内部"AI自动化场景创意比赛"
- 主题：AI职场提效工具实战与干货分享（AI实用工具、智能文案、职场数据处理、办公效率优化、工作场景智能赋能等）
- 形式：限单人参赛、独立完成、现场演示/实操作品、分享AI工具
- 评分导向（原文）：作品原创、脑洞不限、"简单好用就是高分"
- 奖金：一等1000 / 二等500 / 三等200 / 参与奖50
- 评委与观众：公司同事（跨部门，含行政/HR、运营/市场、技术、财务/数据、销售/客服）+ 领导。多数评委不是技术人员。
【参赛者画像】技术/开发/产品岗，会写代码。
【现场演示环境】四楼会议室，有稳定网络；电脑装了Python和Node.js；有可用的大模型API Key（Claude/OpenAI/通义/文心/DeepSeek任一）。可联网、可调API。
【时间】今天约剩2周准备时间；比赛当天现场演示，单次演示时间有限（建议3-8分钟内跑完并出效果）。
【夺冠公式】评委自己每周都会遇到的痛点 + 现场60秒内跑出肉眼可见的"哇"效果 + 界面/交互干净 + 明显原创（不是ChatGPT网页套壳）+ 单人两周内能稳定做完、现场不翻车。
`

const IDEA_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ideas'],
  properties: {
    ideas: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name','tagline','problem','how_it_works','demo_script','tech_stack','wow_moment','originality','simplicity','risks','effort_days'],
        properties: {
          name: { type: 'string', description: '作品中文名（响亮、好记）' },
          tagline: { type: 'string', description: '一句话卖点' },
          problem: { type: 'string', description: '解决谁的什么真实痛点' },
          how_it_works: { type: 'string', description: '核心工作原理/流程' },
          demo_script: { type: 'string', description: '现场演示逐步流程，能在几分钟内出效果' },
          tech_stack: { type: 'string', description: '技术栈与依赖（Python/Node/API/前端等）' },
          wow_moment: { type: 'string', description: '最出彩、让全场惊叹的那一下' },
          originality: { type: 'string', description: '为什么原创、和市面套壳工具的差异' },
          simplicity: { type: 'string', description: '为什么简单好用（评委视角）' },
          risks: { type: 'string', description: '现场翻车风险与规避' },
          effort_days: { type: 'number', description: '单人预估工作量（天）' },
        },
      },
    },
  },
}

const JUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scores'],
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['idea_name','simplicity','demo_wow','usefulness','originality','judge_resonance','feasibility','weighted_total','verdict'],
        properties: {
          idea_name: { type: 'string' },
          simplicity: { type: 'number', description: '简单好用 1-10（权重25%）' },
          demo_wow: { type: 'number', description: '现场演示效果 1-10（权重20%）' },
          usefulness: { type: 'number', description: '实用性/落地价值 1-10（权重20%）' },
          originality: { type: 'number', description: '原创性/脑洞 1-10（权重15%）' },
          judge_resonance: { type: 'number', description: '评委共鸣：非技术评委也懂也想要 1-10（权重10%）' },
          feasibility: { type: 'number', description: '单人两周可实现且现场不翻车 1-10（权重10%）' },
          weighted_total: { type: 'number', description: '按上述权重计算的加权总分（0-10，保留一位小数）' },
          verdict: { type: 'string', description: '一句话点评（优点+最大风险）' },
        },
      },
    },
  },
}

const FINAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ranking','winner','runner_ups','strategy_notes'],
  properties: {
    ranking: {
      type: 'array',
      description: '前5名排名（含加权均分）',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rank','name','avg_score','one_line'],
        properties: {
          rank: { type: 'number' },
          name: { type: 'string' },
          avg_score: { type: 'number' },
          one_line: { type: 'string', description: '一句话：它是什么 + 为什么排这个名次' },
        },
      },
    },
    winner: {
      type: 'object',
      additionalProperties: false,
      required: ['name','tagline','why_wins','what_it_does','demo_script_steps','tech_stack','build_plan','wow_moments','risk_mitigation','bonus_points'],
      properties: {
        name: { type: 'string' },
        tagline: { type: 'string' },
        why_wins: { type: 'string', description: '为什么这个最有夺冠潜力（对照评分维度）' },
        what_it_does: { type: 'string', description: '完整功能说明' },
        demo_script_steps: { type: 'array', items: { type: 'string' }, description: '现场演示逐步台词/操作（可直接照做）' },
        tech_stack: { type: 'string' },
        build_plan: { type: 'array', items: { type: 'string' }, description: '两周分阶段里程碑（可执行）' },
        wow_moments: { type: 'array', items: { type: 'string' } },
        risk_mitigation: { type: 'array', items: { type: 'string' }, description: '现场翻车风险与兜底方案（如离线缓存演示）' },
        bonus_points: { type: 'array', items: { type: 'string' }, description: '锦上添花的加分项' },
      },
    },
    runner_ups: {
      type: 'array',
      description: '2个备选方案（含可嫁接到冠军方案的亮点）',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name','why_consider','graft_idea'],
        properties: {
          name: { type: 'string' },
          why_consider: { type: 'string' },
          graft_idea: { type: 'string', description: '这个方案里可以借鉴/嫁接到冠军方案的点子' },
        },
      },
    },
    strategy_notes: { type: 'array', items: { type: 'string' }, description: '通用夺冠策略提示（演示、话术、加分技巧）' },
  },
}

const LENSES = [
  { key: '开发者提效', prompt: '你是资深开发者。从开发者每周真实痛点出发（代码评审/PR、commit→周报日报、写文档/注释、写测试、排查日志报错、接口调试、SQL/数据处理、脚手架生成等），设计AI自动化提效工具。' },
  { key: '产品经理提效', prompt: '你是资深产品经理。从产品/需求侧真实痛点出发（写PRD、需求评审、竞品调研、用户反馈聚类分析、原型/流程图生成、会议决策记录、跨团队沟通对齐等），设计AI自动化工具。' },
  { key: '现场哇效果', prompt: '你的唯一目标是现场演示的视觉冲击与惊叹感。优先能实时、可视化、多模态、浏览器自动化（可用Playwright驱动真实网页）、看得见"AI在自己动"的方案，让全场同事忍不住拍照录像。' },
  { key: '跨部门通用刚需', prompt: '你要设计人人都能用、非技术评委也秒懂的通用刚需工具（会议纪要/录音转纪要、企业文档知识库问答、Excel/表格智能分析、批量文件处理、邮件/消息智能起草、网页信息采集整理等），最大化评委共鸣。' },
  { key: '原创脑洞差异化', prompt: '你要刻意避开烂大街的"ChatGPT套壳/直接问答"，寻找独特组合、意想不到的场景、有记忆点的差异化角度（如把两个不相关流程自动串起来、把枯燥工作变游戏化、AI Agent自主完成多步任务等），脑洞越大越好但仍要能落地。' },
  { key: '落地稳健低风险', prompt: '你是务实的工程师。在"简单好用+现场绝不翻车"约束下设计方案：代码量小、依赖少、可离线兜底/可缓存演示数据、单人两周内能高质量完成。宁可朴素也要稳、要好用。' },
]

// ---- Phase 1: Ideate (barrier — need all ideas before consolidating) ----
phase('Ideate')
const rawBatches = await parallel(LENSES.map(l => () =>
  agent(
    `${CONTEXT}\n\n【你的视角：${l.key}】${l.prompt}\n\n请产出3-4个高质量、彼此不同的参赛点子。每个点子都要能现场演示、单人两周内可完成、贴合"简单好用=高分"的评分导向。避免空泛，要具体到能照着做。`,
    { label: `ideate:${l.key}`, phase: 'Ideate', schema: IDEA_SCHEMA }
  ).then(r => (r?.ideas || []).map(i => ({ ...i, lens: l.key })))
))
const allIdeas = rawBatches.filter(Boolean).flat()
log(`共产出 ${allIdeas.length} 个原始点子，去重收敛中…`)

// ---- Phase 2: Consolidate (barrier — need全集才能去重/挑选) ----
phase('Consolidate')
const CONSOLIDATE_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['shortlist'],
  properties: { shortlist: IDEA_SCHEMA.properties.ideas },
}
const consolidated = await agent(
  `${CONTEXT}\n\n下面是各视角产出的全部候选点子（JSON）。请你作为总策划：\n1) 合并高度重复/相似的点子，保留更强的表述；\n2) 剔除明显套壳、现场没效果、或两周单人做不完的；\n3) 挑出最有夺冠潜力的8-10个，覆盖不同类型（保证多样性，不要都是同一类）；\n4) 对保留的每个点子，补全并优化各字段，使其更具体、更可演示、更"简单好用"。\n\n候选点子：\n${JSON.stringify(allIdeas)}`,
  { label: 'consolidate', phase: 'Consolidate', schema: CONSOLIDATE_SCHEMA, effort: 'high' }
)
const shortlist = consolidated?.shortlist || []
log(`收敛为 ${shortlist.length} 个入围方案，进入评委打分…`)

// ---- Phase 3: Judge panel (barrier — 综合三位评委分数才能排名) ----
phase('Judge')
const JUDGES = [
  { key: '技术评委', prompt: '你是技术背景评委，看重实现巧思、原创性、技术含量与稳定性，但也警惕过度炫技导致现场不稳。' },
  { key: '业务评委', prompt: '你是业务/运营背景评委（非技术），只关心"我明天能不能用上、好不好用、有没有解决我的痛"，看不懂复杂技术。' },
  { key: '老板ROI评委', prompt: '你是领导/老板视角评委，关心投入产出、能否推广到全公司、演示是否有说服力和记忆点、是否值得发奖金。' },
]
const rubric = '评分权重：简单好用25% / 现场演示效果20% / 实用性20% / 原创性15% / 评委共鸣10% / 可实现性10%。weighted_total请按此权重严格计算（0-10，保留一位小数）。'
const panel = await parallel(JUDGES.map(j => () =>
  agent(
    `${CONTEXT}\n\n【你的评委身份：${j.key}】${j.prompt}\n\n${rubric}\n\n请对下面每一个入围方案打分（每个维度1-10）并给出加权总分与一句话点评。对所有方案打分，严格、有区分度，不要给大家都打高分。\n\n入围方案：\n${JSON.stringify(shortlist)}`,
    { label: `judge:${j.key}`, phase: 'Judge', schema: JUDGE_SCHEMA, effort: 'high' }
  ).then(r => ({ judge: j.key, scores: r?.scores || [] }))
))
const validPanel = panel.filter(Boolean)

// ---- Phase 4: Synthesize (barrier — 需全部分数才能排名+出方案) ----
phase('Synthesize')
const finalPlan = await agent(
  `${CONTEXT}\n\n下面是8-10个入围方案(shortlist)和三位评委各自的打分(panel)。请你综合：\n1) 汇总三位评委的加权总分求平均，产出前5名排名；\n2) 选出综合最有夺冠潜力的1个作为winner，给出完整落地方案：功能说明、现场演示逐步台词/操作、技术栈、两周分阶段build_plan、wow时刻、现场翻车风险与兜底、加分项；\n3) 选2个runner_up备选，并指出它们身上可嫁接到winner的亮点；\n4) 给出通用夺冠策略提示（演示节奏、话术、加分技巧）。\n务必让winner方案"简单好用、现场几分钟出效果、明显原创、单人两周稳做完"。\n\nshortlist：\n${JSON.stringify(shortlist)}\n\npanel：\n${JSON.stringify(validPanel)}`,
  { label: 'synthesize', phase: 'Synthesize', schema: FINAL_SCHEMA, effort: 'high' }
)

return { shortlist_count: shortlist.length, final: finalPlan }
