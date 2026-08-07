<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, getToken, setToken } from './api'

/** 总览：平铺 */
const OVERVIEW_NAV = [
  { id: 'boss', label: '老板驾驶舱', icon: '◉', desc: '跨部门经营与风险摘要' },
  { id: 'dashboard', label: '工作台', icon: '⌂', desc: '个人快捷入口与最近异常' },
]

/** 业务域：可展开 */
const DOMAIN_NAV = [
  {
    id: 'purchase',
    label: '采购',
    icon: '采',
    children: [
      { id: 'purchase-dashboard', label: '仪表盘', desc: '销售天数、滞销断货与采购概览' },
      { id: 'purchase-sync', label: '采购数据同步', desc: '采购相关数据同步与使用改进' },
    ],
  },
  {
    id: 'amazon',
    label: 'Amazon',
    icon: 'A',
    children: [
      { id: 'amz-overview', label: '总览', desc: 'Amazon 仪表盘 · 店铺与异常摘要（张帅）' },
      { id: 'amz-replenish', label: '补货', desc: '助理发起 → 终审李瑾' },
      { id: 'amz-anomaly', label: '环比异常任务', desc: '链接日/周/月环比 · 人维任务闭环' },
      { id: 'amz-shipping', label: '自动化发货', desc: 'FBA/FBM · 赛狐 + 海外仓履约' },
      { id: 'amz-patrol', label: '巡店', desc: '插件 → 飞书 → 任务' },
    ],
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    icon: 'T',
    children: [
      { id: 'tk-overview', label: '平台总览', desc: 'TikTok 店铺与异常摘要' },
      { id: 'tk-ads', label: '广告投流', desc: '广告采集、花费与 ROI' },
      { id: 'tk-content', label: '内容分析', desc: '视频归因 GMV / 商品卡 CTR·CVR · 窗口快照' },
      { id: 'tk-affiliate', label: '达人表现', desc: '联盟达人归因 GMV / 是否出单 / 预计佣金 · 窗口快照' },
      { id: 'tk-report', label: '日报 / AI 简报', desc: '投流日报与智能简报' },
      { id: 'tk-tasks', label: '异常任务', desc: 'TK 业务异常：库存/广告/健康/视频/达人 · 读写 tk.fact_tk_anomaly_task' },
    ],
  },
  {
    id: 'temu',
    label: 'Temu',
    icon: 'M',
    children: [
      { id: 'temu-overview', label: '平台总览', desc: 'Temu 店铺与异常摘要' },
      { id: 'temu-health', label: '店铺健康监测', desc: '在售、流量、下架点名' },
      { id: 'temu-shipping', label: '自动化发货', desc: '赛狐 ERP + 海外仓发货' },
      { id: 'temu-plugin', label: '监测插件', desc: '插件与 Playwright 守护' },
      { id: 'temu-tasks', label: '异常任务', desc: '本平台异常（跳转统一任务引擎）' },
    ],
  },
  {
    id: 'finance',
    label: '财务',
    icon: '财',
    children: [
      { id: 'finance', label: '经营报表', desc: '利润 / 现金流 / 边际 / 打款 / 报税' },
    ],
  },
  {
    id: 'design',
    label: '美工',
    icon: '设',
    children: [
      { id: 'design-tasks', label: '任务表', desc: '设计需求任务与进度' },
      { id: 'design-dashboard', label: '仪表盘', desc: '美工产能与 SLA 概览' },
      { id: 'design-push', label: '跨部门推送', desc: '汇总推送 · 完成后回推需求部门' },
    ],
  },
]

/** 系统：底部折叠 */
const SYSTEM_NAV = [
  { id: 'tasks', label: '异常任务中心', icon: '⚠', desc: '跨平台异常跟踪与闭环' },
  { id: 'shops', label: '店铺主数据', icon: '🏪', desc: '多平台店铺主数据' },
  { id: 'plugins', label: '插件中心', icon: '🔌', desc: '采集插件与节点总览' },
  { id: 'ai-reports', label: 'AI报表', icon: '✦', desc: '跨平台智能分析与经营简报' },
  { id: 'sync', label: '飞书同步', icon: '↻', desc: '任务等表增量同步到飞书多维表' },
]

const FINANCE_TABS = [
  {
    id: 'profit',
    label: '平台利润表',
    desc: '分平台利润视图；赛狐数据 + 补差逻辑，后续可 AI 辅助。',
    sources: ['赛狐订单/费用', '补差规则', 'AI 辅助（规划）'],
  },
  {
    id: 'cashflow',
    label: '公司现金流表',
    desc: '现金水位：飞书出纳银行余额、采购货值、采购未付。',
    sources: ['飞书 · 出纳银行余额', '采购货值', '采购未付'],
  },
  {
    id: 'margin',
    label: '边际利润表',
    desc: '当月平台利润 − 出纳当月实际支出 → 每月净利润。',
    sources: ['平台利润', '出纳 · 当月实际支出'],
  },
  {
    id: 'payout',
    label: '打款分布',
    desc: '付款流水分布，支撑资金链测算。',
    sources: ['打款流水', '资金链测算模型'],
  },
  {
    id: 'tax',
    label: '报税',
    desc: '数据处理后生成报税报表（经营辅助，非全量总账）。',
    sources: ['结构化经营数据', '报税报表模板'],
  },
]

const plugins = [
  {
    id: 'amazon-extension',
    name: 'Amazon 前台巡检',
    platform: 'Amazon',
    platformKey: 'amazon',
    kind: 'Chrome MV3',
    path: 'collectors/amazon-extension',
    status: '规划中',
    statusClass: 'planned',
    desc: '账号健康 / 销售异常前台 12 项巡检，登录态复用，结果上报 Ingest。',
  },
  {
    id: 'temu-extension',
    name: 'Temu 监测插件',
    platform: 'Temu',
    platformKey: 'temu',
    kind: 'Chrome MV3',
    path: 'collectors/temu-extension',
    status: '改造中',
    statusClass: 'building',
    desc: '在售数量、流量待关注、下架点名；多店轮巡，异常写任务中心。',
  },
  {
    id: 'temu-monitor',
    name: 'Temu Playwright 守护',
    platform: 'Temu',
    platformKey: 'temu',
    kind: 'Node + Playwright',
    path: 'collectors/temu-monitor',
    status: '改造中',
    statusClass: 'building',
    desc: '无插件本机常驻；对齐插件能力，适合固定采集机。',
  },
  {
    id: 'tiktok-ads',
    name: 'TikTok 广告采集',
    platform: 'TikTok',
    platformKey: 'tiktok',
    kind: '紫鸟 + 插件',
    path: 'collectors/tiktok-ads',
    status: '待接入',
    statusClass: 'pending',
    desc: '广告花费 / 销量 / ROI / 收入；dual 模式先写中心库再同步飞书。',
  },
  {
    id: 'agent-core',
    name: 'Collector Agent SDK',
    platform: '通用',
    platformKey: 'common',
    kind: 'Python SDK',
    path: 'collectors/agent-core',
    status: '可用',
    statusClass: 'ready',
    desc: '鉴权、心跳、幂等上报、重试；各插件统一对接中心 Ingest API。',
  },
  {
    id: 'sellfox-worker',
    name: '赛狐 Worker',
    platform: 'Sellfox',
    platformKey: 'temu',
    kind: 'API Worker',
    path: 'collectors/sellfox-worker',
    status: '规划中',
    statusClass: 'planned',
    desc: '固定出口 IP 拉取商品/订单；供发货与异常补全。',
  },
]

const shippingPipelineTemu = [
  { step: '1', title: '订单拉取', desc: '赛狐 OpenAPI / Temu 订单同步' },
  { step: '2', title: '规则匹配', desc: '店铺、仓别、SKU、时效策略' },
  { step: '3', title: 'WMS 下发', desc: '英国海外仓出库指令' },
  { step: '4', title: '轨迹回写', desc: '运单号、状态回中心与飞书' },
]

const shippingPipelineAmazon = [
  { step: '1', title: '订单拉取', desc: '赛狐 / Amazon 订单（FBM 优先）' },
  { step: '2', title: '履约分流', desc: 'FBA 走亚马逊仓 · FBM 走海外仓规则' },
  { step: '3', title: 'WMS / 物流下单', desc: 'FBM：金猫/黑猫 WMS 出库；FBA 库存同步' },
  { step: '4', title: '回传闭环', desc: '运单号回赛狐/平台 · 异常进任务中心' },
]

const shippingShopsTemu = [
  { name: 'Agnis', platform: 'Temu', warehouse: 'UK WMS', mode: '海外仓直发' },
  { name: 'HomeCove', platform: 'Temu', warehouse: 'UK WMS', mode: '海外仓直发' },
  { name: 'Twilight Cove', platform: 'Temu', warehouse: 'UK WMS', mode: '海外仓直发' },
]

const shippingShopsAmazon = [
  { name: 'Amazon Demo UK', platform: 'Amazon', warehouse: 'FBA + UK WMS(FBM)', mode: 'FBA / FBM 双轨' },
  { name: '（待配置正式店）', platform: 'Amazon', warehouse: '待绑定赛狐店号', mode: '规划中' },
]

const aiReportTemplates = [
  {
    id: 'daily-ops',
    name: '运营异常日报',
    scope: '全平台',
    desc: '汇总待处理/进行中异常、高优先级 ASIN/商品、建议动作。',
  },
  {
    id: 'tk-ads',
    name: 'TK 广告投流简报',
    scope: 'TikTok',
    desc: '花费、ROI、零产出系列、分店 KPI 与亮点/风险。',
  },
  {
    id: 'temu-health',
    name: 'Temu 店铺健康周报',
    scope: 'Temu',
    desc: '下架、限流、在售波动趋势与需关注商品清单。',
  },
  {
    id: 'ship-sla',
    name: '发货时效分析',
    scope: '海外仓',
    desc: '出库时效、异常包裹、仓配瓶颈与建议。',
  },
]

const PLATFORM_META = {
  amazon: {
    key: 'amazon',
    label: 'Amazon',
    focus: '环比异常任务、补货审批、自动化发货（FBA/FBM）、巡店 12 项',
    schedule: '销售异常 每日 07:00 · 账号异常 05:30 起每 8h',
    owner: '仪表盘 · 张帅',
  },
  tiktok: {
    key: 'tiktok',
    label: 'TikTok',
    focus: '广告投流数据、ROI、多店日报',
    schedule: '广告采集约 17:20 · 业务日=昨日',
    owner: '对接 · 宋敏',
  },
  temu: {
    key: 'temu',
    label: 'Temu',
    focus: '在售/流量/下架监测、海外仓发货',
    schedule: '监测 15min 轮询 · 09:30/16:30 必提醒',
    owner: '对接 · 刘芝',
  },
}

const EXPAND_KEY = 'qq_nav_expand_v2'
const SYSTEM_KEY = 'qq_nav_system_v2'

function loadExpandState() {
  try {
    const raw = localStorage.getItem(EXPAND_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return { purchase: false, amazon: true, tiktok: false, temu: false, finance: false, design: false }
}

const token = ref(getToken())
const me = ref(null)
const loading = ref(false)
const error = ref('')
const health = ref(null)
const activeTab = ref('boss')
const expandedDomains = ref(loadExpandState())
const systemOpen = ref(localStorage.getItem(SYSTEM_KEY) === '1')
const financeTab = ref('profit')

const loginForm = reactive({ username: 'admin', password: 'admin123' })
const filters = reactive({ status: '', platform: '', page: 1, page_size: 20 })
const tasks = ref([])
const total = ref(0)
const shops = ref([])
const syncMsg = ref('')
const aiMsg = ref('')
const aiForm = reactive({
  template: 'daily-ops',
  range: 'yesterday',
  note: '',
})

/** TK 异常任务（tk.fact_tk_anomaly_task） */
const tkFilters = reactive({
  status: '',
  priority: '',
  anomaly_code: '',
  object_type: '',
  shop_external_id: '',
  q: '',
  open_only: false,
  page: 1,
  page_size: 20,
})
const tkTasks = ref([])
const tkTotal = ref(0)
const tkSummary = ref({ open: 0, in_progress: 0, resolved: 0, cancelled: 0, ignored: 0 })
const tkTypes = ref([])
const tkAdsEvalMsg = ref('')
const tkAdsEvalLoading = ref(false)
const tkProductEvalMsg = ref('')
const tkProductEvalLoading = ref(false)
const tkContentEvalMsg = ref('')
const tkContentEvalLoading = ref(false)
const tkAffiliateEvalMsg = ref('')
const tkAffiliateEvalLoading = ref(false)

/** TK 广告投流列表 */
const tkAdsFilters = reactive({
  biz_date: '',
  shop_external_id: '',
  q: '',
  page: 1,
  page_size: 50,
})
const tkAdsItems = ref([])
const tkAdsTotal = ref(0)
const tkAdsSummary = ref({ spend: 0, orders: 0, revenue: 0, roi: null, open_anomaly_rows: 0 })
const tkAdsBizDate = ref('')
const tkAdsAvailableDates = ref([])
const tkAdsLoading = ref(false)

/** TK 内容分析（视频 content_daily + 商品卡 traffic） */
const tkContentPane = ref('video') // video | traffic
const tkContentFilters = reactive({
  biz_date: '',
  shop_external_id: '',
  channel: 'short_video',
  order_by: 'attributed_gmv',
  page: 1,
  page_size: 50,
})
const tkContentItems = ref([])
const tkContentTotal = ref(0)
const tkContentBizDate = ref('')
const tkContentAvailableDates = ref([])
const tkContentLoading = ref(false)
const tkContentSummary = ref({
  row_count: 0,
  content_count: 0,
  shop_count: 0,
  attributed_gmv_sum: 0,
  play_count_sum: 0,
  impressions_sum: 0,
  attributed_sku_orders_sum: 0,
  metric: 'window_snapshot',
  note: '',
})
const tkTrafficFilters = reactive({
  biz_date: '',
  shop_external_id: '',
  channel: '', // 空=全部渠道，便于 ≥2 渠道对比
  order_by: 'gmv',
  page: 1,
  page_size: 50,
})
const tkTrafficItems = ref([])
const tkTrafficTotal = ref(0)
const tkTrafficBizDate = ref('')
const tkTrafficAvailableDates = ref([])
const tkTrafficLoading = ref(false)
const tkTrafficSummary = ref({
  row_count: 0,
  product_count: 0,
  shop_count: 0,
  gmv_sum: 0,
  impressions_sum: 0,
  orders_sum: 0,
  metric: 'window_snapshot',
  note: '',
})
/** 商品卡多渠道对比：同一 product_id 下按 channel 透视（当前页数据） */
const tkTrafficChannelCompare = computed(() => {
  const map = new Map()
  for (const r of tkTrafficItems.value || []) {
    const pid = r.product_id || '—'
    if (!map.has(pid)) {
      map.set(pid, {
        product_id: pid,
        product_name: r.product_name || pid,
        shop_name: r.shop_name || r.shop_external_id || '—',
        currency: r.currency || '',
        channels: {},
      })
    }
    const row = map.get(pid)
    const ch = r.channel || 'other'
    row.channels[ch] = {
      impressions: r.impressions,
      clicks: r.clicks,
      ctr: r.ctr,
      cvr: r.cvr,
      orders_cnt: r.orders_cnt,
      gmv: r.gmv,
    }
  }
  return Array.from(map.values()).slice(0, 30)
})
const tkTrafficChannelKeys = computed(() => {
  const s = new Set()
  for (const r of tkTrafficItems.value || []) {
    if (r.channel) s.add(r.channel)
  }
  return Array.from(s).sort()
})

/** TK 达人表现（P3.2 · affiliate creator + shop window） */
const tkAffiliatePane = ref('creator') // creator | shop
const tkAffiliateFilters = reactive({
  biz_date: '',
  shop_external_id: '',
  sold_only: false,
  order_by: 'gmv',
  page: 1,
  page_size: 50,
})
const tkAffiliateItems = ref([])
const tkAffiliateTotal = ref(0)
const tkAffiliateBizDate = ref('')
const tkAffiliateAvailableDates = ref([])
const tkAffiliateLoading = ref(false)
const tkAffiliateSummary = ref({
  row_count: 0,
  creator_count: 0,
  sold_creator_count: 0,
  shop_count: 0,
  gmv_sum: 0,
  order_units_sum: 0,
  est_commission_sum: 0,
  orders_cnt_sum: 0,
  metric: 'window_snapshot',
  note: '',
})
const tkAffiliateShopFilters = reactive({
  biz_date: '',
  shop_external_id: '',
  page: 1,
  page_size: 50,
})
const tkAffiliateShopItems = ref([])
const tkAffiliateShopTotal = ref(0)
const tkAffiliateShopBizDate = ref('')
const tkAffiliateShopAvailableDates = ref([])
const tkAffiliateShopLoading = ref(false)
const tkAffiliateShopSummary = ref({
  row_count: 0,
  shop_count: 0,
  gmv_affiliate_sum: 0,
  order_units_sum: 0,
  est_commission_sum: 0,
  creators_sold_sum: 0,
  creators_published_sum: 0,
  metric: 'window_snapshot',
  note: '',
})

/** TK 店日经营总览（shop_daily / ads rollup） */
const tkShopDailyBizDate = ref('')
const tkShopDailyLoading = ref(false)
const tkShopDailyItems = ref([])
const tkShopDailySummary = ref({
  gmv: 0,
  orders_cnt: 0,
  buyers_cnt: 0,
  refund_amount: 0,
  ad_spend: 0,
  ad_revenue: 0,
  ad_orders: 0,
  ad_roi: null,
  aov: null,
  shop_count: 0,
  real_shop_rows: 0,
  ads_fallback_rows: 0,
  open_anomaly_count: 0,
  boss_decision_count: 0,
  data_source: 'empty',
})
const tkShopDailyNote = ref('')
const tkFreshness = ref({
  as_of: '',
  shop_daily_max: null,
  ads_max: null,
  content_max: null,
  traffic_max: null,
  affiliate_max: null,
  shop_daily_age_days: null,
  ads_age_days: null,
  content_age_days: null,
  traffic_age_days: null,
  affiliate_age_days: null,
  open_anomaly_count: 0,
  boss_decision_count: 0,
  stale: [],
  ok: true,
})
const tkFreshnessBanner = computed(() => {
  const f = tkFreshness.value || {}
  const stale = Array.isArray(f.stale) ? f.stale : []
  if (!stale.length) return ''
  const label = {
    shop_daily: `店日偏旧(${f.shop_daily_max || '无'} · ${f.shop_daily_age_days ?? '?'}天前)`,
    shop_daily_empty: '店日无数据',
    ads: `广告偏旧(${f.ads_max || '无'} · ${f.ads_age_days ?? '?'}天前，同事机日更)`,
    ads_empty: '广告无数据',
    content: `内容窗偏旧(${f.content_max || '无'})`,
    content_empty: '内容无数据',
    traffic: `商品卡窗偏旧(${f.traffic_max || '无'})`,
    traffic_empty: '商品卡无数据',
    affiliate: `达人窗偏旧(${f.affiliate_max || '无'})`,
  }
  return stale.map((k) => label[k] || k).join(' · ')
})

/** TK 商品销量排行（快照 sales_qty） */
const tkProductRankLoading = ref(false)
const tkProductRankItems = ref([])
const tkProductRankSummary = ref({
  product_count: 0,
  sales_qty_sum: 0,
  shop_count: 0,
  metric: 'sales_qty',
  note: '',
})
const tkProductRankLimit = ref(10)

const drawer = reactive({
  open: false,
  task: null,
  note: '',
  mode: 'progress',
  /** center = public.task；tk = tk.fact_tk_anomaly_task */
  source: 'center',
  action_code: '',
  effect_code: '',
  resolveStatus: 'resolved',
  guidance: null,
  guidanceLoading: false,
})

const tkCreateForm = reactive({
  anomaly_code: 'product_stock_low',
  summary: '',
  shop_external_id: '',
  product_id: '',
  product_name: '',
  product_name_cn: '',
  seller_sku: '',
  object_ref: '',
  priority: 'P1',
  metric_snapshot: '',
  progress_note: '',
  owner_name: '',
})

const SKELETON_TYPES = {
  'amazon|link_wow_units_drop': true,
  'tiktok|low_roi': true,
  'temu|listing_off': true,
}

const ACTION_OPTIONS = [
  { code: 'amz_adjust_ads', label: 'amz_adjust_ads · 调整广告' },
  { code: 'amz_check_stock', label: 'amz_check_stock · 查库存' },
  { code: 'tk_pause_low_roi', label: 'tk_pause_low_roi · 暂停低ROI' },
  { code: 'tk_revise_creative', label: 'tk_revise_creative · 换素材' },
  { code: 'temu_relist', label: 'temu_relist · 重新上架' },
  { code: 'temu_fix_listing', label: 'temu_fix_listing · 核对信息' },
  { code: 'generic_observe', label: 'generic_observe · 观察等待' },
]

const EFFECT_OPTIONS = [
  { code: 'recovered', label: 'recovered · 已恢复' },
  { code: 'partial', label: 'partial · 部分改善' },
  { code: 'no_effect', label: 'no_effect · 无效' },
  { code: 'false_positive', label: 'false_positive · 误报' },
  { code: 'escalated', label: 'escalated · 已升级' },
]

function isSkeletonTask(task) {
  if (!task) return false
  return !!SKELETON_TYPES[`${task.platform}|${task.anomaly_type}`]
}

const createForm = reactive({
  platform: 'tiktok',
  anomaly_type: 'low_roi',
  biz_id: '',
  title: '',
  progress_note: '',
})

const flatNav = computed(() => {
  const list = [...OVERVIEW_NAV, ...SYSTEM_NAV]
  for (const d of DOMAIN_NAV) {
    for (const c of d.children) {
      list.push({
        ...c,
        domainId: d.id,
        domainLabel: d.label,
        icon: d.icon,
      })
    }
  }
  return list
})

const currentNav = computed(() => {
  const hit = flatNav.value.find((n) => n.id === activeTab.value)
  if (!hit) return OVERVIEW_NAV[0]
  if (hit.domainLabel && hit.domainId !== 'finance') {
    return { ...hit, label: `${hit.domainLabel} · ${hit.label}` }
  }
  if (hit.id === 'finance') {
    const t = FINANCE_TABS.find((x) => x.id === financeTab.value)
    return {
      ...hit,
      label: t ? `财务 · ${t.label}` : '财务 · 经营报表',
      desc: t?.desc || hit.desc,
    }
  }
  return hit
})

const activePlatformKey = computed(() => {
  const id = activeTab.value
  if (id.startsWith('amz-')) return 'amazon'
  if (id.startsWith('tk-')) return 'tiktok'
  if (id.startsWith('temu-')) return 'temu'
  return ''
})

const systemChildActive = computed(() => SYSTEM_NAV.some((n) => n.id === activeTab.value))

const stats = computed(() => {
  const items = tasks.value || []
  return {
    total: total.value,
    open: items.filter((t) => t.status === 'open').length,
    doing: items.filter((t) => t.status === 'in_progress').length,
    resolved: items.filter((t) => t.status === 'resolved').length,
    shops: shops.value.length,
  }
})

const platformTaskStats = computed(() => {
  const map = { amazon: 0, tiktok: 0, temu: 0 }
  for (const t of tasks.value || []) {
    const p = (t.platform || '').toLowerCase()
    if (p in map) map[p] += 1
    else map[p] = (map[p] || 0) + 1
  }
  const max = Math.max(1, ...Object.values(map))
  return Object.entries(map).map(([platform, count]) => ({
    platform,
    count,
    pct: Math.round((count / max) * 100),
  }))
})

const platformShopStats = computed(() => {
  const map = { amazon: 0, tiktok: 0, temu: 0 }
  for (const s of shops.value || []) {
    const p = (s.platform || '').toLowerCase()
    if (p in map) map[p] += 1
    else map[p] = (map[p] || 0) + 1
  }
  return Object.entries(map).map(([platform, count]) => ({ platform, count }))
})

const openAnomalies = computed(() =>
  (tasks.value || []).filter((t) => t.status === 'open' || t.status === 'in_progress').slice(0, 8),
)

const statusBars = computed(() => {
  const items = tasks.value || []
  const n = Math.max(items.length, 1)
  const rows = [
    { key: 'open', label: '待处理', count: items.filter((t) => t.status === 'open').length, color: '#3b82f6' },
    { key: 'in_progress', label: '进行中', count: items.filter((t) => t.status === 'in_progress').length, color: '#f59e0b' },
    { key: 'resolved', label: '已闭环', count: items.filter((t) => t.status === 'resolved').length, color: '#10b981' },
    { key: 'cancelled', label: '已取消', count: items.filter((t) => t.status === 'cancelled').length, color: '#9ca3af' },
  ]
  return rows.map((r) => ({ ...r, pct: Math.round((r.count / n) * 100) }))
})

const platformScopedTasks = computed(() => {
  const key = activePlatformKey.value
  if (!key) return tasks.value || []
  return (tasks.value || []).filter((t) => (t.platform || '').toLowerCase() === key)
})

const platformScopedShops = computed(() => {
  const key = activePlatformKey.value
  if (!key) return shops.value || []
  return (shops.value || []).filter((s) => (s.platform || '').toLowerCase() === key)
})

const platformOpenCount = computed(
  () => platformScopedTasks.value.filter((t) => t.status === 'open' || t.status === 'in_progress').length,
)

const currentFinance = computed(() => FINANCE_TABS.find((t) => t.id === financeTab.value) || FINANCE_TABS[0])

const isAmzShipping = computed(() => activeTab.value === 'amz-shipping')
const isTemuShipping = computed(() => activeTab.value === 'temu-shipping')
const isShippingPage = computed(() => isAmzShipping.value || isTemuShipping.value)
const currentShippingPipeline = computed(() =>
  isAmzShipping.value ? shippingPipelineAmazon : shippingPipelineTemu,
)
const currentShippingShops = computed(() =>
  isAmzShipping.value ? shippingShopsAmazon : shippingShopsTemu,
)
const shippingTitle = computed(() =>
  isAmzShipping.value ? 'Amazon 自动化发货' : 'Temu 自动化发货',
)
const shippingSubtitle = computed(() =>
  isAmzShipping.value
    ? 'FBA 库存与绩效联动；FBM 走赛狐 → 英国海外仓（金猫/黑猫）→ 回传。与 Temu 共用发货桥能力，规则按平台分流。'
    : 'Temu 订单经赛狐 ERP 推送英国海外仓 WMS，出库后回传闭环。现网独立进程，中台做监控与入口。',
)

function isDomainChildActive(domainId) {
  return DOMAIN_NAV.find((d) => d.id === domainId)?.children.some((c) => c.id === activeTab.value)
}

function persistExpand() {
  try {
    localStorage.setItem(EXPAND_KEY, JSON.stringify(expandedDomains.value))
  } catch {
    /* ignore */
  }
}

function toggleDomain(id) {
  expandedDomains.value[id] = !expandedDomains.value[id]
  persistExpand()
}

function toggleSystem() {
  systemOpen.value = !systemOpen.value
  try {
    localStorage.setItem(SYSTEM_KEY, systemOpen.value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

function statusLabel(s) {
  return (
    {
      open: '待处理',
      in_progress: '进行中',
      resolved: '已闭环',
      cancelled: '已取消',
      ignored: '已忽略',
    }[s] || s
  )
}

function priorityLabel(p) {
  return p || '—'
}

function levelLabel(code, priority) {
  const raw = String(code || '').toLowerCase()
  if (raw === 'red') return '红'
  if (raw === 'orange') return '橙'
  if (raw === 'yellow') return '黄'
  const p = String(priority || '').toUpperCase()
  if (p === 'P0') return '红'
  if (p === 'P1') return '橙'
  if (p === 'P2') return '黄'
  return '—'
}

function levelClass(code, priority) {
  const raw = String(code || '').toLowerCase()
  if (raw === 'red' || raw === 'orange' || raw === 'yellow') return 'lvl-' + raw
  const p = String(priority || '').toUpperCase()
  if (p === 'P0') return 'lvl-red'
  if (p === 'P1') return 'lvl-orange'
  if (p === 'P2') return 'lvl-yellow'
  return 'lvl-unknown'
}

function fmtMetricValue(v, label) {
  if (v == null || v === '') return label || '—'
  const n = Number(v)
  const num = Number.isNaN(n) ? String(v) : n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  return label ? `${num} ${label}` : num
}

const tkShops = computed(() =>
  (shops.value || []).filter((s) => (s.platform || '').toLowerCase() === 'tiktok'),
)

const tkStats = computed(() => ({
  total: tkTotal.value,
  open: tkSummary.value.open || 0,
  doing: tkSummary.value.in_progress || 0,
  resolved: tkSummary.value.resolved || 0,
  closedOther: (tkSummary.value.cancelled || 0) + (tkSummary.value.ignored || 0),
}))

function fmtTime(v) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return String(v)
  }
}

function switchTab(id) {
  if (id === 'temu-tasks') {
    openGlobalTasks('temu')
    return
  }

  activeTab.value = id
  error.value = ''
  syncMsg.value = ''
  aiMsg.value = ''

  for (const d of DOMAIN_NAV) {
    if (d.children.some((c) => c.id === id)) {
      expandedDomains.value[d.id] = true
      persistExpand()
    }
  }
  if (SYSTEM_NAV.some((n) => n.id === id)) {
    systemOpen.value = true
    try {
      localStorage.setItem(SYSTEM_KEY, '1')
    } catch {
      /* ignore */
    }
  }

  if (id === 'tk-tasks') {
    expandedDomains.value.tiktok = true
    persistExpand()
    tkFilters.page = 1
  } else if (id === 'tk-ads') {
    expandedDomains.value.tiktok = true
    persistExpand()
    tkAdsFilters.page = 1
  } else if (id === 'amz-anomaly' || id === 'amz-patrol') {
    filters.platform = 'amazon'
    filters.page = 1
  } else if (id === 'temu-health') {
    filters.platform = 'temu'
    filters.page = 1
  } else if (
    id === 'boss' ||
    id === 'dashboard' ||
    id.endsWith('-overview') ||
    id === 'plugins' ||
    id === 'tk-ads' ||
    id === 'tk-report' ||
    id.startsWith('purchase-') ||
    id.startsWith('design-') ||
    id === 'finance' ||
    id === 'amz-replenish'
  ) {
    filters.platform = ''
    filters.page = 1
  }
}

function openGlobalTasks(platform = '') {
  filters.platform = platform
  filters.page = 1
  activeTab.value = 'tasks'
  systemOpen.value = true
  try {
    localStorage.setItem(SYSTEM_KEY, '1')
  } catch {
    /* ignore */
  }
  loadTasks()
}

function onFilterChange() {
  filters.page = 1
  return loadTasks()
}

function onTkFilterChange() {
  tkFilters.page = 1
  return loadTkTasks()
}

async function refreshActive() {
  error.value = ''
  loading.value = true
  try {
    if (activeTab.value === 'shops') await loadShops()
    else if (activeTab.value === 'tk-tasks') {
      await Promise.all([loadTkTasks(), loadTkTypes(), loadShops(), checkHealth()])
    } else if (activeTab.value === 'tk-ads') {
      await Promise.all([loadTkAds(), loadShops(), checkHealth()])
    } else if (activeTab.value === 'tk-content') {
      await Promise.all([loadTkContent(), loadTkTraffic(), loadShops(), checkHealth()])
    } else if (activeTab.value === 'tk-affiliate') {
      await Promise.all([loadTkAffiliate(), loadTkAffiliateShop(), loadShops(), checkHealth()])
    } else if (activeTab.value === 'tk-overview') {
      await Promise.all([loadTkShopDaily(), loadTkProductRanking(), loadTkTasks(), loadShops(), checkHealth()])
    } else await Promise.all([loadTasks(), loadShops(), checkHealth()])
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  } finally {
    loading.value = false
  }
}

async function checkHealth() {
  try {
    health.value = await api('/health', { auth: false })
  } catch (e) {
    health.value = { status: 'down', detail: e.message }
  }
}

async function doLogin() {
  error.value = ''
  loading.value = true
  try {
    const data = await api('/api/v1/auth/login', {
      method: 'POST',
      auth: false,
      body: { username: loginForm.username, password: loginForm.password },
    })
    setToken(data.access_token)
    token.value = data.access_token
    activeTab.value = 'boss'
    await bootstrap()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function logout() {
  setToken('')
  token.value = ''
  me.value = null
  tasks.value = []
  tkTasks.value = []
  shops.value = []
  activeTab.value = 'boss'
}

async function bootstrap() {
  error.value = ''
  loading.value = true
  try {
    me.value = await api('/api/v1/auth/me')
    await Promise.all([loadTasks(), loadShops(), loadTkTypes(), checkHealth()])
  } catch (e) {
    if (e.status === 401) logout()
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.platform) q.set('platform', filters.platform)
  q.set('page', String(filters.page))
  q.set('page_size', String(filters.page_size))
  const data = await api(`/api/v1/tasks?${q.toString()}`)
  tasks.value = data.items || []
  total.value = data.total || 0
}

async function loadTkTasks() {
  const q = new URLSearchParams()
  if (tkFilters.status) q.set('status', tkFilters.status)
  if (tkFilters.priority) q.set('priority', tkFilters.priority)
  if (tkFilters.anomaly_code) q.set('anomaly_code', tkFilters.anomaly_code)
  if (tkFilters.object_type) q.set('object_type', tkFilters.object_type)
  if (tkFilters.shop_external_id) q.set('shop_external_id', tkFilters.shop_external_id)
  if (tkFilters.q) q.set('q', tkFilters.q)
  if (tkFilters.open_only) q.set('open_only', 'true')
  q.set('page', String(tkFilters.page))
  q.set('page_size', String(tkFilters.page_size))
  const data = await api(`/api/v1/tk/anomaly-tasks?${q.toString()}`)
  tkTasks.value = data.items || []
  tkTotal.value = data.total || 0
  tkSummary.value = data.summary || { open: 0, in_progress: 0, resolved: 0, cancelled: 0, ignored: 0 }
}

async function loadTkTypes() {
  try {
    const data = await api('/api/v1/tk/anomaly-tasks/types')
    tkTypes.value = data.items || []
    if (!tkCreateForm.anomaly_code && tkTypes.value.length) {
      tkCreateForm.anomaly_code = tkTypes.value[0].code
    }
  } catch {
    tkTypes.value = []
  }
}

async function loadTkAds() {
  tkAdsLoading.value = true
  try {
    const q = new URLSearchParams()
    if (tkAdsFilters.biz_date) q.set('biz_date', tkAdsFilters.biz_date)
    if (tkAdsFilters.shop_external_id) q.set('shop_external_id', tkAdsFilters.shop_external_id)
    if (tkAdsFilters.q) q.set('q', tkAdsFilters.q)
    q.set('page', String(tkAdsFilters.page))
    q.set('page_size', String(tkAdsFilters.page_size))
    const data = await api(`/api/v1/tk/ads/campaigns?${q.toString()}`)
    tkAdsItems.value = data.items || []
    tkAdsTotal.value = data.total || 0
    tkAdsBizDate.value = data.biz_date || ''
    if (!tkAdsFilters.biz_date && data.biz_date) tkAdsFilters.biz_date = data.biz_date
    tkAdsSummary.value = data.summary || {
      spend: 0,
      orders: 0,
      revenue: 0,
      roi: null,
      open_anomaly_rows: 0,
    }
    tkAdsAvailableDates.value = data.available_dates || []
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkAdsLoading.value = false
  }
}

async function loadTkShopDaily() {
  tkShopDailyLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('lookback_days', '1')
    q.set('page_size', '20')
    const data = await api(`/api/v1/tk/shop-daily?${q.toString()}`)
    tkShopDailyBizDate.value = data.biz_date || ''
    tkShopDailyItems.value = data.items || []
    tkShopDailyNote.value = data.note || ''
    tkShopDailySummary.value = data.summary || {
      gmv: 0,
      orders_cnt: 0,
      buyers_cnt: 0,
      refund_amount: 0,
      ad_spend: 0,
      ad_revenue: 0,
      ad_orders: 0,
      ad_roi: null,
      aov: null,
      shop_count: 0,
      real_shop_rows: 0,
      ads_fallback_rows: 0,
      open_anomaly_count: 0,
      boss_decision_count: 0,
      data_source: 'empty',
    }
    if (data.freshness) {
      tkFreshness.value = {
        as_of: data.freshness.as_of || '',
        shop_daily_max: data.freshness.shop_daily_max || null,
        ads_max: data.freshness.ads_max || null,
        content_max: data.freshness.content_max || null,
        traffic_max: data.freshness.traffic_max || null,
        affiliate_max: data.freshness.affiliate_max || null,
        shop_daily_age_days: data.freshness.shop_daily_age_days,
        ads_age_days: data.freshness.ads_age_days,
        content_age_days: data.freshness.content_age_days,
        traffic_age_days: data.freshness.traffic_age_days,
        affiliate_age_days: data.freshness.affiliate_age_days,
        open_anomaly_count: data.freshness.open_anomaly_count || 0,
        boss_decision_count: data.freshness.boss_decision_count || 0,
        stale: data.freshness.stale || [],
        ok: data.freshness.ok !== false,
      }
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkShopDailyLoading.value = false
  }
}

function onTkAdsFilterChange() {
  tkAdsFilters.page = 1
  return loadTkAds()
}

function fmtNum(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function fmtRoi(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toFixed(2)
}

function anomalyCodeLabel(code) {
  const map = {
    ads_roi_low: 'ROI过低',
    ads_spend_no_sale: '空耗',
    ads_budget_burn: '预算将尽',
    ads_cpa_high: '下单成本高',
    product_stockout: '断货',
    product_stock_low: '库存不足',
    shop_gmv_drop: 'GMV骤降',
    shop_order_drop: '订单骤降',
    content_gmv_drop: '视频GMV骤降',
    content_play_drop: '视频播放崩',
    content_imp_no_order: '视频有曝无单',
    creator_invest_no_sale: '达人有投入无成交',
    creator_gmv_drop: '达人归因GMV骤降',
    affiliate_creators_sold_drop: '动销达人数下降',
    creator_refund_high: '达人退款异常',
  }
  return map[code] || code
}

function objectTypeLabel(t) {
  const map = {
    campaign: '广告',
    product: '库存',
    shop: '店铺分析',
    content: '视频内容',
    creator: '达人表现',
  }
  return map[t] || t || '—'
}


async function loadTkProductRanking() {
  tkProductRankLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('limit', String(tkProductRankLimit.value || 10))
    const data = await api(`/api/v1/tk/products/ranking?${q.toString()}`)
    tkProductRankItems.value = data.items || []
    tkProductRankSummary.value = data.summary || {
      product_count: 0,
      sales_qty_sum: 0,
      shop_count: 0,
      metric: 'sales_qty',
      note: '',
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkProductRankLoading.value = false
  }
}

async function loadTkContent() {
  tkContentLoading.value = true
  try {
    const q = new URLSearchParams()
    if (tkContentFilters.biz_date) q.set('biz_date', tkContentFilters.biz_date)
    if (tkContentFilters.shop_external_id) q.set('shop_external_id', tkContentFilters.shop_external_id)
    // 显式传 channel（含空串=全部），避免后端默认 short_video 盖住「全部」
    q.set('channel', tkContentFilters.channel || '')
    q.set('order_by', tkContentFilters.order_by || 'attributed_gmv')
    q.set('page', String(tkContentFilters.page))
    q.set('page_size', String(tkContentFilters.page_size))
    // lookback=1：只看所选/最新锚点日，避免跨窗混加
    q.set('lookback_days', '1')
    const data = await api(`/api/v1/tk/content?${q.toString()}`)
    tkContentItems.value = data.items || []
    tkContentTotal.value = data.total || 0
    tkContentBizDate.value = data.biz_date || ''
    if (!tkContentFilters.biz_date && data.biz_date) tkContentFilters.biz_date = data.biz_date
    tkContentAvailableDates.value = data.available_dates || []
    tkContentSummary.value = data.summary || {
      row_count: 0,
      content_count: 0,
      shop_count: 0,
      attributed_gmv_sum: 0,
      play_count_sum: 0,
      impressions_sum: 0,
      attributed_sku_orders_sum: 0,
      metric: 'window_snapshot',
      note: '',
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkContentLoading.value = false
  }
}

async function loadTkTraffic() {
  tkTrafficLoading.value = true
  try {
    const q = new URLSearchParams()
    if (tkTrafficFilters.biz_date) q.set('biz_date', tkTrafficFilters.biz_date)
    if (tkTrafficFilters.shop_external_id) q.set('shop_external_id', tkTrafficFilters.shop_external_id)
    // channel 空串 = 不传，后端默认 product_card；要「全部」需显式关掉 filter
    // API filter_channel=bool(channel)；传空则不过滤，便于多渠道对比
    if (tkTrafficFilters.channel) q.set('channel', tkTrafficFilters.channel)
    else q.set('channel', '')
    q.set('order_by', tkTrafficFilters.order_by || 'gmv')
    q.set('page', String(tkTrafficFilters.page))
    q.set('page_size', String(tkTrafficFilters.page_size))
    q.set('lookback_days', '1')
    const data = await api(`/api/v1/tk/product-traffic?${q.toString()}`)
    tkTrafficItems.value = data.items || []
    tkTrafficTotal.value = data.total || 0
    tkTrafficBizDate.value = data.biz_date || ''
    if (!tkTrafficFilters.biz_date && data.biz_date) tkTrafficFilters.biz_date = data.biz_date
    tkTrafficAvailableDates.value = data.available_dates || []
    tkTrafficSummary.value = data.summary || {
      row_count: 0,
      product_count: 0,
      shop_count: 0,
      gmv_sum: 0,
      impressions_sum: 0,
      orders_sum: 0,
      metric: 'window_snapshot',
      note: '',
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkTrafficLoading.value = false
  }
}

function onTkContentFilterChange() {
  tkContentFilters.page = 1
  return loadTkContent()
}

function onTkTrafficFilterChange() {
  tkTrafficFilters.page = 1
  return loadTkTraffic()
}

async function loadTkAffiliate() {
  tkAffiliateLoading.value = true
  try {
    const q = new URLSearchParams()
    if (tkAffiliateFilters.biz_date) q.set('biz_date', tkAffiliateFilters.biz_date)
    if (tkAffiliateFilters.shop_external_id) {
      q.set('shop_external_id', tkAffiliateFilters.shop_external_id)
    }
    if (tkAffiliateFilters.sold_only) q.set('sold_only', 'true')
    q.set('order_by', tkAffiliateFilters.order_by || 'gmv')
    q.set('page', String(tkAffiliateFilters.page))
    q.set('page_size', String(tkAffiliateFilters.page_size))
    q.set('lookback_days', '1')
    const data = await api(`/api/v1/tk/affiliate?${q.toString()}`)
    tkAffiliateItems.value = data.items || []
    tkAffiliateTotal.value = data.total || 0
    tkAffiliateBizDate.value = data.biz_date || ''
    if (!tkAffiliateFilters.biz_date && data.biz_date) {
      tkAffiliateFilters.biz_date = data.biz_date
    }
    tkAffiliateAvailableDates.value = data.available_dates || []
    tkAffiliateSummary.value = data.summary || {
      row_count: 0,
      creator_count: 0,
      sold_creator_count: 0,
      shop_count: 0,
      gmv_sum: 0,
      order_units_sum: 0,
      est_commission_sum: 0,
      orders_cnt_sum: 0,
      metric: 'window_snapshot',
      note: '',
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkAffiliateLoading.value = false
  }
}

async function loadTkAffiliateShop() {
  tkAffiliateShopLoading.value = true
  try {
    const q = new URLSearchParams()
    if (tkAffiliateShopFilters.biz_date) q.set('biz_date', tkAffiliateShopFilters.biz_date)
    if (tkAffiliateShopFilters.shop_external_id) {
      q.set('shop_external_id', tkAffiliateShopFilters.shop_external_id)
    }
    q.set('page', String(tkAffiliateShopFilters.page))
    q.set('page_size', String(tkAffiliateShopFilters.page_size))
    q.set('lookback_days', '1')
    const data = await api(`/api/v1/tk/affiliate/shop-daily?${q.toString()}`)
    tkAffiliateShopItems.value = data.items || []
    tkAffiliateShopTotal.value = data.total || 0
    tkAffiliateShopBizDate.value = data.biz_date || ''
    if (!tkAffiliateShopFilters.biz_date && data.biz_date) {
      tkAffiliateShopFilters.biz_date = data.biz_date
    }
    tkAffiliateShopAvailableDates.value = data.available_dates || []
    tkAffiliateShopSummary.value = data.summary || {
      row_count: 0,
      shop_count: 0,
      gmv_affiliate_sum: 0,
      order_units_sum: 0,
      est_commission_sum: 0,
      creators_sold_sum: 0,
      creators_published_sum: 0,
      metric: 'window_snapshot',
      note: '',
    }
  } catch (e) {
    if (e.status === 401) logout()
    else throw e
  } finally {
    tkAffiliateShopLoading.value = false
  }
}

function onTkAffiliateFilterChange() {
  tkAffiliateFilters.page = 1
  return loadTkAffiliate()
}

function onTkAffiliateShopFilterChange() {
  tkAffiliateShopFilters.page = 1
  return loadTkAffiliateShop()
}

/** P3.5 下钻：店 → 达人明细（带 shop_external_id） */
function drillToTkAffiliate(shopExternalId, opts = {}) {
  const shop = (shopExternalId || '').trim()
  tkAffiliatePane.value = opts.pane === 'shop' ? 'shop' : 'creator'
  tkAffiliateFilters.shop_external_id = shop
  tkAffiliateFilters.page = 1
  tkAffiliateShopFilters.shop_external_id = shop
  tkAffiliateShopFilters.page = 1
  if (opts.biz_date) {
    tkAffiliateFilters.biz_date = opts.biz_date
    tkAffiliateShopFilters.biz_date = opts.biz_date
  }
  if (activeTab.value === 'tk-affiliate') {
    return Promise.all([loadTkAffiliate(), loadTkAffiliateShop()])
  }
  switchTab('tk-affiliate')
}

/** P3.5 下钻：→ 达人表现异常（object_type=creator） */
function drillToTkCreatorTasks(shopExternalId) {
  const shop = (shopExternalId || '').trim()
  tkFilters.object_type = 'creator'
  tkFilters.shop_external_id = shop
  tkFilters.page = 1
  tkFilters.open_only = true
  if (activeTab.value === 'tk-tasks') {
    return loadTkTasks()
  }
  switchTab('tk-tasks')
}

/** 从异常任务回到达人 TAB */
function drillFromTkTaskToAffiliate(task) {
  if (!task) return
  const shop = (task.shop_external_id || '').trim()
  drillToTkAffiliate(shop, { pane: 'creator' })
}

async function runTkContentAnomalyEval(dryRun = false) {
  error.value = ''
  tkContentEvalMsg.value = ''
  tkContentEvalLoading.value = true
  try {
    const shop =
      tkContentFilters.shop_external_id ||
      tkTrafficFilters.shop_external_id ||
      tkFilters.shop_external_id ||
      undefined
    const biz = tkContentFilters.biz_date || tkTrafficFilters.biz_date || undefined
    const data = await api('/api/v1/tk/content/anomaly-eval', {
      method: 'POST',
      body: {
        dry_run: dryRun,
        project_center_task: !dryRun,
        shop_external_id: shop || undefined,
        biz_date: biz || undefined,
      },
    })
    const parts = [
      dryRun ? '【预览 dry-run】' : '【已写入】',
      `锚点日 ${data.biz_date}`,
      `扫描 ${data.scanned} 条内容`,
      `GMV骤降 ${data.hit_gmv_drop ?? 0}`,
      `播放/曝光崩 ${data.hit_play_drop ?? 0}`,
      `有曝无单 ${data.hit_imp_no_order ?? 0}`,
      `${dryRun ? '将' : '已'}处理 ${data.created_or_updated}`,
    ]
    if (data.missing_prev != null) parts.push(`无上窗 ${data.missing_prev}`)
    if (data.errors?.length) parts.push(`错误 ${data.errors.length}`)
    const sampleLine = (data.samples || [])
      .slice(0, 3)
      .map((s) => `${s.anomaly_code}:${s.summary || s.content_id || ''}`)
      .join(' · ')
    tkContentEvalMsg.value = parts.join(' · ') + (sampleLine ? `\n样例：${sampleLine}` : '')
    if (!dryRun) {
      await loadTkTasks()
      if (activeTab.value === 'tk-content') await loadTkContent()
    }
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  } finally {
    tkContentEvalLoading.value = false
  }
}

async function runTkAffiliateAnomalyEval(dryRun = false) {
  error.value = ''
  tkAffiliateEvalMsg.value = ''
  tkAffiliateEvalLoading.value = true
  try {
    const shop =
      tkAffiliateFilters.shop_external_id ||
      tkAffiliateShopFilters.shop_external_id ||
      tkFilters.shop_external_id ||
      undefined
    const biz =
      tkAffiliateFilters.biz_date || tkAffiliateShopFilters.biz_date || undefined
    const data = await api('/api/v1/tk/affiliate/anomaly-eval', {
      method: 'POST',
      body: {
        dry_run: dryRun,
        project_center_task: !dryRun,
        shop_external_id: shop || undefined,
        biz_date: biz || undefined,
      },
    })
    const parts = [
      dryRun ? '【预览 dry-run】' : '【已写入】',
      `锚点日 ${data.biz_date}`,
      `达人 ${data.scanned_creators ?? 0}`,
      `店级 ${data.scanned_shops ?? 0}`,
      `有投入无成交 ${data.hit_invest_no_sale ?? 0}`,
      `GMV骤降 ${data.hit_gmv_drop ?? 0}`,
      `动销降 ${data.hit_creators_sold_drop ?? 0}`,
      `退款异常 ${data.hit_refund_high ?? 0}`,
      `${dryRun ? '将' : '已'}处理 ${data.created_or_updated}`,
    ]
    if (data.missing_prev != null) parts.push(`无上窗 ${data.missing_prev}`)
    if (data.errors?.length) parts.push(`错误 ${data.errors.length}`)
    const sampleLine = (data.samples || [])
      .slice(0, 3)
      .map((s) => `${s.anomaly_code}:${s.summary || s.creator_id || s.shop_external_id || ''}`)
      .join(' · ')
    tkAffiliateEvalMsg.value = parts.join(' · ') + (sampleLine ? `\n样例：${sampleLine}` : '')
    if (!dryRun) {
      await loadTkTasks()
      if (activeTab.value === 'tk-affiliate') {
        await Promise.all([loadTkAffiliate(), loadTkAffiliateShop()])
      }
    }
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  } finally {
    tkAffiliateEvalLoading.value = false
  }
}

async function runTkAdsAnomalyEval(dryRun = false, fromAdsPage = false) {
  error.value = ''
  tkAdsEvalMsg.value = ''
  tkAdsEvalLoading.value = true
  try {
    const shop =
      (fromAdsPage ? tkAdsFilters.shop_external_id : tkFilters.shop_external_id) || undefined
    const biz =
      (fromAdsPage ? tkAdsFilters.biz_date : undefined) || tkAdsFilters.biz_date || undefined
    const data = await api('/api/v1/tk/ads/anomaly-eval', {
      method: 'POST',
      body: {
        dry_run: dryRun,
        project_center_task: !dryRun,
        shop_external_id: shop,
        biz_date: biz || undefined,
      },
    })
    const parts = [
      dryRun ? '【预览 dry-run】' : '【已写入】',
      `业务日 ${data.biz_date}`,
      `扫描 ${data.scanned} 条广告`,
      `ROI过低 ${data.hit_roi_low}`,
      `空耗 ${data.hit_spend_no_sale}`,
      `预算将尽 ${data.hit_budget_burn ?? 0}`,
      `高CPA ${data.hit_cpa_high ?? 0}`,
      `${dryRun ? '将' : '已'}处理 ${data.created_or_updated}`,
    ]
    if (data.errors?.length) parts.push(`错误 ${data.errors.length}`)
    if (data.thresholds) {
      parts.push(
        `阈值 min_spend=${data.thresholds.min_spend} global_roi=${data.thresholds.global_min_roi}` +
          ` burn=${data.thresholds.budget_burn_ratio ?? '-'} max_cpa=${data.thresholds.max_cpa ?? '-'}`,
      )
    }
    const sampleLine = (data.samples || [])
      .slice(0, 3)
      .map((s) => `${s.anomaly_code}:${s.campaign_name}`)
      .join(' · ')
    tkAdsEvalMsg.value = parts.join(' · ') + (sampleLine ? `\n样例：${sampleLine}` : '')
    if (!dryRun) {
      await loadTkTasks()
      if (fromAdsPage || activeTab.value === 'tk-ads') await loadTkAds()
    }
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  } finally {
    tkAdsEvalLoading.value = false
  }
}

async function runTkProductAnomalyEval(dryRun = false) {
  error.value = ''
  tkProductEvalMsg.value = ''
  tkProductEvalLoading.value = true
  try {
    const data = await api('/api/v1/tk/products/anomaly-eval', {
      method: 'POST',
      body: {
        dry_run: dryRun,
        project_center_task: !dryRun,
        shop_external_id: tkFilters.shop_external_id || undefined,
      },
    })
    const parts = [
      dryRun ? '【预览 dry-run】' : '【已写入】',
      `扫描 ${data.scanned} 条商品`,
      `断货 ${data.hit_stockout}`,
      `库存不足 ${data.hit_stock_low}`,
      `${dryRun ? '将' : '已'}处理 ${data.created_or_updated}`,
    ]
    if (data.errors?.length) parts.push(`错误 ${data.errors.length}`)
    if (data.thresholds) {
      parts.push(
        `阈值 stockout≤${data.thresholds.stockout_qty} low<${data.thresholds.stock_low_qty}`,
      )
    }
    const sampleLine = (data.samples || [])
      .slice(0, 3)
      .map((s) => `${s.anomaly_code}:${s.product_name || s.product_id}`)
      .join(' · ')
    tkProductEvalMsg.value = parts.join(' · ') + (sampleLine ? `\n样例：${sampleLine}` : '')
    if (!dryRun) await loadTkTasks()
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  } finally {
    tkProductEvalLoading.value = false
  }
}

async function loadShops() {
  const data = await api('/api/v1/shops')
  shops.value = data.items || []
}

async function loadGuidance(task) {
  drawer.guidance = null
  if (!task?.platform || !task?.anomaly_type) return
  drawer.guidanceLoading = true
  try {
    const q = new URLSearchParams({
      platform: task.platform,
      anomaly_type: task.anomaly_type,
    })
    drawer.guidance = await api(`/api/v1/kb/guidance?${q.toString()}`)
  } catch (e) {
    drawer.guidance = { history: [], playbooks: [], error: e.message }
  } finally {
    drawer.guidanceLoading = false
  }
}

function openProgress(task, source = 'center') {
  drawer.open = true
  drawer.mode = 'progress'
  drawer.source = source
  drawer.task = task
  drawer.note = ''
  drawer.action_code = ''
  drawer.effect_code = ''
  drawer.resolveStatus = 'resolved'
  if (source === 'center') loadGuidance(task)
  else drawer.guidance = null
}

function openResolve(task, source = 'center') {
  drawer.open = true
  drawer.mode = 'resolve'
  drawer.source = source
  drawer.task = task
  drawer.note = '已处理完成'
  drawer.action_code = task.last_action_code || ''
  drawer.effect_code = ''
  drawer.resolveStatus = 'resolved'
  if (source === 'center') loadGuidance(task)
  else drawer.guidance = null
}

function openCreate() {
  drawer.open = true
  drawer.mode = 'create'
  drawer.source = 'center'
  drawer.task = null
  drawer.note = ''
  createForm.biz_id = ''
  createForm.title = ''
  createForm.progress_note = ''
  if (activePlatformKey.value) createForm.platform = activePlatformKey.value
  else if (filters.platform) createForm.platform = filters.platform
}

function openTkCreate() {
  drawer.open = true
  drawer.mode = 'create'
  drawer.source = 'tk'
  drawer.task = null
  drawer.note = ''
  tkCreateForm.summary = ''
  tkCreateForm.product_id = ''
  tkCreateForm.product_name = ''
  tkCreateForm.product_name_cn = ''
  tkCreateForm.seller_sku = ''
  tkCreateForm.object_ref = ''
  tkCreateForm.metric_snapshot = ''
  tkCreateForm.progress_note = ''
  tkCreateForm.priority = 'P1'
  if (!tkCreateForm.shop_external_id && tkShops.value.length) {
    tkCreateForm.shop_external_id = tkShops.value[0].external_shop_id
  }
  if (!tkCreateForm.anomaly_code && tkTypes.value.length) {
    tkCreateForm.anomaly_code = tkTypes.value[0].code
  }
}

function closeDrawer() {
  drawer.open = false
}

async function submitDrawer() {
  error.value = ''
  loading.value = true
  try {
    if (drawer.source === 'tk') {
      if (drawer.mode === 'create') {
        if (!tkCreateForm.anomaly_code) throw new Error('请选择异常类型')
        if (
          !tkCreateForm.object_ref &&
          !tkCreateForm.product_id &&
          !tkCreateForm.seller_sku &&
          !tkCreateForm.shop_external_id
        ) {
          throw new Error('请填写商品ID / SKU / 对象引用，或选择店铺')
        }
        await api('/api/v1/tk/anomaly-tasks', {
          method: 'POST',
          body: {
            anomaly_code: tkCreateForm.anomaly_code,
            summary: tkCreateForm.summary || undefined,
            shop_external_id: tkCreateForm.shop_external_id || undefined,
            product_id: tkCreateForm.product_id || undefined,
            product_name: tkCreateForm.product_name || undefined,
            product_name_cn: tkCreateForm.product_name_cn || undefined,
            seller_sku: tkCreateForm.seller_sku || undefined,
            object_ref: tkCreateForm.object_ref || undefined,
            priority: tkCreateForm.priority || undefined,
            metric_snapshot: tkCreateForm.metric_snapshot || undefined,
            progress_note: tkCreateForm.progress_note || undefined,
            owner_name: tkCreateForm.owner_name || undefined,
            project_center_task: true,
          },
        })
      } else if (drawer.mode === 'progress') {
        if (!drawer.note.trim()) throw new Error('请填写进度说明')
        await api(`/api/v1/tk/anomaly-tasks/${drawer.task.id}/progress`, {
          method: 'POST',
          body: { note: drawer.note, status: 'in_progress' },
        })
      } else if (drawer.mode === 'resolve') {
        await api(`/api/v1/tk/anomaly-tasks/${drawer.task.id}/resolve`, {
          method: 'POST',
          body: {
            note: drawer.note || undefined,
            status: drawer.resolveStatus || 'resolved',
          },
        })
      }
      closeDrawer()
      await loadTkTasks()
    } else {
      if (drawer.mode === 'create') {
        if (!createForm.biz_id || !createForm.title) throw new Error('请填写业务ID与标题')
        await api('/api/v1/tasks', {
          method: 'POST',
          body: {
            platform: createForm.platform,
            anomaly_type: createForm.anomaly_type,
            biz_id: createForm.biz_id,
            title: createForm.title,
            progress_note: createForm.progress_note || undefined,
          },
        })
      } else if (drawer.mode === 'progress') {
        if (!drawer.note.trim()) throw new Error('请填写进度说明')
        await api(`/api/v1/tasks/${drawer.task.id}/progress`, {
          method: 'POST',
          body: {
            note: drawer.note,
            status: 'in_progress',
            action_code: drawer.action_code || undefined,
          },
        })
      } else if (drawer.mode === 'resolve') {
        if (isSkeletonTask(drawer.task) && !drawer.effect_code) {
          throw new Error('骨架异常类型闭环必须选择效果标签')
        }
        await api(`/api/v1/tasks/${drawer.task.id}/resolve`, {
          method: 'POST',
          body: {
            note: drawer.note || undefined,
            action_code: drawer.action_code || undefined,
            effect_code: drawer.effect_code || undefined,
          },
        })
      }
      closeDrawer()
      await loadTasks()
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function triggerFeishu() {
  error.value = ''
  syncMsg.value = ''
  loading.value = true
  try {
    const r = await api('/api/v1/export/feishu', {
      method: 'POST',
      body: { table_key: 'tasks', mode: 'incremental' },
    })
    syncMsg.value = `已入队飞书同步 job: ${r.job_id}`
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function generateAiReport() {
  error.value = ''
  const tpl = aiReportTemplates.find((t) => t.id === aiForm.template)
  const rangeLabel =
    {
      yesterday: '昨日',
      last7: '近 7 天',
      last30: '近 30 天',
    }[aiForm.range] || aiForm.range

  aiMsg.value = [
    `【${tpl?.name || 'AI 报表'}】${rangeLabel}`,
    `范围：${tpl?.scope || '全平台'}`,
    `异常任务 ${stats.value.total} 条（待处理 ${stats.value.open} / 进行中 ${stats.value.doing}），店铺 ${stats.value.shops} 个。`,
    platformTaskStats.value.map((p) => `${p.platform}: ${p.count}`).join(' · ') || '分平台：暂无数据',
    aiForm.note ? `补充说明：${aiForm.note}` : '',
    '',
    '（Phase0 演示：基于中心库任务/店铺汇总生成预览。）',
  ]
    .filter(Boolean)
    .join('\n')
}

function goPlatformAi(templateId) {
  aiForm.template = templateId
  switchTab('ai-reports')
}

const showTaskActions = computed(
  () =>
    activeTab.value === 'tasks' ||
    activeTab.value === 'amz-anomaly' ||
    activeTab.value === 'temu-health',
)

const showTkTaskActions = computed(() => activeTab.value === 'tk-tasks')

const showRefresh = computed(
  () =>
    showTaskActions.value ||
    showTkTaskActions.value ||
    activeTab.value === 'tk-ads' ||
    activeTab.value === 'tk-content' ||
    activeTab.value === 'tk-affiliate' ||
    activeTab.value === 'boss' ||
    activeTab.value === 'dashboard' ||
    activeTab.value.endsWith('-overview') ||
    activeTab.value === 'shops',
)

watch(activeTab, async (id) => {
  if (!token.value) return
  try {
    if (id === 'tk-tasks') {
      await Promise.all([loadTkTasks(), loadTkTypes(), loadShops()])
      return
    }
    if (id === 'tk-ads') {
      await Promise.all([loadTkAds(), loadShops()])
      return
    }
    if (id === 'tk-content') {
      await Promise.all([loadTkContent(), loadTkTraffic(), loadShops()])
      return
    }
    if (id === 'tk-affiliate') {
      await Promise.all([loadTkAffiliate(), loadTkAffiliateShop(), loadShops()])
      return
    }
    if (id === 'tk-overview') {
      await Promise.all([loadTkShopDaily(), loadTkProductRanking(), loadTkTasks(), loadShops()])
      return
    }
    const needTasks =
      id === 'tasks' ||
      id === 'dashboard' ||
      id === 'boss' ||
      id.startsWith('amz-') ||
      id.startsWith('tk-') ||
      id.startsWith('temu-')
    const needShops =
      id === 'shops' ||
      id === 'dashboard' ||
      id === 'boss' ||
      id.endsWith('-overview') ||
      id === 'temu-shipping' ||
      id === 'amz-shipping'
    if (needTasks) await loadTasks()
    if (needShops) await loadShops()
  } catch (e) {
    if (e.status === 401) logout()
    else error.value = e.message
  }
})

onMounted(async () => {
  await checkHealth()
  if (token.value) {
    try {
      await bootstrap()
    } catch {
      logout()
    }
  }
})
</script>

<template>
  <div v-if="!token" class="login-wrap">
    <div class="card login-card">
      <h1>清泉跨境系统</h1>
      <div class="sub">企业中台 · Phase0 演示</div>
      <div class="stack">
        <label class="field">
          用户名
          <input v-model="loginForm.username" autocomplete="username" />
        </label>
        <label class="field">
          密码
          <input
            v-model="loginForm.password"
            type="password"
            autocomplete="current-password"
            @keyup.enter="doLogin"
          />
        </label>
        <div v-if="error" class="error">{{ error }}</div>
        <button class="btn btn-primary" :disabled="loading" @click="doLogin">
          {{ loading ? '登录中…' : '登录' }}
        </button>
        <div class="muted">
          默认账号 admin / admin123 · API
          <span :style="{ color: health?.status === 'ok' ? 'var(--ok)' : 'var(--danger)' }">
            {{ health?.status === 'ok' ? '在线' : '离线' }}
          </span>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="logo">清泉中台</div>
        <div class="tag">老板驾驶舱 · 部门业务域</div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-label">总览</div>
        <button
          v-for="item in OVERVIEW_NAV"
          :key="item.id"
          type="button"
          class="nav-item"
          :class="{ active: activeTab === item.id }"
          @click="switchTab(item.id)"
        >
          <span class="icon">{{ item.icon }}</span>
          <span class="label">{{ item.label }}</span>
        </button>

        <div class="nav-section-label">业务域</div>
        <div v-for="d in DOMAIN_NAV" :key="d.id" class="nav-group">
          <button
            type="button"
            class="nav-item nav-group-head"
            :class="{ active: isDomainChildActive(d.id), open: expandedDomains[d.id] }"
            @click="toggleDomain(d.id)"
          >
            <span class="icon platform-icon">{{ d.icon }}</span>
            <span class="label">{{ d.label }}</span>
            <span class="chevron">{{ expandedDomains[d.id] ? '▾' : '▸' }}</span>
          </button>
          <div v-show="expandedDomains[d.id]" class="nav-children">
            <button
              v-for="child in d.children"
              :key="child.id"
              type="button"
              class="nav-item child"
              :class="{ active: activeTab === child.id }"
              @click="switchTab(child.id)"
            >
              <span class="label">{{ child.label }}</span>
            </button>
          </div>
        </div>

        <div class="nav-section-label system-label">系统</div>
        <div class="nav-group">
          <button
            type="button"
            class="nav-item nav-group-head system-head"
            :class="{ active: systemChildActive, open: systemOpen }"
            @click="toggleSystem"
          >
            <span class="icon">⚙</span>
            <span class="label">系统工具</span>
            <span class="chevron">{{ systemOpen ? '▾' : '▸' }}</span>
          </button>
          <div v-show="systemOpen" class="nav-children">
            <button
              v-for="item in SYSTEM_NAV"
              :key="item.id"
              type="button"
              class="nav-item child"
              :class="{ active: activeTab === item.id }"
              @click="switchTab(item.id)"
            >
              <span class="label">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <div class="sidebar-foot">
        <div class="user">{{ me?.display_name || me?.username || '用户' }}</div>
        <div>
          <span class="status-dot" :class="health?.status === 'ok' ? 'ok' : 'down'" />
          API {{ health?.status === 'ok' ? '正常' : '异常' }}
        </div>
        <button type="button" class="logout" @click="logout">退出登录</button>
      </div>
    </aside>

    <div class="main">
      <header class="main-header">
        <div>
          <h1>{{ currentNav.label }}</h1>
          <p class="desc">{{ currentNav.desc }}</p>
        </div>
        <div class="actions">
          <button v-if="showTaskActions" class="btn btn-primary" @click="openCreate">新建异常任务</button>
          <button v-if="showTkTaskActions" class="btn btn-primary" @click="openTkCreate">新建 TK 异常</button>
          <button v-if="showRefresh" class="btn" :disabled="loading" @click="refreshActive">刷新</button>
        </div>
      </header>

      <div class="main-body">
        <div v-if="error" class="error" style="margin-bottom: 12px">{{ error }}</div>

        <!-- 老板驾驶舱 -->
        <section v-show="activeTab === 'boss'">
          <div class="grid-stats">
            <div class="stat accent">
              <div class="label">异常任务总数</div>
              <div class="value">{{ stats.total }}</div>
            </div>
            <div class="stat">
              <div class="label">待处理</div>
              <div class="value">{{ stats.open }}</div>
            </div>
            <div class="stat">
              <div class="label">进行中</div>
              <div class="value">{{ stats.doing }}</div>
            </div>
            <div class="stat">
              <div class="label">店铺覆盖</div>
              <div class="value">{{ stats.shops }}</div>
            </div>
          </div>

          <div class="card" style="margin-bottom: 16px">
            <h2>业务域入口</h2>
            <div class="platform-entry-grid boss-entry-grid">
              <button type="button" class="platform-entry" @click="switchTab('purchase-dashboard')">
                <strong>采购</strong>
                <span class="muted">仪表盘 · 采购数据同步</span>
                <span class="phase-tag">规划中</span>
              </button>
              <button type="button" class="platform-entry" @click="switchTab('amz-overview')">
                <strong>Amazon</strong>
                <span class="muted">总览 · 补货 · 环比 · 发货 · 巡店</span>
              </button>
              <button type="button" class="platform-entry" @click="switchTab('tk-overview')">
                <strong>TikTok</strong>
                <span class="muted">广告 · 日报 · 异常</span>
              </button>
              <button type="button" class="platform-entry" @click="switchTab('temu-overview')">
                <strong>Temu</strong>
                <span class="muted">健康 · 发货 · 插件</span>
              </button>
              <button type="button" class="platform-entry" @click="switchTab('finance')">
                <strong>财务</strong>
                <span class="muted">利润 / 现金流 / 边际 / 报税</span>
                <span class="phase-tag">规划中</span>
              </button>
              <button type="button" class="platform-entry" @click="switchTab('design-tasks')">
                <strong>美工</strong>
                <span class="muted">任务表 · 推送</span>
                <span class="phase-tag">规划中</span>
              </button>
            </div>
          </div>

          <div class="dash-grid">
            <div class="card">
              <h2>运营风险 · 任务状态</h2>
              <div class="bar-list">
                <div v-for="row in statusBars" :key="row.key" class="bar-row">
                  <div class="bar-meta">
                    <span>{{ row.label }}</span>
                    <span class="mono">{{ row.count }} · {{ row.pct }}%</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: row.pct + '%', background: row.color }" />
                  </div>
                </div>
              </div>
            </div>
            <div class="card">
              <h2>分平台异常量</h2>
              <div class="bar-list">
                <div v-for="row in platformTaskStats" :key="row.platform" class="bar-row">
                  <div class="bar-meta">
                    <span class="platform-tag">{{ row.platform }}</span>
                    <span class="mono">{{ row.count }}</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill platform" :style="{ width: row.pct + '%' }" />
                  </div>
                </div>
              </div>
              <div class="muted" style="margin-top: 12px; font-size: 12px">
                财务现金/净利润、采购未付等接入后展示于本舱（Phase4）。
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <h2>未闭环异常</h2>
              <button class="btn btn-ghost" @click="switchTab('tasks')">异常任务中心 →</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>状态</th><th>平台</th><th>异常类型</th><th>标题</th><th>更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!openAnomalies.length">
                    <td colspan="5" class="muted">当前无待处理/进行中的异常。</td>
                  </tr>
                  <tr v-for="t in openAnomalies" :key="t.id">
                    <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                    <td>{{ t.platform }}</td>
                    <td class="mono">{{ t.anomaly_type }}</td>
                    <td>{{ t.title }}</td>
                    <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- 工作台 -->
        <section v-show="activeTab === 'dashboard'">
          <div class="grid-stats">
            <div class="stat accent"><div class="label">异常任务总数</div><div class="value">{{ stats.total }}</div></div>
            <div class="stat"><div class="label">本页待处理</div><div class="value">{{ stats.open }}</div></div>
            <div class="stat"><div class="label">本页进行中</div><div class="value">{{ stats.doing }}</div></div>
            <div class="stat"><div class="label">店铺数量</div><div class="value">{{ stats.shops }}</div></div>
          </div>
          <div class="card">
            <h2>快捷入口</h2>
            <div class="actions">
              <button class="btn btn-primary" @click="switchTab('boss')">老板驾驶舱</button>
              <button class="btn" @click="switchTab('tasks')">异常任务中心</button>
              <button class="btn" @click="switchTab('finance')">财务报表</button>
              <button class="btn" @click="switchTab('sync')">飞书同步</button>
            </div>
            <ul class="hint-list" style="margin-top: 16px">
              <li>导航按中台蓝图：总览 + 业务域 + 系统工具（底部折叠）。</li>
              <li>任务去重：平台 + 业务ID + 异常类型；闭环后再出现新建。</li>
            </ul>
          </div>
          <div class="card">
            <div class="card-head">
              <h2>最近异常任务</h2>
              <button class="btn btn-ghost" @click="switchTab('tasks')">全部 →</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>状态</th><th>平台</th><th>标题</th><th>更新时间</th></tr>
                </thead>
                <tbody>
                  <tr v-if="!tasks.length"><td colspan="4" class="muted">暂无异常任务</td></tr>
                  <tr v-for="t in tasks.slice(0, 5)" :key="t.id">
                    <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                    <td>{{ t.platform }}</td>
                    <td>{{ t.title }}</td>
                    <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- 采购 -->
        <section v-show="activeTab === 'purchase-dashboard'">
          <div class="card plan-card">
            <span class="phase-tag">Phase3 · 规划中</span>
            <h2 style="margin-top: 8px">采购仪表盘</h2>
            <p class="muted plan-p">销售天数（赛狐，周一 07:00）、滞销/断货任务、供应商概览（名称脱敏）。对接人：李瑾。</p>
            <ul class="hint-list">
              <li>任务类型建议：stockout / slow_moving / purchase_replenish</li>
              <li>与 AMZ 补货终审联动（助理 → 李瑾）</li>
            </ul>
            <div class="actions" style="margin-top: 12px">
              <button class="btn" @click="switchTab('purchase-sync')">采购数据同步</button>
              <button class="btn" @click="switchTab('amz-replenish')">AMZ 补货</button>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'purchase-sync'">
          <div class="card plan-card">
            <span class="phase-tag">Phase3 · 规划中</span>
            <h2 style="margin-top: 8px">采购数据同步</h2>
            <p class="muted plan-p">
              与系统底部「飞书同步」区分：本页聚焦采购域主数据/货值/未付等到中心库与飞书协作表，并收集
              <strong>使用改进</strong>反馈。
            </p>
            <label class="field" style="margin-top: 12px">
              使用改进建议（演示占位）
              <textarea placeholder="例如：希望断货任务按供应商汇总推送…" />
            </label>
            <button class="btn btn-primary" style="margin-top: 10px" type="button" disabled>提交（待接后端）</button>
          </div>
        </section>

        <!-- 平台总览（AMZ/TK/TEMU） -->
        <section v-show="activeTab.endsWith('-overview')">
          <div class="grid-stats">
            <div class="stat accent"><div class="label">本平台店铺</div><div class="value">{{ platformScopedShops.length }}</div></div>
            <div class="stat"><div class="label">本平台任务（当前列表）</div><div class="value">{{ platformScopedTasks.length }}</div></div>
            <div class="stat"><div class="label">未闭环</div><div class="value">{{ platformOpenCount }}</div></div>
            <div class="stat">
              <div class="label">调度 / 负责人</div>
              <div class="value" style="font-size: 12px; line-height: 1.4; font-weight: 600">
                {{ PLATFORM_META[activePlatformKey]?.schedule }}<br />
                <span class="muted">{{ PLATFORM_META[activePlatformKey]?.owner }}</span>
              </div>
            </div>
          </div>
          <div class="card">
            <h2>{{ PLATFORM_META[activePlatformKey]?.label }} · 能力焦点</h2>
            <p class="muted" style="margin: 0 0 12px; font-size: 13px">{{ PLATFORM_META[activePlatformKey]?.focus }}</p>
            <div v-if="activePlatformKey === 'amazon'" class="actions">
              <button class="btn btn-primary" @click="switchTab('amz-anomaly')">环比异常任务</button>
              <button class="btn" @click="switchTab('amz-replenish')">补货</button>
              <button class="btn" @click="switchTab('amz-shipping')">自动化发货</button>
              <button class="btn" @click="switchTab('amz-patrol')">巡店</button>
              <button class="btn" @click="openGlobalTasks('amazon')">统一任务引擎</button>
            </div>
            <div v-else-if="activePlatformKey === 'tiktok'" class="actions">
              <button class="btn btn-primary" @click="switchTab('tk-ads')">广告投流</button>
              <button class="btn" @click="switchTab('tk-content')">内容分析</button>
              <button class="btn" @click="switchTab('tk-affiliate')">达人表现</button>
              <button class="btn" @click="switchTab('tk-report')">日报 / AI</button>
              <button class="btn" @click="switchTab('tk-tasks')">异常任务</button>
              <button class="btn" :disabled="tkShopDailyLoading" @click="loadTkShopDaily">
                {{ tkShopDailyLoading ? '刷新店日…' : '刷新店日 KPI' }}
              </button>
            </div>
            <div v-else-if="activePlatformKey === 'temu'" class="actions">
              <button class="btn btn-primary" @click="switchTab('temu-health')">健康监测</button>
              <button class="btn" @click="switchTab('temu-shipping')">自动化发货</button>
              <button class="btn" @click="switchTab('temu-plugin')">监测插件</button>
              <button class="btn" @click="switchTab('temu-tasks')">异常任务</button>
            </div>
          </div>

          <!-- TK 店日 KPI（P0）：读 /api/v1/tk/shop-daily -->
          <template v-if="activePlatformKey === 'tiktok'">
            <div
              v-if="tkFreshnessBanner"
              class="freshness-banner warn"
              style="margin-top: 12px"
            >
              <strong>数据新鲜度</strong>
              <span>{{ tkFreshnessBanner }}</span>
              <span class="muted" style="margin-left: 8px">
                店日 {{ tkFreshness.shop_daily_max || '—' }}
                · 广告 {{ tkFreshness.ads_max || '—' }}
                · 内容 {{ tkFreshness.content_max || '—' }}
                · 商品卡 {{ tkFreshness.traffic_max || '—' }}
                · 达人 {{ tkFreshness.affiliate_max || '—' }}
              </span>
            </div>
            <div
              v-else-if="tkFreshness.shop_daily_max || tkFreshness.ads_max"
              class="freshness-banner ok"
              style="margin-top: 12px"
            >
              <strong>数据新鲜度</strong>
              <span class="muted">
                店日 {{ tkFreshness.shop_daily_max || '—' }}
                · 广告 {{ tkFreshness.ads_max || '—' }}
                · 内容 {{ tkFreshness.content_max || '—' }}
                · 商品卡 {{ tkFreshness.traffic_max || '—' }}
                · 达人 {{ tkFreshness.affiliate_max || '—' }}
                · 待老板决策 {{ tkFreshness.boss_decision_count || 0 }}
              </span>
            </div>
            <div class="grid-stats" style="margin-top: 12px">
              <div class="stat accent">
                <div class="label">店日 GMV{{ tkShopDailySummary.data_source === 'ads_rollup' ? '（广告估）' : '' }}</div>
                <div class="value">{{ fmtNum(tkShopDailySummary.gmv) }}</div>
              </div>
              <div class="stat">
                <div class="label">订单 / AOV</div>
                <div class="value" style="font-size: 18px">
                  {{ fmtNum(tkShopDailySummary.orders_cnt, 0) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    / {{ fmtNum(tkShopDailySummary.aov) }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">广告花费 · ROI</div>
                <div class="value" style="font-size: 18px">
                  {{ fmtNum(tkShopDailySummary.ad_spend) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ fmtRoi(tkShopDailySummary.ad_roi) }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">业务日 / 未闭环 · 老板决策</div>
                <div class="value" style="font-size: 16px">
                  {{ tkShopDailyBizDate || '—' }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkShopDailySummary.open_anomaly_count || 0 }}
                    · {{ tkShopDailySummary.boss_decision_count || tkFreshness.boss_decision_count || 0 }}
                  </span>
                </div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="card-head">
                <h2>店日明细（最新业务日）</h2>
                <span class="muted" style="font-size: 12px">
                  源：{{ tkShopDailySummary.data_source || '—' }}
                  <template v-if="tkShopDailyNote"> · {{ tkShopDailyNote }}</template>
                </span>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>GMV</th>
                      <th>订单</th>
                      <th>广告花费</th>
                      <th>广告ROI</th>
                      <th>健康分</th>
                      <th>源</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkShopDailyLoading && !tkShopDailyItems.length">
                      <td colspan="7" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkShopDailyItems.length">
                      <td colspan="7" class="muted">暂无店日数据（请跑 shop-modules 或确认广告已入库）</td>
                    </tr>
                    <tr v-for="r in tkShopDailyItems" :key="r.id || (r.shop_external_id + r.biz_date)">
                      <td>
                        {{ r.shop_name || '—' }}
                        <div class="muted mono" style="font-size: 11px">{{ r.shop_external_id }}</div>
                        <div class="actions" style="margin-top: 4px; gap: 4px">
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            title="达人归因 ≠ 店日 GMV；仅下钻查看联盟表现"
                            @click="drillToTkAffiliate(r.shop_external_id)"
                          >
                            达人 →
                          </button>
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            @click="drillToTkCreatorTasks(r.shop_external_id)"
                          >
                            达人异常
                          </button>
                        </div>
                      </td>
                      <td>{{ fmtNum(r.gmv) }}</td>
                      <td>{{ fmtNum(r.orders_cnt, 0) }}</td>
                      <td>{{ fmtNum(r.ad_spend) }}</td>
                      <td>{{ fmtRoi(r.ad_roi) }}</td>
                      <td>{{ r.health_score != null ? fmtNum(r.health_score, 1) : '—' }}</td>
                      <td>
                        <span class="badge" :class="r.data_source === 'shop_daily' ? 'resolved' : 'open'">
                          {{ r.data_source === 'shop_daily' ? '真店日' : '广告估' }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="card-head">
                <h2>商品销量排行 TOP</h2>
                <span class="muted" style="font-size: 12px">
                  fact_tiktok_product.sales_qty ·
                  {{ tkProductRankSummary.product_count || 0 }} 有销量 ·
                  {{ tkProductRankSummary.note || '快照非日 GMV' }}
                </span>
              </div>
              <div class="actions" style="margin-bottom: 8px">
                <button class="btn" :disabled="tkProductRankLoading" @click="loadTkProductRanking">
                  {{ tkProductRankLoading ? '加载中…' : '刷新排行' }}
                </button>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>店铺</th>
                      <th>商品</th>
                      <th>销量</th>
                      <th>库存</th>
                      <th>标价</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkProductRankLoading && !tkProductRankItems.length">
                      <td colspan="7" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkProductRankItems.length">
                      <td colspan="7" class="muted">暂无带销量的商品快照</td>
                    </tr>
                    <tr v-for="r in tkProductRankItems" :key="r.id || (r.shop_external_id + r.product_id)">
                      <td class="mono">{{ r.rank }}</td>
                      <td>{{ r.shop_name || r.shop_external_id || '—' }}</td>
                      <td>
                        {{ r.product_name || r.product_id || '—' }}
                        <div class="muted mono" style="font-size: 11px">{{ r.product_id }}</div>
                      </td>
                      <td>{{ fmtNum(r.sales_qty, 0) }}</td>
                      <td>{{ r.stock_qty != null ? fmtNum(r.stock_qty, 0) : '—' }}</td>
                      <td>
                        {{ r.price != null ? fmtNum(r.price) : '—' }}
                        <span class="muted" style="font-size: 11px">{{ r.currency || '' }}</span>
                      </td>
                      <td>{{ r.status || '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>

          <div class="dash-grid">
            <div class="card">
              <h2>本平台店铺</h2>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>名称</th>
                      <th>外部ID</th>
                      <th>币种</th>
                      <th>状态</th>
                      <th v-if="activePlatformKey === 'tiktok'">下钻</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!platformScopedShops.length">
                      <td :colspan="activePlatformKey === 'tiktok' ? 5 : 4" class="muted">暂无该平台店铺</td>
                    </tr>
                    <tr v-for="s in platformScopedShops" :key="s.id">
                      <td>{{ s.name }}</td>
                      <td class="mono">{{ s.external_shop_id }}</td>
                      <td>{{ s.currency }}</td>
                      <td>{{ s.status }}</td>
                      <td v-if="activePlatformKey === 'tiktok'">
                        <div class="actions" style="gap: 4px">
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            @click="drillToTkAffiliate(s.external_shop_id)"
                          >
                            达人
                          </button>
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            @click="drillToTkCreatorTasks(s.external_shop_id)"
                          >
                            异常
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card">
              <div class="card-head">
                <h2>本平台最近异常</h2>
                <button class="btn btn-ghost" @click="openGlobalTasks(activePlatformKey)">全部 →</button>
              </div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>状态</th><th>异常</th><th>标题</th><th>更新</th></tr></thead>
                  <tbody>
                    <tr v-if="!platformScopedTasks.length"><td colspan="4" class="muted">暂无异常</td></tr>
                    <tr v-for="t in platformScopedTasks.slice(0, 6)" :key="t.id">
                      <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                      <td class="mono">{{ t.anomaly_type }}</td>
                      <td>{{ t.title }}</td>
                      <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <!-- AMZ 补货 -->
        <section v-show="activeTab === 'amz-replenish'">
          <div class="card plan-card">
            <span class="phase-tag">Phase2 · 规划中</span>
            <h2 style="margin-top: 8px">补货审批</h2>
            <div class="pipeline" style="margin-top: 14px">
              <div class="pipe-step"><div class="pipe-num">1</div><div><div class="pipe-title">助理发起</div><div class="muted">唐丹 / 其他运营</div></div></div>
              <div class="pipe-step"><div class="pipe-num">2</div><div><div class="pipe-title">终审</div><div class="muted">李瑾</div></div></div>
              <div class="pipe-step"><div class="pipe-num">3</div><div><div class="pipe-title">通过 / 驳回</div><div class="muted">通知发起人</div></div></div>
              <div class="pipe-step"><div class="pipe-num">4</div><div><div class="pipe-title">执行跟踪</div><div class="muted">可关联采购任务</div></div></div>
            </div>
            <ul class="hint-list" style="margin-top: 14px">
              <li>状态机：draft → pending_review → approved / rejected</li>
              <li>字段：ASIN/链接、建议量、库存、销售天数、备注</li>
            </ul>
          </div>
        </section>

        <!-- AMZ 环比异常 / Temu 健康 任务表 -->
        <section v-show="activeTab === 'amz-anomaly' || activeTab === 'temu-health'">
          <div class="card" style="margin-bottom: 16px">
            <p class="muted" style="margin: 0; font-size: 13px; line-height: 1.6">
              <template v-if="activeTab === 'amz-anomaly'">
                赛狐链接日/周/月环比异常 → 人维任务 → 第一负责人填运营动作直至闭环。默认筛选 Amazon。
              </template>
              <template v-else>
                在售/流量/下架点名异常进入统一任务引擎。默认筛选 Temu。
              </template>
            </p>
          </div>
          <div class="card">
            <div class="row" style="margin-bottom: 12px">
              <label class="field">
                状态
                <select v-model="filters.status" @change="onFilterChange">
                  <option value="">全部</option>
                  <option value="open">待处理</option>
                  <option value="in_progress">进行中</option>
                  <option value="resolved">已闭环</option>
                </select>
              </label>
              <div class="muted grow">platform = {{ filters.platform || '—' }}</div>
              <button v-if="activeTab === 'temu-health'" class="btn" @click="goPlatformAi('temu-health')">AI 健康周报</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>状态</th><th>异常</th><th>业务ID</th><th>标题</th><th>进度</th><th>更新</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!tasks.length"><td colspan="7" class="muted">暂无任务</td></tr>
                  <tr v-for="t in tasks" :key="t.id">
                    <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                    <td class="mono">{{ t.anomaly_type }}</td>
                    <td class="mono">{{ t.biz_id }}</td>
                    <td>{{ t.title }}</td>
                    <td>{{ t.progress_note || '—' }}</td>
                    <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                    <td>
                      <div v-if="t.status !== 'resolved' && t.status !== 'cancelled'" class="actions">
                        <button class="btn btn-ghost" @click="openProgress(t)">进度</button>
                        <button class="btn btn-danger" @click="openResolve(t)">闭环</button>
                      </div>
                      <span v-else class="muted">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- AMZ 巡店 -->
        <section v-show="activeTab === 'amz-patrol'">
          <div class="card plan-card" style="margin-bottom: 16px">
            <span class="phase-tag">Phase2 · 规划中</span>
            <h2 style="margin-top: 8px">巡店链路</h2>
            <p class="muted plan-p">检查店铺异常 → <strong>插件 → 飞书 → 任务</strong>；仅异常建单，正常静默。对齐前台 12 项 + 赛狐绩效。</p>
          </div>
          <div class="plugin-grid">
            <div
              v-for="p in plugins.filter((x) => x.platformKey === 'amazon' || x.platformKey === 'common')"
              :key="p.id"
              class="card plugin-card"
            >
              <div class="plugin-head">
                <div>
                  <div class="plugin-name">{{ p.name }}</div>
                  <div class="muted">{{ p.kind }}</div>
                </div>
                <span class="badge-status" :class="p.statusClass">{{ p.status }}</span>
              </div>
              <p class="plugin-desc">{{ p.desc }}</p>
              <div class="mono muted">{{ p.path }}</div>
            </div>
          </div>
        </section>

        <!-- TK 广告投流（真实对接 fact_ads_campaign_daily） -->
        <section v-show="activeTab === 'tk-ads'">
          <div class="grid-stats">
            <div class="stat accent">
              <div class="label">业务日</div>
              <div class="value" style="font-size: 20px">{{ tkAdsBizDate || '—' }}</div>
            </div>
            <div class="stat">
              <div class="label">总花费</div>
              <div class="value">{{ fmtNum(tkAdsSummary.spend) }}</div>
            </div>
            <div class="stat">
              <div class="label">订单 / 收入</div>
              <div class="value" style="font-size: 18px">
                {{ fmtNum(tkAdsSummary.orders, 0) }}
                <span class="muted" style="font-size: 13px; font-weight: 400">
                  / {{ fmtNum(tkAdsSummary.revenue) }}
                </span>
              </div>
            </div>
            <div class="stat">
              <div class="label">综合 ROI</div>
              <div class="value">{{ fmtRoi(tkAdsSummary.roi) }}</div>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <h2 style="margin: 0">广告系列日明细</h2>
              <span class="muted">
                tk.fact_ads_campaign_daily · 本页异常标记
                {{ tkAdsSummary.open_anomaly_rows || 0 }} 条
              </span>
            </div>
            <p class="muted plan-p" style="margin-top: 0">
              红标 = 未闭环广告异常（ROI/空耗/预算将尽/高CPA）。采集入库后会自动扫规则；也可手动预览/写入。
            </p>
            <div class="actions" style="margin-bottom: 12px">
              <button
                class="btn"
                :disabled="tkAdsEvalLoading || tkAdsLoading"
                @click="runTkAdsAnomalyEval(true, true)"
              >
                {{ tkAdsEvalLoading ? '扫描中…' : '预览广告异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkAdsEvalLoading || tkAdsLoading"
                @click="runTkAdsAnomalyEval(false, true)"
              >
                {{ tkAdsEvalLoading ? '写入中…' : '扫描并写入广告异常' }}
              </button>
              <button class="btn" @click="goPlatformAi('tk-ads')">TK 投流简报</button>
              <button class="btn" @click="switchTab('tk-tasks')">异常任务</button>
              <button class="btn" @click="switchTab('plugins')">插件中心</button>
            </div>
            <div
              v-if="tkAdsEvalMsg"
              class="muted"
              style="margin: -4px 0 12px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkAdsEvalMsg }}
            </div>
            <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
              <label class="field">
                业务日
                <select v-model="tkAdsFilters.biz_date" @change="onTkAdsFilterChange">
                  <option v-if="!tkAdsAvailableDates.length" value="">最新</option>
                  <option
                    v-for="d in tkAdsAvailableDates"
                    :key="d.d"
                    :value="d.d"
                  >
                    {{ d.d }}（{{ d.cnt }}）
                  </option>
                </select>
              </label>
              <label class="field">
                店铺
                <select v-model="tkAdsFilters.shop_external_id" @change="onTkAdsFilterChange">
                  <option value="">全部</option>
                  <option
                    v-for="s in tkShops"
                    :key="s.id"
                    :value="s.external_shop_id"
                  >
                    {{ s.name }}
                  </option>
                </select>
              </label>
              <label class="field grow">
                搜索
                <input
                  v-model="tkAdsFilters.q"
                  placeholder="系列名 / 店铺"
                  @keyup.enter="onTkAdsFilterChange"
                />
              </label>
              <button class="btn" :disabled="tkAdsLoading" @click="loadTkAds">
                {{ tkAdsLoading ? '加载中…' : '刷新' }}
              </button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>异常</th>
                    <th>店铺</th>
                    <th>系列</th>
                    <th>花费</th>
                    <th>订单</th>
                    <th>收入</th>
                    <th>ROI</th>
                    <th>目标ROI</th>
                    <th>日预算</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="tkAdsLoading && !tkAdsItems.length">
                    <td colspan="10" class="muted">加载中…</td>
                  </tr>
                  <tr v-else-if="!tkAdsItems.length">
                    <td colspan="10" class="muted">
                      暂无广告日数据（先跑采集插件，或确认业务日筛选）
                    </td>
                  </tr>
                  <tr
                    v-for="r in tkAdsItems"
                    :key="r.id"
                    :class="{ 'row-alert': r.has_open_anomaly }"
                  >
                    <td>
                      <template v-if="r.has_open_anomaly">
                        <span
                          v-for="c in r.open_anomaly_codes"
                          :key="c"
                          class="chip"
                          :class="c === 'ads_spend_no_sale' ? 'pri-p0' : 'pri-p1'"
                          style="margin: 0 4px 4px 0"
                        >
                          {{ anomalyCodeLabel(c) }}
                        </span>
                      </template>
                      <span v-else class="muted">—</span>
                    </td>
                    <td>{{ r.shop_name || r.shop_external_id || '—' }}</td>
                    <td>
                      <div>{{ r.campaign_name }}</div>
                      <div v-if="r.source_url" class="mono muted" style="font-size: 11px">
                        <a :href="r.source_url" target="_blank" rel="noopener">源链接</a>
                      </div>
                    </td>
                    <td class="mono">{{ fmtNum(r.spend) }}</td>
                    <td class="mono">{{ fmtNum(r.orders, 0) }}</td>
                    <td class="mono">{{ fmtNum(r.revenue) }}</td>
                    <td class="mono">{{ fmtRoi(r.roi) }}</td>
                    <td class="mono">{{ fmtRoi(r.target_roi) }}</td>
                    <td class="mono">{{ fmtNum(r.daily_budget) }}</td>
                    <td class="muted" style="font-size: 12px">
                      {{ r.plan_status || '—' }}
                      <span v-if="r.delivery_status"> / {{ r.delivery_status }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="row" style="margin-top: 12px; justify-content: space-between">
              <div class="muted">共 {{ tkAdsTotal }} 条 · 第 {{ tkAdsFilters.page }} 页</div>
              <div class="actions">
                <button
                  class="btn"
                  :disabled="tkAdsFilters.page <= 1 || tkAdsLoading"
                  @click="tkAdsFilters.page -= 1; loadTkAds()"
                >
                  上一页
                </button>
                <button
                  class="btn"
                  :disabled="tkAdsFilters.page * tkAdsFilters.page_size >= tkAdsTotal || tkAdsLoading"
                  @click="tkAdsFilters.page += 1; loadTkAds()"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- TK 内容分析（P2.5）：视频 content_daily + 商品卡 traffic -->
        <section v-show="activeTab === 'tk-content'">
          <div class="card" style="margin-bottom: 12px">
            <div class="card-head">
              <h2 style="margin: 0">内容分析 · ② 视频 / 商品卡</h2>
              <span class="muted" style="font-size: 12px">
                窗口快照 · 非日均摊 · 锚点日内汇总 · 混币勿加总 GMV
              </span>
            </div>
            <p class="muted plan-p" style="margin-top: 0">
              数据源：<code>fact_tiktok_content_daily</code>（视频归因）与
              <code>fact_tiktok_product_traffic_daily</code>（商品卡 CTR/CVR）。
              「日期」= 窗口锚点，不是把近 7 天拆成 7 行。异常域「视频内容」：归因 GMV 骤降 / 播放曝光崩 / 有曝无单。
            </p>
            <div class="actions" style="margin-bottom: 8px; flex-wrap: wrap">
              <button
                class="btn"
                :class="tkContentPane === 'video' ? 'btn-primary' : ''"
                @click="tkContentPane = 'video'"
              >
                视频内容
              </button>
              <button
                class="btn"
                :class="tkContentPane === 'traffic' ? 'btn-primary' : ''"
                @click="tkContentPane = 'traffic'"
              >
                商品卡流量
              </button>
              <button
                class="btn"
                :disabled="tkContentEvalLoading || loading"
                @click="runTkContentAnomalyEval(true)"
              >
                {{ tkContentEvalLoading ? '扫描中…' : '预览视频异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkContentEvalLoading || loading"
                @click="runTkContentAnomalyEval(false)"
              >
                {{ tkContentEvalLoading ? '写入中…' : '扫描并写入视频异常' }}
              </button>
              <button class="btn" @click="switchTab('tk-tasks'); tkFilters.object_type = 'content'; onTkFilterChange()">
                异常 · 视频内容
              </button>
            </div>
            <div
              v-if="tkContentEvalMsg"
              class="muted"
              style="margin: 0 0 8px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkContentEvalMsg }}
            </div>
          </div>

          <!-- 视频内容 -->
          <template v-if="tkContentPane === 'video'">
            <div class="grid-stats">
              <div class="stat accent">
                <div class="label">归因 GMV（锚点窗）</div>
                <div class="value">{{ fmtNum(tkContentSummary.attributed_gmv_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">播放 / 曝光</div>
                <div class="value" style="font-size: 16px">
                  {{ fmtNum(tkContentSummary.play_count_sum, 0) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    / {{ fmtNum(tkContentSummary.impressions_sum, 0) }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">归因订单 · 视频数</div>
                <div class="value" style="font-size: 16px">
                  {{ fmtNum(tkContentSummary.attributed_sku_orders_sum, 0) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkContentSummary.content_count || 0 }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">锚点日 / 店数</div>
                <div class="value" style="font-size: 16px">
                  {{ tkContentBizDate || '—' }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkContentSummary.shop_count || 0 }}
                  </span>
                </div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
                <label class="field">
                  锚点日
                  <select v-model="tkContentFilters.biz_date" @change="onTkContentFilterChange">
                    <option v-if="!tkContentAvailableDates.length" value="">最新</option>
                    <option v-for="d in tkContentAvailableDates" :key="d" :value="d">{{ d }}</option>
                  </select>
                </label>
                <label class="field">
                  店铺
                  <select v-model="tkContentFilters.shop_external_id" @change="onTkContentFilterChange">
                    <option value="">全部</option>
                    <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">{{ s.name }}</option>
                  </select>
                </label>
                <label class="field">
                  渠道
                  <select v-model="tkContentFilters.channel" @change="onTkContentFilterChange">
                    <option value="short_video">短视频</option>
                    <option value="live">直播</option>
                    <option value="photo">照片</option>
                    <option value="">全部</option>
                  </select>
                </label>
                <label class="field">
                  排序
                  <select v-model="tkContentFilters.order_by" @change="onTkContentFilterChange">
                    <option value="attributed_gmv">归因 GMV</option>
                    <option value="play_count">播放量</option>
                    <option value="impressions">曝光</option>
                    <option value="attributed_sku_orders">归因订单</option>
                    <option value="cvr">CVR</option>
                  </select>
                </label>
                <button class="btn" :disabled="tkContentLoading" @click="loadTkContent">
                  {{ tkContentLoading ? '加载中…' : '刷新' }}
                </button>
              </div>
              <p v-if="tkContentSummary.note" class="muted" style="margin: -4px 0 10px; font-size: 12px">
                {{ tkContentSummary.note }}
              </p>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>视频</th>
                      <th>窗口</th>
                      <th>归因GMV</th>
                      <th>归因订单</th>
                      <th>播放</th>
                      <th>曝光</th>
                      <th>点击</th>
                      <th>CTR</th>
                      <th>CVR</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkContentLoading && !tkContentItems.length">
                      <td colspan="10" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkContentItems.length">
                      <td colspan="10" class="muted">
                        暂无内容日数据（先跑 video-details 采集 / content ingest，或换锚点日）
                      </td>
                    </tr>
                    <tr v-for="r in tkContentItems" :key="r.id || (r.content_id + r.biz_date)">
                      <td>
                        {{ r.shop_name || r.shop_external_id || '—' }}
                      </td>
                      <td>
                        <div>{{ r.content_title || r.content_id || '—' }}</div>
                        <div class="mono muted" style="font-size: 11px">{{ r.content_id }}</div>
                        <div v-if="r.product_id" class="muted" style="font-size: 11px">商品 {{ r.product_id }}</div>
                      </td>
                      <td class="muted" style="font-size: 12px">{{ r.window || '—' }}</td>
                      <td class="mono">
                        {{ fmtNum(r.attributed_gmv) }}
                        <span class="muted" style="font-size: 11px">{{ r.currency || '' }}</span>
                      </td>
                      <td class="mono">{{ fmtNum(r.attributed_sku_orders, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.play_count, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.impressions, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.clicks, 0) }}</td>
                      <td class="mono">{{ r.ctr != null ? fmtNum(r.ctr, 4) : '—' }}</td>
                      <td class="mono">{{ r.cvr != null ? fmtNum(r.cvr, 4) : '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="row" style="margin-top: 12px; justify-content: space-between">
                <div class="muted">共 {{ tkContentTotal }} 条 · 第 {{ tkContentFilters.page }} 页</div>
                <div class="actions">
                  <button
                    class="btn"
                    :disabled="tkContentFilters.page <= 1 || tkContentLoading"
                    @click="tkContentFilters.page -= 1; loadTkContent()"
                  >
                    上一页
                  </button>
                  <button
                    class="btn"
                    :disabled="tkContentFilters.page * tkContentFilters.page_size >= tkContentTotal || tkContentLoading"
                    @click="tkContentFilters.page += 1; loadTkContent()"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </template>

          <!-- 商品卡流量 / 多渠道 -->
          <template v-else>
            <div class="grid-stats">
              <div class="stat accent">
                <div class="label">商品 GMV（锚点窗）</div>
                <div class="value">{{ fmtNum(tkTrafficSummary.gmv_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">曝光合计</div>
                <div class="value">{{ fmtNum(tkTrafficSummary.impressions_sum, 0) }}</div>
              </div>
              <div class="stat">
                <div class="label">订单 · 商品数</div>
                <div class="value" style="font-size: 16px">
                  {{ fmtNum(tkTrafficSummary.orders_sum, 0) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkTrafficSummary.product_count || 0 }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">锚点日 / 渠道数(本页)</div>
                <div class="value" style="font-size: 16px">
                  {{ tkTrafficBizDate || '—' }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkTrafficChannelKeys.length }}
                  </span>
                </div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
                <label class="field">
                  锚点日
                  <select v-model="tkTrafficFilters.biz_date" @change="onTkTrafficFilterChange">
                    <option v-if="!tkTrafficAvailableDates.length" value="">最新</option>
                    <option v-for="d in tkTrafficAvailableDates" :key="d" :value="d">{{ d }}</option>
                  </select>
                </label>
                <label class="field">
                  店铺
                  <select v-model="tkTrafficFilters.shop_external_id" @change="onTkTrafficFilterChange">
                    <option value="">全部</option>
                    <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">{{ s.name }}</option>
                  </select>
                </label>
                <label class="field">
                  渠道
                  <select v-model="tkTrafficFilters.channel" @change="onTkTrafficFilterChange">
                    <option value="">全部（对比）</option>
                    <option value="product_card">商品卡</option>
                    <option value="ads_link">广告链</option>
                    <option value="short_video">短视频</option>
                    <option value="live">直播</option>
                    <option value="other">其他</option>
                  </select>
                </label>
                <label class="field">
                  排序
                  <select v-model="tkTrafficFilters.order_by" @change="onTkTrafficFilterChange">
                    <option value="gmv">GMV</option>
                    <option value="impressions">曝光</option>
                    <option value="cvr">CVR</option>
                    <option value="orders_cnt">订单</option>
                  </select>
                </label>
                <button class="btn" :disabled="tkTrafficLoading" @click="loadTkTraffic">
                  {{ tkTrafficLoading ? '加载中…' : '刷新' }}
                </button>
              </div>
              <p v-if="tkTrafficSummary.note" class="muted" style="margin: -4px 0 10px; font-size: 12px">
                {{ tkTrafficSummary.note }}
              </p>

              <h3 style="margin: 0 0 8px; font-size: 14px">多渠道 CTR/CVR 对比（当前页按商品聚合）</h3>
              <p class="muted" style="margin: 0 0 8px; font-size: 12px">
                同一商品出现 ≥2 渠道时横向对比；当前仅有单渠道数据时仍展示一行。有数渠道：
                {{ tkTrafficChannelKeys.join(' / ') || '—' }}
              </p>
              <div class="table-wrap" style="margin-bottom: 16px">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>商品</th>
                      <th v-for="ch in tkTrafficChannelKeys" :key="'h-' + ch">{{ ch }} · 曝/CTR/CVR/GMV</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkTrafficLoading && !tkTrafficChannelCompare.length">
                      <td :colspan="2 + Math.max(tkTrafficChannelKeys.length, 1)" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkTrafficChannelCompare.length">
                      <td :colspan="2 + Math.max(tkTrafficChannelKeys.length, 1)" class="muted">
                        暂无商品卡流量（跑 product_traffic 采集后刷新）
                      </td>
                    </tr>
                    <tr v-for="row in tkTrafficChannelCompare" :key="row.product_id">
                      <td>{{ row.shop_name }}</td>
                      <td>
                        {{ row.product_name }}
                        <div class="mono muted" style="font-size: 11px">{{ row.product_id }}</div>
                      </td>
                      <td v-for="ch in tkTrafficChannelKeys" :key="row.product_id + ch" class="mono" style="font-size: 12px">
                        <template v-if="row.channels[ch]">
                          {{ fmtNum(row.channels[ch].impressions, 0) }}
                          /
                          {{ row.channels[ch].ctr != null ? fmtNum(row.channels[ch].ctr, 4) : '—' }}
                          /
                          {{ row.channels[ch].cvr != null ? fmtNum(row.channels[ch].cvr, 4) : '—' }}
                          /
                          {{ fmtNum(row.channels[ch].gmv) }}
                        </template>
                        <span v-else class="muted">—</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3 style="margin: 0 0 8px; font-size: 14px">明细行</h3>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>商品</th>
                      <th>渠道</th>
                      <th>窗口</th>
                      <th>曝光</th>
                      <th>点击</th>
                      <th>CTR</th>
                      <th>订单</th>
                      <th>GMV</th>
                      <th>CVR</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkTrafficLoading && !tkTrafficItems.length">
                      <td colspan="10" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkTrafficItems.length">
                      <td colspan="10" class="muted">暂无行</td>
                    </tr>
                    <tr v-for="r in tkTrafficItems" :key="r.id || (r.product_id + r.channel + r.biz_date)">
                      <td>{{ r.shop_name || r.shop_external_id || '—' }}</td>
                      <td>
                        {{ r.product_name || r.product_id || '—' }}
                        <div class="mono muted" style="font-size: 11px">{{ r.product_id }}</div>
                      </td>
                      <td><span class="badge open">{{ r.channel || '—' }}</span></td>
                      <td class="muted" style="font-size: 12px">{{ r.window || '—' }}</td>
                      <td class="mono">{{ fmtNum(r.impressions, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.clicks, 0) }}</td>
                      <td class="mono">{{ r.ctr != null ? fmtNum(r.ctr, 4) : '—' }}</td>
                      <td class="mono">{{ fmtNum(r.orders_cnt, 0) }}</td>
                      <td class="mono">
                        {{ fmtNum(r.gmv) }}
                        <span class="muted" style="font-size: 11px">{{ r.currency || '' }}</span>
                      </td>
                      <td class="mono">{{ r.cvr != null ? fmtNum(r.cvr, 4) : '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="row" style="margin-top: 12px; justify-content: space-between">
                <div class="muted">共 {{ tkTrafficTotal }} 条 · 第 {{ tkTrafficFilters.page }} 页</div>
                <div class="actions">
                  <button
                    class="btn"
                    :disabled="tkTrafficFilters.page <= 1 || tkTrafficLoading"
                    @click="tkTrafficFilters.page -= 1; loadTkTraffic()"
                  >
                    上一页
                  </button>
                  <button
                    class="btn"
                    :disabled="tkTrafficFilters.page * tkTrafficFilters.page_size >= tkTrafficTotal || tkTrafficLoading"
                    @click="tkTrafficFilters.page += 1; loadTkTraffic()"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </template>
        </section>

        <!-- TK 达人表现（P3.2）：联盟 creator_daily + shop affiliate_daily -->
        <section v-show="activeTab === 'tk-affiliate'">
          <div class="card" style="margin-bottom: 12px">
            <div class="card-head">
              <h2 style="margin: 0">达人表现 · ③ 联盟中心</h2>
              <span class="muted" style="font-size: 12px">
                窗口快照 · 近7天不拆日 · creator_id=handle · 投入仅预计佣金
              </span>
            </div>
            <p class="muted plan-p" style="margin-top: 0">
              数据源：<code>fact_tiktok_affiliate_creator_daily</code>（达人行）与
              <code>fact_tiktok_affiliate_daily</code>（店级 KPI）。
              「是否出单」= 归因GMV&gt;0 或 成交件&gt;0。投流/寄样金额暂不采，界面不填 0。
              飞书 T7「达人日」由 PG 同步。规则：有投入无成交 / 归因GMV骤降 / 动销达人降 / 退款异常（object_type=creator）。
              <strong>分盘：</strong>达人归因 GMV ≠ 店日 GMV ≠ 广告花费，禁止混加（见 docs/TK-P3-分盘与口径.md）。
            </p>
            <div class="actions" style="margin-bottom: 8px; flex-wrap: wrap">
              <button
                class="btn"
                :class="tkAffiliatePane === 'creator' ? 'btn-primary' : ''"
                @click="tkAffiliatePane = 'creator'"
              >
                达人明细
              </button>
              <button
                class="btn"
                :class="tkAffiliatePane === 'shop' ? 'btn-primary' : ''"
                @click="tkAffiliatePane = 'shop'"
              >
                店级汇总
              </button>
              <button
                class="btn"
                :disabled="tkAffiliateEvalLoading || loading"
                @click="runTkAffiliateAnomalyEval(true)"
              >
                {{ tkAffiliateEvalLoading ? '扫描中…' : '预览达人异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkAffiliateEvalLoading || loading"
                @click="runTkAffiliateAnomalyEval(false)"
              >
                {{ tkAffiliateEvalLoading ? '写入中…' : '扫描并写入达人异常' }}
              </button>
              <button
                class="btn"
                @click="switchTab('tk-tasks'); tkFilters.object_type = 'creator'; onTkFilterChange()"
              >
                达人异常任务
              </button>
            </div>
            <div
              v-if="tkAffiliateEvalMsg"
              class="muted"
              style="margin: 0 0 8px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkAffiliateEvalMsg }}
            </div>
          </div>

          <template v-if="tkAffiliatePane === 'creator'">
            <div class="grid-stats">
              <div class="stat accent">
                <div class="label">归因 GMV（锚点窗）</div>
                <div class="value">{{ fmtNum(tkAffiliateSummary.gmv_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">预计佣金</div>
                <div class="value">{{ fmtNum(tkAffiliateSummary.est_commission_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">出单 / 达人数</div>
                <div class="value" style="font-size: 16px">
                  {{ tkAffiliateSummary.sold_creator_count || 0 }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    / {{ tkAffiliateSummary.creator_count || 0 }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">锚点日 / 店数</div>
                <div class="value" style="font-size: 16px">
                  {{ tkAffiliateBizDate || '—' }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkAffiliateSummary.shop_count || 0 }}
                  </span>
                </div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
                <label class="field">
                  锚点日
                  <select v-model="tkAffiliateFilters.biz_date" @change="onTkAffiliateFilterChange">
                    <option v-if="!tkAffiliateAvailableDates.length" value="">最新</option>
                    <option v-for="d in tkAffiliateAvailableDates" :key="d" :value="d">{{ d }}</option>
                  </select>
                </label>
                <label class="field">
                  店铺
                  <select
                    v-model="tkAffiliateFilters.shop_external_id"
                    @change="onTkAffiliateFilterChange"
                  >
                    <option value="">全部</option>
                    <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">
                      {{ s.name }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  排序
                  <select v-model="tkAffiliateFilters.order_by" @change="onTkAffiliateFilterChange">
                    <option value="gmv">归因 GMV</option>
                    <option value="order_units">成交件数</option>
                    <option value="est_commission">预计佣金</option>
                    <option value="video_views">视频播放</option>
                    <option value="orders_cnt">订单数</option>
                  </select>
                </label>
                <label class="field" style="min-width: auto; justify-content: flex-end">
                  <span class="muted" style="margin-bottom: 6px">仅已出单</span>
                  <input
                    v-model="tkAffiliateFilters.sold_only"
                    type="checkbox"
                    @change="onTkAffiliateFilterChange"
                  />
                </label>
                <button class="btn" :disabled="tkAffiliateLoading" @click="loadTkAffiliate">
                  {{ tkAffiliateLoading ? '加载中…' : '刷新' }}
                </button>
              </div>
              <p v-if="tkAffiliateSummary.note" class="muted" style="margin: -4px 0 10px; font-size: 12px">
                {{ tkAffiliateSummary.note }}
              </p>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>达人</th>
                      <th>窗口</th>
                      <th>出单</th>
                      <th>归因GMV</th>
                      <th>成交件</th>
                      <th>订单</th>
                      <th>预计佣金</th>
                      <th>视频/直播</th>
                      <th>播放</th>
                      <th>样品发货</th>
                      <th>下钻</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkAffiliateLoading && !tkAffiliateItems.length">
                      <td colspan="12" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkAffiliateItems.length">
                      <td colspan="12" class="muted">
                        暂无达人数据（先跑 run-affiliate-poc.ps1 -SkipIngest:$false，或换锚点日）
                      </td>
                    </tr>
                    <tr
                      v-for="r in tkAffiliateItems"
                      :key="r.id || (r.creator_id + r.biz_date + r.shop_external_id)"
                    >
                      <td>{{ r.shop_name || r.shop_external_id || '—' }}</td>
                      <td>
                        <div>{{ r.creator_name || r.creator_handle || r.creator_id || '—' }}</div>
                        <div class="mono muted" style="font-size: 11px">
                          {{ r.creator_handle || r.creator_id }}
                        </div>
                      </td>
                      <td class="muted" style="font-size: 12px">{{ r.window_label || '—' }}</td>
                      <td>
                        <span :class="r.sold_flag ? 'tag ok' : 'tag muted'">
                          {{ r.sold_flag ? '是' : '否' }}
                        </span>
                      </td>
                      <td class="mono">
                        {{ fmtNum(r.gmv) }}
                        <span class="muted" style="font-size: 11px">{{ r.currency || '' }}</span>
                      </td>
                      <td class="mono">{{ fmtNum(r.order_units, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.orders_cnt, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.est_commission) }}</td>
                      <td class="mono">
                        {{ fmtNum(r.video_cnt, 0) }}
                        <span class="muted">/</span>
                        {{ fmtNum(r.live_cnt, 0) }}
                      </td>
                      <td class="mono">{{ fmtNum(r.video_views, 0) }}</td>
                      <td class="mono">
                        {{ r.samples_shipped != null ? fmtNum(r.samples_shipped, 0) : '—' }}
                      </td>
                      <td>
                        <button
                          type="button"
                          class="btn btn-ghost"
                          style="font-size: 11px; padding: 2px 6px"
                          title="查看该店达人表现异常"
                          @click="drillToTkCreatorTasks(r.shop_external_id)"
                        >
                          异常
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="row" style="margin-top: 12px; justify-content: space-between">
                <div class="muted">
                  共 {{ tkAffiliateTotal }} 条 · 第 {{ tkAffiliateFilters.page }} 页
                </div>
                <div class="actions">
                  <button
                    class="btn"
                    :disabled="tkAffiliateFilters.page <= 1 || tkAffiliateLoading"
                    @click="tkAffiliateFilters.page -= 1; loadTkAffiliate()"
                  >
                    上一页
                  </button>
                  <button
                    class="btn"
                    :disabled="
                      tkAffiliateFilters.page * tkAffiliateFilters.page_size >= tkAffiliateTotal ||
                      tkAffiliateLoading
                    "
                    @click="tkAffiliateFilters.page += 1; loadTkAffiliate()"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="grid-stats">
              <div class="stat accent">
                <div class="label">店级联盟 GMV</div>
                <div class="value">{{ fmtNum(tkAffiliateShopSummary.gmv_affiliate_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">预计佣金</div>
                <div class="value">{{ fmtNum(tkAffiliateShopSummary.est_commission_sum) }}</div>
              </div>
              <div class="stat">
                <div class="label">动销 / 发布达人</div>
                <div class="value" style="font-size: 16px">
                  {{ fmtNum(tkAffiliateShopSummary.creators_sold_sum, 0) }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    / {{ fmtNum(tkAffiliateShopSummary.creators_published_sum, 0) }}
                  </span>
                </div>
              </div>
              <div class="stat">
                <div class="label">锚点日 / 店数</div>
                <div class="value" style="font-size: 16px">
                  {{ tkAffiliateShopBizDate || '—' }}
                  <span class="muted" style="font-size: 12px; font-weight: 500">
                    · {{ tkAffiliateShopSummary.shop_count || 0 }}
                  </span>
                </div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px">
              <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
                <label class="field">
                  锚点日
                  <select
                    v-model="tkAffiliateShopFilters.biz_date"
                    @change="onTkAffiliateShopFilterChange"
                  >
                    <option v-if="!tkAffiliateShopAvailableDates.length" value="">最新</option>
                    <option v-for="d in tkAffiliateShopAvailableDates" :key="d" :value="d">
                      {{ d }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  店铺
                  <select
                    v-model="tkAffiliateShopFilters.shop_external_id"
                    @change="onTkAffiliateShopFilterChange"
                  >
                    <option value="">全部</option>
                    <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">
                      {{ s.name }}
                    </option>
                  </select>
                </label>
                <button class="btn" :disabled="tkAffiliateShopLoading" @click="loadTkAffiliateShop">
                  {{ tkAffiliateShopLoading ? '加载中…' : '刷新' }}
                </button>
              </div>
              <p
                v-if="tkAffiliateShopSummary.note"
                class="muted"
                style="margin: -4px 0 10px; font-size: 12px"
              >
                {{ tkAffiliateShopSummary.note }}
              </p>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>店铺</th>
                      <th>窗口</th>
                      <th>联盟GMV</th>
                      <th>成交件</th>
                      <th>预计佣金</th>
                      <th>动销达人</th>
                      <th>发布达人</th>
                      <th>视频/直播</th>
                      <th>退款</th>
                      <th>下钻</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="tkAffiliateShopLoading && !tkAffiliateShopItems.length">
                      <td colspan="10" class="muted">加载中…</td>
                    </tr>
                    <tr v-else-if="!tkAffiliateShopItems.length">
                      <td colspan="10" class="muted">暂无店级联盟窗数据</td>
                    </tr>
                    <tr
                      v-for="r in tkAffiliateShopItems"
                      :key="r.id || (r.shop_external_id + r.biz_date)"
                    >
                      <td>{{ r.shop_name || r.shop_external_id || '—' }}</td>
                      <td class="muted" style="font-size: 12px">{{ r.window_label || '—' }}</td>
                      <td class="mono">
                        {{ fmtNum(r.gmv_affiliate) }}
                        <span class="muted" style="font-size: 11px">{{ r.currency || '' }}</span>
                      </td>
                      <td class="mono">{{ fmtNum(r.order_units, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.est_commission) }}</td>
                      <td class="mono">{{ fmtNum(r.creators_sold, 0) }}</td>
                      <td class="mono">{{ fmtNum(r.creators_published, 0) }}</td>
                      <td class="mono">
                        {{ fmtNum(r.video_cnt, 0) }}
                        <span class="muted">/</span>
                        {{ fmtNum(r.live_cnt, 0) }}
                      </td>
                      <td class="mono">
                        {{ r.refund_amount != null ? fmtNum(r.refund_amount) : '—' }}
                      </td>
                      <td>
                        <div class="actions" style="gap: 4px">
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            @click="drillToTkAffiliate(r.shop_external_id, { pane: 'creator', biz_date: r.biz_date })"
                          >
                            达人明细
                          </button>
                          <button
                            type="button"
                            class="btn btn-ghost"
                            style="font-size: 11px; padding: 2px 6px"
                            @click="drillToTkCreatorTasks(r.shop_external_id)"
                          >
                            异常
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="row" style="margin-top: 12px; justify-content: space-between">
                <div class="muted">
                  共 {{ tkAffiliateShopTotal }} 条 · 第 {{ tkAffiliateShopFilters.page }} 页
                </div>
                <div class="actions">
                  <button
                    class="btn"
                    :disabled="tkAffiliateShopFilters.page <= 1 || tkAffiliateShopLoading"
                    @click="tkAffiliateShopFilters.page -= 1; loadTkAffiliateShop()"
                  >
                    上一页
                  </button>
                  <button
                    class="btn"
                    :disabled="
                      tkAffiliateShopFilters.page * tkAffiliateShopFilters.page_size >=
                        tkAffiliateShopTotal || tkAffiliateShopLoading
                    "
                    @click="tkAffiliateShopFilters.page += 1; loadTkAffiliateShop()"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </template>
        </section>

        <section v-show="activeTab === 'tk-report'">
          <div class="card">
            <h2>日报 / AI 简报</h2>
            <p class="muted plan-p">总览、分店 KPI、亮点、低 ROI、TOP 系列。</p>
            <div class="actions">
              <button class="btn btn-primary" @click="goPlatformAi('tk-ads')">打开 AI · TK 简报</button>
              <button class="btn" @click="switchTab('tk-ads')">返回广告投流</button>
              <button class="btn" @click="switchTab('tk-content')">内容分析</button>
              <button class="btn" @click="switchTab('tk-affiliate')">达人表现</button>
              <button class="btn" @click="switchTab('tk-tasks')">异常任务</button>
            </div>
          </div>
        </section>

        <!-- TK 异常任务（真实对接 tk.fact_tk_anomaly_task） -->
        <section v-show="activeTab === 'tk-tasks'">
          <div class="grid-stats">
            <div class="stat accent">
              <div class="label">TK 异常总数</div>
              <div class="value">{{ tkStats.total }}</div>
            </div>
            <div class="stat">
              <div class="label">待处理</div>
              <div class="value">{{ tkStats.open }}</div>
            </div>
            <div class="stat">
              <div class="label">进行中</div>
              <div class="value">{{ tkStats.doing }}</div>
            </div>
            <div class="stat">
              <div class="label">已闭环</div>
              <div class="value">{{ tkStats.resolved }}</div>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <h2 style="margin: 0">TK 异常任务</h2>
              <span class="muted">数据源 · tk.fact_tk_anomaly_task</span>
            </div>
            <p class="muted plan-p" style="margin-top: 0">
              对齐飞书「异常任务」：主键 / 日期 / 店铺 / 商品 / 异常类型 / 负责人 / 状态。处置会同步投影到中心任务引擎（若有 center_task_id）。
              广告：ROI 过低 / 空耗 / 预算将尽 / 高 CPA。商品：断货 / 库存不足。店铺分析：GMV/订单骤降。视频内容：归因GMV骤降 / 播放曝光崩 / 有曝无单。达人表现：有投入无成交 / 归因GMV骤降 / 动销达人降 / 退款异常。
              采集入库后自动扫规则；也可下方手动预览/写入。筛选可按「店铺分析 / 广告 / 库存 / 视频内容 / 达人表现」域过滤。
            </p>
            <div class="actions" style="margin-bottom: 12px; flex-wrap: wrap">
              <button
                class="btn"
                :disabled="tkAdsEvalLoading || loading"
                @click="runTkAdsAnomalyEval(true)"
              >
                {{ tkAdsEvalLoading ? '扫描中…' : '预览广告异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkAdsEvalLoading || loading"
                @click="runTkAdsAnomalyEval(false)"
              >
                {{ tkAdsEvalLoading ? '写入中…' : '扫描并写入广告异常' }}
              </button>
              <button
                class="btn"
                :disabled="tkProductEvalLoading || loading"
                @click="runTkProductAnomalyEval(true)"
              >
                {{ tkProductEvalLoading ? '扫描中…' : '预览库存异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkProductEvalLoading || loading"
                @click="runTkProductAnomalyEval(false)"
              >
                {{ tkProductEvalLoading ? '写入中…' : '扫描并写入库存异常' }}
              </button>
              <button
                class="btn"
                :disabled="tkContentEvalLoading || loading"
                @click="runTkContentAnomalyEval(true)"
              >
                {{ tkContentEvalLoading ? '扫描中…' : '预览视频异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkContentEvalLoading || loading"
                @click="runTkContentAnomalyEval(false)"
              >
                {{ tkContentEvalLoading ? '写入中…' : '扫描并写入视频异常' }}
              </button>
              <button
                class="btn"
                :disabled="tkAffiliateEvalLoading || loading"
                @click="runTkAffiliateAnomalyEval(true)"
              >
                {{ tkAffiliateEvalLoading ? '扫描中…' : '预览达人异常' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="tkAffiliateEvalLoading || loading"
                @click="runTkAffiliateAnomalyEval(false)"
              >
                {{ tkAffiliateEvalLoading ? '写入中…' : '扫描并写入达人异常' }}
              </button>
              <span class="muted">广告扫最新业务日；库存扫商品快照；视频/达人扫锚点窗。若选了店铺则只扫该店</span>
            </div>
            <div
              v-if="tkAdsEvalMsg"
              class="muted"
              style="margin: -4px 0 12px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkAdsEvalMsg }}
            </div>
            <div
              v-if="tkProductEvalMsg"
              class="muted"
              style="margin: -4px 0 12px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkProductEvalMsg }}
            </div>
            <div
              v-if="tkContentEvalMsg"
              class="muted"
              style="margin: -4px 0 12px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkContentEvalMsg }}
            </div>
            <div
              v-if="tkAffiliateEvalMsg"
              class="muted"
              style="margin: -4px 0 12px; white-space: pre-wrap; color: var(--ok)"
            >
              {{ tkAffiliateEvalMsg }}
            </div>
            <div class="row" style="margin-bottom: 12px; flex-wrap: wrap; gap: 10px">
              <label class="field">
                状态
                <select v-model="tkFilters.status" @change="onTkFilterChange">
                  <option value="">全部</option>
                  <option value="open">待处理</option>
                  <option value="in_progress">进行中</option>
                  <option value="resolved">已闭环</option>
                  <option value="cancelled">已取消</option>
                  <option value="ignored">已忽略</option>
                </select>
              </label>
              <label class="field">
                优先级
                <select v-model="tkFilters.priority" @change="onTkFilterChange">
                  <option value="">全部</option>
                  <option value="P0">P0</option>
                  <option value="P1">P1</option>
                  <option value="P2">P2</option>
                </select>
              </label>
              <label class="field">
                异常类型
                <select v-model="tkFilters.anomaly_code" @change="onTkFilterChange">
                  <option value="">全部</option>
                  <option v-for="t in tkTypes" :key="t.code" :value="t.code">{{ t.name_cn }}</option>
                </select>
              </label>
              <label class="field">
                分析域
                <select v-model="tkFilters.object_type" @change="onTkFilterChange">
                  <option value="">全部</option>
                  <option value="shop">店铺分析</option>
                  <option value="campaign">广告</option>
                  <option value="product">库存</option>
                  <option value="content">视频内容</option>
                  <option value="creator">达人表现</option>
                </select>
              </label>
              <label class="field">
                店铺
                <select v-model="tkFilters.shop_external_id" @change="onTkFilterChange">
                  <option value="">全部</option>
                  <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">{{ s.name }}</option>
                </select>
              </label>
              <label class="field grow">
                搜索
                <input
                  v-model="tkFilters.q"
                  placeholder="商品 / SKU / 摘要 / 主键"
                  @keyup.enter="onTkFilterChange"
                />
              </label>
              <label class="field" style="min-width: auto; justify-content: flex-end">
                <span class="muted" style="margin-bottom: 6px">仅未闭环</span>
                <input v-model="tkFilters.open_only" type="checkbox" @change="onTkFilterChange" />
              </label>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>等级</th>
                    <th>优先级</th>
                    <th>日期</th>
                    <th>店铺</th>
                    <th>异常</th>
                    <th>对象</th>
                    <th>当前值</th>
                    <th>摘要 / 说明</th>
                    <th>指标</th>
                    <th>负责人</th>
                    <th>更新</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!tkTasks.length">
                    <td colspan="13" class="muted">暂无 TK 异常任务（可点右上角「新建 TK 异常」或等采集/规则写入）</td>
                  </tr>
                  <tr
                    v-for="t in tkTasks"
                    :key="t.id"
                    :class="{ 'row-alert': t.needs_boss_decision || String(t.priority || '').toUpperCase() === 'P0' }"
                  >
                    <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                    <td>
                      <span class="chip" :class="levelClass(t.level_code, t.priority)">
                        {{ levelLabel(t.level_code, t.priority) }}
                      </span>
                      <div
                        v-if="t.needs_boss_decision"
                        class="muted"
                        style="font-size: 11px; color: #b91c1c; font-weight: 600"
                      >
                        待老板决策
                      </div>
                      <div v-else-if="t.streak_count && t.streak_count > 1" class="muted" style="font-size: 11px">
                        连续 {{ t.streak_count }} 次
                      </div>
                    </td>
                    <td>
                      <span class="chip" :class="'pri-' + (t.priority || '').toLowerCase()">{{ priorityLabel(t.priority) }}</span>
                    </td>
                    <td class="mono">{{ t.biz_date || '—' }}</td>
                    <td>{{ t.shop_name || t.shop_external_id || '—' }}</td>
                    <td>
                      <div>{{ t.anomaly_type }}</div>
                      <div class="mono muted" style="font-size: 11px">{{ t.anomaly_code }}</div>
                    </td>
                    <td>
                      <div>{{ t.product_name_cn || t.product_name || t.object_ref || '—' }}</div>
                      <div class="mono muted" style="font-size: 11px">
                        {{ objectTypeLabel(t.object_type) }} · {{ t.product_id || t.seller_sku || t.object_ref || '' }}
                      </div>
                    </td>
                    <td class="mono" style="max-width: 120px">
                      <div>{{ fmtMetricValue(t.current_value, t.current_value_label) }}</div>
                      <div
                        v-if="t.compare_value != null && t.compare_value !== ''"
                        class="muted"
                        style="font-size: 11px"
                      >
                        vs {{ fmtMetricValue(t.compare_value, t.compare_value_label) }}
                      </div>
                    </td>
                    <td style="max-width: 220px">
                      <div>{{ t.summary || '—' }}</div>
                      <div
                        v-if="t.description && t.description !== t.summary"
                        class="muted"
                        style="font-size: 11px; margin-top: 2px"
                      >
                        {{ t.description }}
                      </div>
                    </td>
                    <td class="muted" style="max-width: 160px">{{ t.metric_snapshot || '—' }}</td>
                    <td>{{ t.owner_name || '—' }}</td>
                    <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                    <td>
                      <div class="actions" style="flex-wrap: wrap; gap: 4px">
                        <button
                          v-if="t.object_type === 'creator'"
                          type="button"
                          class="btn btn-ghost"
                          style="font-size: 11px; padding: 2px 6px"
                          @click="drillFromTkTaskToAffiliate(t)"
                        >
                          达人明细
                        </button>
                        <template v-if="t.status === 'open' || t.status === 'in_progress'">
                          <button class="btn btn-ghost" @click="openProgress(t, 'tk')">进度</button>
                          <button class="btn btn-danger" @click="openResolve(t, 'tk')">闭环</button>
                        </template>
                        <span
                          v-else-if="t.object_type !== 'creator'"
                          class="muted"
                        >{{ t.progress_note || '—' }}</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="row" style="margin-top: 12px; justify-content: space-between">
              <div class="muted">
                共 {{ tkTotal }} 条 · 第 {{ tkFilters.page }} 页
              </div>
              <div class="actions">
                <button
                  class="btn"
                  :disabled="tkFilters.page <= 1 || loading"
                  @click="tkFilters.page -= 1; loadTkTasks()"
                >
                  上一页
                </button>
                <button
                  class="btn"
                  :disabled="tkFilters.page * tkFilters.page_size >= tkTotal || loading"
                  @click="tkFilters.page += 1; loadTkTasks()"
                >
                  下一页
                </button>
                <button class="btn" @click="openGlobalTasks('tiktok')">中心任务引擎（TikTok）</button>
              </div>
            </div>
          </div>
        </section>

        <!-- Amazon / Temu 自动化发货 -->
        <section v-show="isShippingPage">
          <div class="grid-stats">
            <div class="stat accent">
              <div class="label">授权/规划店铺</div>
              <div class="value">{{ currentShippingShops.length }}</div>
            </div>
            <div class="stat">
              <div class="label">默认仓</div>
              <div class="value" style="font-size: 16px">
                {{ isAmzShipping ? 'FBA + UK WMS' : 'UK WMS' }}
              </div>
            </div>
            <div class="stat">
              <div class="label">ERP</div>
              <div class="value" style="font-size: 18px">赛狐</div>
            </div>
            <div class="stat">
              <div class="label">链路</div>
              <div class="value" style="font-size: 16px; color: var(--warn)">
                {{ isAmzShipping ? '建设中' : '独立运行' }}
              </div>
            </div>
          </div>

          <div class="card" style="margin-bottom: 16px">
            <div class="card-head">
              <h2 style="margin: 0">{{ shippingTitle }}</h2>
              <span class="phase-tag">{{ isAmzShipping ? 'Phase2 · 建设中' : '现网桥 · 中台入口' }}</span>
            </div>
            <p class="muted plan-p">{{ shippingSubtitle }}</p>
            <div class="actions" style="margin-top: 10px">
              <button
                v-if="isAmzShipping"
                class="btn"
                @click="switchTab('temu-shipping')"
              >
                查看 Temu 发货
              </button>
              <button
                v-else
                class="btn"
                @click="switchTab('amz-shipping')"
              >
                查看 Amazon 发货
              </button>
              <button class="btn" @click="openGlobalTasks(isAmzShipping ? 'amazon' : 'temu')">
                发货相关异常任务
              </button>
            </div>
          </div>

          <div class="card">
            <h2>发货流水线</h2>
            <div class="pipeline">
              <div v-for="s in currentShippingPipeline" :key="s.step" class="pipe-step">
                <div class="pipe-num">{{ s.step }}</div>
                <div>
                  <div class="pipe-title">{{ s.title }}</div>
                  <div class="muted">{{ s.desc }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="card">
            <h2>{{ isAmzShipping ? 'Amazon 履约范围' : 'Temu 授权店铺' }}</h2>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>店铺</th>
                    <th>平台</th>
                    <th>履约仓</th>
                    <th>模式</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in currentShippingShops" :key="s.name + s.platform">
                    <td>{{ s.name }}</td>
                    <td>{{ s.platform }}</td>
                    <td>{{ s.warehouse }}</td>
                    <td class="muted">{{ s.mode }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <ul v-if="isAmzShipping" class="hint-list" style="margin-top: 14px">
              <li><strong>FBM</strong>：对齐海外仓桥（赛狐物流下单 → WMS → 运单回传），库存补齐会议缺口。</li>
              <li><strong>FBA</strong>：以赛狐/后台库存与绩效同步为主，异常进任务中心（迟发、库存风险）。</li>
              <li>中台先做监控入口与任务闭环；发货执行仍可由 <code>E:\project\海外仓</code> 扩展 Amazon 规则。</li>
            </ul>
            <ul v-else class="hint-list" style="margin-top: 14px">
              <li>现有资产：<code>E:\project\海外仓</code>（Python + Sellfox + WMS）</li>
              <li>Phase1+：赛狐 Worker 抽离；发货状态回写中心库</li>
            </ul>
          </div>
        </section>

        <section v-show="activeTab === 'temu-plugin'">
          <div class="plugin-grid">
            <div
              v-for="p in plugins.filter((x) => x.platformKey === 'temu' || x.platformKey === 'common')"
              :key="p.id"
              class="card plugin-card"
            >
              <div class="plugin-head">
                <div>
                  <div class="plugin-name">{{ p.name }}</div>
                  <div class="muted">{{ p.kind }}</div>
                </div>
                <span class="badge-status" :class="p.statusClass">{{ p.status }}</span>
              </div>
              <p class="plugin-desc">{{ p.desc }}</p>
              <div class="mono muted">{{ p.path }}</div>
            </div>
          </div>
        </section>

        <!-- 财务 · 页内 Tab -->
        <section v-show="activeTab === 'finance'">
          <div class="card">
            <div class="inner-tabs">
              <button
                v-for="t in FINANCE_TABS"
                :key="t.id"
                type="button"
                class="inner-tab"
                :class="{ active: financeTab === t.id }"
                @click="financeTab = t.id"
              >
                {{ t.label }}
              </button>
            </div>
            <div class="finance-panel">
              <span class="phase-tag">Phase4 · 规划中</span>
              <h2 style="margin: 10px 0 8px">{{ currentFinance.label }}</h2>
              <p class="muted plan-p">{{ currentFinance.desc }}</p>
              <div class="muted" style="font-size: 13px; margin-bottom: 8px">数据来源</div>
              <div class="actions">
                <span v-for="s in currentFinance.sources" :key="s" class="chip">{{ s }}</span>
              </div>
              <div class="panel-empty" style="margin-top: 20px">
                报表计算与出纳飞书表接入后在此展示。详见 docs/中台产品蓝图.md §5.5
              </div>
            </div>
          </div>
        </section>

        <!-- 美工 -->
        <section v-show="activeTab === 'design-tasks' || activeTab === 'design-dashboard' || activeTab === 'design-push'">
          <div class="card plan-card">
            <span class="phase-tag">Phase3 · 规划中</span>
            <h2 style="margin-top: 8px">
              {{
                activeTab === 'design-dashboard'
                  ? '美工仪表盘'
                  : activeTab === 'design-push'
                    ? '跨部门推送'
                    : '美工任务表'
              }}
            </h2>
            <p class="muted plan-p">
              <template v-if="activeTab === 'design-tasks'">设计需求任务、进度、SLA；类型 design_*，可复用任务状态机。</template>
              <template v-else-if="activeTab === 'design-dashboard'">产能、按时完成率、各部门提需量（占位）。</template>
              <template v-else>各部门需求汇总推送；任务完成后回推相应需求部门（飞书/智能体）。</template>
            </p>
            <div class="actions">
              <button class="btn" :class="{ 'btn-primary': activeTab === 'design-tasks' }" @click="switchTab('design-tasks')">任务表</button>
              <button class="btn" :class="{ 'btn-primary': activeTab === 'design-dashboard' }" @click="switchTab('design-dashboard')">仪表盘</button>
              <button class="btn" :class="{ 'btn-primary': activeTab === 'design-push' }" @click="switchTab('design-push')">跨部门推送</button>
            </div>
          </div>
        </section>

        <!-- 系统：异常任务中心 -->
        <section v-show="activeTab === 'tasks'">
          <div class="grid-stats">
            <div class="stat"><div class="label">任务总数</div><div class="value">{{ stats.total }}</div></div>
            <div class="stat"><div class="label">本页待处理</div><div class="value">{{ stats.open }}</div></div>
            <div class="stat"><div class="label">本页进行中</div><div class="value">{{ stats.doing }}</div></div>
            <div class="stat"><div class="label">本页已闭环</div><div class="value">{{ stats.resolved }}</div></div>
          </div>
          <div class="card">
            <div class="row" style="margin-bottom: 12px">
              <label class="field">
                状态
                <select v-model="filters.status" @change="onFilterChange">
                  <option value="">全部</option>
                  <option value="open">待处理</option>
                  <option value="in_progress">进行中</option>
                  <option value="resolved">已闭环</option>
                  <option value="cancelled">已取消</option>
                </select>
              </label>
              <label class="field">
                平台
                <select v-model="filters.platform" @change="onFilterChange">
                  <option value="">全部</option>
                  <option value="amazon">Amazon</option>
                  <option value="tiktok">TikTok</option>
                  <option value="temu">Temu</option>
                </select>
              </label>
              <div class="muted grow">跨平台统一任务引擎</div>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>状态</th><th>平台</th><th>异常</th><th>业务ID</th><th>标题</th><th>进度</th><th>更新时间</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!tasks.length"><td colspan="8" class="muted">暂无异常任务</td></tr>
                  <tr v-for="t in tasks" :key="t.id">
                    <td><span class="badge" :class="t.status">{{ statusLabel(t.status) }}</span></td>
                    <td>{{ t.platform }}</td>
                    <td class="mono">{{ t.anomaly_type }}</td>
                    <td class="mono">{{ t.biz_id }}</td>
                    <td>{{ t.title }}</td>
                    <td>{{ t.progress_note || '—' }}</td>
                    <td class="muted">{{ fmtTime(t.updated_at) }}</td>
                    <td>
                      <div v-if="t.status !== 'resolved' && t.status !== 'cancelled'" class="actions">
                        <button class="btn btn-ghost" @click="openProgress(t)">进度</button>
                        <button class="btn btn-danger" @click="openResolve(t)">闭环</button>
                      </div>
                      <span v-else class="muted">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'shops'">
          <div class="card">
            <div class="card-head">
              <h2>店铺主数据</h2>
              <span class="muted">共 {{ shops.length }} 个</span>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>平台</th><th>名称</th><th>外部ID</th><th>币种</th><th>时区</th><th>状态</th></tr>
                </thead>
                <tbody>
                  <tr v-if="!shops.length"><td colspan="6" class="muted">暂无店铺</td></tr>
                  <tr v-for="s in shops" :key="s.id">
                    <td>{{ s.platform }}</td>
                    <td>{{ s.name }}</td>
                    <td class="mono">{{ s.external_shop_id }}</td>
                    <td>{{ s.currency }}</td>
                    <td class="muted">{{ s.timezone || '—' }}</td>
                    <td>{{ s.status }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'plugins'">
          <div class="card" style="margin-bottom: 16px">
            <h2>采集插件与节点</h2>
            <p class="muted" style="margin: 0; font-size: 13px">边缘采集经 Agent SDK 调 Ingest API，不直连数据库。</p>
          </div>
          <div class="plugin-grid">
            <div v-for="p in plugins" :key="p.id" class="card plugin-card">
              <div class="plugin-head">
                <div>
                  <div class="plugin-name">{{ p.name }}</div>
                  <div class="muted">{{ p.platform }} · {{ p.kind }}</div>
                </div>
                <span class="badge-status" :class="p.statusClass">{{ p.status }}</span>
              </div>
              <p class="plugin-desc">{{ p.desc }}</p>
              <div class="mono muted">{{ p.path }}</div>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'ai-reports'">
          <div class="dash-grid">
            <div class="card">
              <h2>生成简报</h2>
              <div class="stack">
                <label class="field">
                  报表模板
                  <select v-model="aiForm.template">
                    <option v-for="t in aiReportTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
                  </select>
                </label>
                <label class="field">
                  时间范围
                  <select v-model="aiForm.range">
                    <option value="yesterday">昨日</option>
                    <option value="last7">近 7 天</option>
                    <option value="last30">近 30 天</option>
                  </select>
                </label>
                <label class="field">
                  补充说明
                  <textarea v-model="aiForm.note" placeholder="可选" />
                </label>
                <button class="btn btn-primary" @click="generateAiReport">生成预览</button>
              </div>
            </div>
            <div class="card">
              <h2>模板说明</h2>
              <div class="tpl-list">
                <div v-for="t in aiReportTemplates" :key="t.id" class="tpl-item">
                  <div class="tpl-name">{{ t.name }} <span class="chip">{{ t.scope }}</span></div>
                  <div class="muted">{{ t.desc }}</div>
                </div>
              </div>
            </div>
          </div>
          <div class="card">
            <h2>报表预览</h2>
            <pre v-if="aiMsg" class="ai-preview">{{ aiMsg }}</pre>
            <div v-else class="panel-empty">选择模板后生成预览</div>
          </div>
        </section>

        <section v-show="activeTab === 'sync'">
          <div class="card">
            <h2>飞书同步</h2>
            <p class="muted plan-p">
              系统级任务表增量同步到飞书 Bitable（table_key=tasks）。与采购域「采购数据同步」不同，本页只负责中心 → 飞书出队。
            </p>
            <div class="actions">
              <button class="btn btn-primary" :disabled="loading" @click="triggerFeishu">
                {{ loading ? '提交中…' : '触发增量同步' }}
              </button>
            </div>
            <div v-if="syncMsg" class="muted" style="margin-top: 14px; color: var(--ok)">{{ syncMsg }}</div>
          </div>
        </section>
      </div>
    </div>

    <div v-if="drawer.open" class="drawer-mask" @click.self="closeDrawer">
      <div class="drawer">
        <h2 style="margin-top: 0">
          <template v-if="drawer.mode === 'create' && drawer.source === 'tk'">新建 TK 异常任务</template>
          <template v-else-if="drawer.mode === 'create'">新建异常任务</template>
          <template v-else-if="drawer.mode === 'progress'">更新进度</template>
          <template v-else>闭环异常任务</template>
        </h2>

        <!-- 中心任务新建 -->
        <div v-if="drawer.mode === 'create' && drawer.source !== 'tk'" class="stack">
          <label class="field">
            平台
            <select v-model="createForm.platform">
              <option value="tiktok">tiktok</option>
              <option value="amazon">amazon</option>
              <option value="temu">temu</option>
            </select>
          </label>
          <label class="field">异常类型<input v-model="createForm.anomaly_type" /></label>
          <label class="field">业务ID<input v-model="createForm.biz_id" /></label>
          <label class="field">标题<input v-model="createForm.title" /></label>
          <label class="field">备注<textarea v-model="createForm.progress_note" /></label>
        </div>

        <!-- TK 异常新建 -->
        <div v-else-if="drawer.mode === 'create' && drawer.source === 'tk'" class="stack">
          <label class="field">
            异常类型
            <select v-model="tkCreateForm.anomaly_code">
              <option v-for="t in tkTypes" :key="t.code" :value="t.code">
                {{ t.name_cn }}（{{ t.code }}）
              </option>
            </select>
          </label>
          <label class="field">
            店铺
            <select v-model="tkCreateForm.shop_external_id">
              <option value="">（不选）</option>
              <option v-for="s in tkShops" :key="s.id" :value="s.external_shop_id">
                {{ s.name }} · {{ s.external_shop_id }}
              </option>
            </select>
          </label>
          <label class="field">
            优先级
            <select v-model="tkCreateForm.priority">
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
            </select>
          </label>
          <label class="field">摘要 / 标题<input v-model="tkCreateForm.summary" placeholder="可选，默认用异常类型名" /></label>
          <label class="field">商品 ID<input v-model="tkCreateForm.product_id" /></label>
          <label class="field">商品名<input v-model="tkCreateForm.product_name" /></label>
          <label class="field">中文名<input v-model="tkCreateForm.product_name_cn" /></label>
          <label class="field">Seller SKU<input v-model="tkCreateForm.seller_sku" /></label>
          <label class="field">对象引用 object_ref<input v-model="tkCreateForm.object_ref" placeholder="默认取商品ID/SKU/店铺" /></label>
          <label class="field">指标快照<textarea v-model="tkCreateForm.metric_snapshot" placeholder="如 ROI=1.2 / 库存=3" /></label>
          <label class="field">备注<textarea v-model="tkCreateForm.progress_note" /></label>
          <label class="field">负责人<input v-model="tkCreateForm.owner_name" placeholder="默认当前用户" /></label>
        </div>

        <!-- 进度 / 闭环 -->
        <div v-else class="stack">
          <div class="muted mono">
            {{ drawer.source === 'tk' ? drawer.task?.task_key : drawer.task?.dedupe_key }}
          </div>
          <div>
            <strong>
              {{ drawer.source === 'tk' ? drawer.task?.summary || drawer.task?.anomaly_type : drawer.task?.title }}
            </strong>
          </div>
          <div v-if="drawer.source === 'tk'" class="muted" style="font-size: 13px">
            {{ drawer.task?.shop_name || drawer.task?.shop_external_id || '' }}
            ·
            {{ drawer.task?.product_name_cn || drawer.task?.product_name || drawer.task?.object_ref || '' }}
            ·
            {{ drawer.task?.priority }}
          </div>

          <template v-if="drawer.source !== 'tk'">
            <div class="kb-panel">
              <div class="kb-title">历史参考</div>
              <div v-if="drawer.guidanceLoading" class="muted">加载中…</div>
              <div v-else-if="drawer.guidance?.error" class="muted">{{ drawer.guidance.error }}</div>
              <ul v-else-if="drawer.guidance?.history?.length" class="kb-list">
                <li v-for="h in drawer.guidance.history" :key="h.action_code">
                  <span class="mono">{{ h.action_code }}</span>
                  ×{{ h.count }}
                  <span class="muted">
                    （{{ Object.entries(h.effects || {}).map(([k, v]) => `${k}:${v}`).join(', ') }}）
                  </span>
                </li>
              </ul>
              <div v-else class="muted">暂无结构化历史</div>
            </div>

            <div class="kb-panel">
              <div class="kb-title">已发布剧本</div>
              <div v-if="drawer.guidanceLoading" class="muted">加载中…</div>
              <div v-else-if="drawer.guidance?.playbooks?.length">
                <div v-for="p in drawer.guidance.playbooks" :key="p.id" class="kb-playbook">
                  <strong>{{ p.title }}</strong>
                  <p class="muted" style="margin: 6px 0 0; white-space: pre-wrap">{{ p.body }}</p>
                </div>
              </div>
              <div v-else class="muted">暂无已发布剧本</div>
            </div>

            <label class="field">
              运营动作（可选）
              <select v-model="drawer.action_code">
                <option value="">（不选）</option>
                <option v-for="a in ACTION_OPTIONS" :key="a.code" :value="a.code">{{ a.label }}</option>
              </select>
            </label>
            <label v-if="drawer.mode === 'resolve'" class="field">
              效果标签{{ isSkeletonTask(drawer.task) ? '（必选）' : '（可选）' }}
              <select v-model="drawer.effect_code">
                <option value="">（不选）</option>
                <option v-for="e in EFFECT_OPTIONS" :key="e.code" :value="e.code">{{ e.label }}</option>
              </select>
            </label>
          </template>

          <label v-if="drawer.source === 'tk' && drawer.mode === 'resolve'" class="field">
            闭环结果
            <select v-model="drawer.resolveStatus">
              <option value="resolved">已闭环</option>
              <option value="cancelled">已取消</option>
              <option value="ignored">已忽略</option>
            </select>
          </label>
          <label class="field">
            说明
            <textarea v-model="drawer.note" />
          </label>
        </div>
        <div class="actions" style="margin-top: 16px; justify-content: flex-end">
          <button class="btn" @click="closeDrawer">取消</button>
          <button class="btn btn-primary" :disabled="loading" @click="submitDrawer">
            {{ loading ? '提交中…' : '确定' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
