/**
 * 字段归一化：统一为业务 5 字段 + 元数据
 */

/**
 * 从单元格文本识别币种（$ / £ / € 等）
 * @param {unknown} text
 * @returns {'USD'|'GBP'|'EUR'|'CNY'|null}
 */
export function detectCurrency(text) {
  const s = String(text ?? '');
  if (/[£]|GBP|英镑/i.test(s)) return 'GBP';
  if (/[€]|EUR|欧元/i.test(s)) return 'EUR';
  if (/[¥￥]|CNY|RMB|元/i.test(s) && !/\$/.test(s)) return 'CNY';
  if (/\$|USD|美金|美元/i.test(s)) return 'USD';
  return null;
}

/**
 * 从字符串解析数字（去掉货币符号、千分位、百分号）
 * 金额按美金口径使用；符号仅用于识别币种，不改变数值本身。
 * @param {unknown} value
 * @returns {number|null}
 */
export function parseNumber(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  let s = String(value).trim();
  if (!s || s === '-' || s === '—') return null;
  s = s
    .replace(/[,\s]/g, '')
    .replace(/[¥$€£￥]/g, '')
    .replace(/USD|GBP|EUR|CNY|RMB|美金|美元|英镑|欧元/gi, '')
    .replace(/%/g, '');
  // 括号负数 (1.2) → -1.2
  const paren = s.match(/^\((.+)\)$/);
  if (paren) s = `-${paren[1]}`;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/**
 * @param {string} text
 * @returns {string}
 */
export function cleanText(text) {
  return String(text ?? '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** 英区广告后台时区（含夏令时）。中国早上 8 点 ≈ 英国 0 点。 */
export const DEFAULT_BIZ_TIMEZONE = 'Europe/London';

/**
 * 按业务时区格式化 YYYY-MM-DD（不用浏览器本地日历日）
 * @param {Date} [date]
 * @param {string} [timeZone]
 */
export function formatDateInTimeZone(date = new Date(), timeZone = DEFAULT_BIZ_TIMEZONE) {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(date);
  } catch {
    return formatDateLocal(date);
  }
}

/**
 * YYYY-MM-DD ± N 天（按日历日，与时区无关）
 * @param {string} ymd
 * @param {number} deltaDays
 */
export function shiftYmd(ymd, deltaDays) {
  const [y, m, d] = String(ymd).split('-').map(Number);
  const utc = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
  utc.setUTCDate(utc.getUTCDate() + deltaDays);
  const yy = utc.getUTCFullYear();
  const mm = String(utc.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(utc.getUTCDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

/**
 * 解析业务日期 YYYY-MM-DD
 * 默认按 Europe/London（英区后台），避免中国本地「今天」对应英国日刚开始。
 * @param {'yesterday'|'today'|'custom'} mode
 * @param {string} [customDate]
 * @param {string} [timeZone]
 */
export function resolveBizDate(mode, customDate, timeZone = DEFAULT_BIZ_TIMEZONE) {
  if (mode === 'custom' && customDate) {
    return customDate.slice(0, 10);
  }
  const today = formatDateInTimeZone(new Date(), timeZone || DEFAULT_BIZ_TIMEZONE);
  if (mode === 'yesterday') {
    return shiftYmd(today, -1);
  }
  return today;
}

export function formatDateLocal(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * 应用店铺名映射
 * @param {string} detected
 * @param {{alias:string,name:string}[]} mappings
 * @param {string} [fallback]
 */
export function mapStoreName(detected, mappings = [], fallback = '') {
  const raw = cleanText(detected || '');
  if (!raw && fallback) return fallback;
  for (const m of mappings) {
    if (!m?.alias) continue;
    if (raw.toLowerCase().includes(String(m.alias).toLowerCase()) ||
        String(m.alias).toLowerCase().includes(raw.toLowerCase())) {
      return m.name || m.alias;
    }
  }
  return raw || fallback || '未知店铺';
}

/**
 * 将原始行归一化为标准记录
 * @param {object} row
 * @param {object} ctx
 */
/**
 * 计划开关归一：on | off | unknown
 * @param {unknown} raw
 * @returns {'on'|'off'|'unknown'}
 */
export function normalizePlanStatus(raw) {
  if (raw == null || raw === '') return 'unknown';
  const s = String(raw).trim().toLowerCase();
  if (/^(on|1|true|open|enable|enabled|active|running|投放中|开启|开)$/i.test(s)) {
    return 'on';
  }
  if (
    /^(off|0|false|close|closed|disable|disabled|paused|inactive|已关闭|关闭|关|暂停)$/i.test(
      s
    )
  ) {
    return 'off';
  }
  return 'unknown';
}

export function normalizeRow(row, ctx = {}) {
  const campaign = cleanText(row.campaign ?? row.name ?? '');
  const spend = parseNumber(row.spend ?? row.cost);
  const orders = parseNumber(row.orders ?? row.units ?? row.sales_count);
  const roi = parseNumber(row.roi ?? row.roas);
  const revenue = parseNumber(row.revenue ?? row.gmv ?? row.income);
  // 与广告后台一致：落库单位为美金 USD
  const currency = cleanText(row.currency || ctx.currency || 'USD').toUpperCase() || 'USD';
  const planStatus = normalizePlanStatus(row.planStatus ?? row.switch ?? row.enabled);

  const filled = [campaign, spend, orders, roi, revenue].filter(
    (v) => v !== null && v !== ''
  ).length;

  let status = 'success';
  if (!campaign && filled === 0) status = 'error';
  else if (filled < 4) status = 'partial';

  return {
    date: ctx.date || resolveBizDate('yesterday'),
    store: ctx.storeName || '未知店铺',
    storeId: ctx.storeId || '',
    campaign,
    spend: spend ?? 0,
    orders: orders ?? 0,
    roi: roi ?? 0,
    revenue: revenue ?? 0,
    currency,
    scrapedAt: ctx.scrapedAt || new Date().toISOString(),
    sourceUrl: ctx.sourceUrl || '',
    status,
    planStatus
  };
}

/**
 * 过滤空行 / 汇总行；策略 C：已关闭且花费=0且销售额=0 跳过
 * @param {ReturnType<typeof normalizeRow>[]} rows
 * @param {{ skipZeroDisabled?: boolean }} [opts]
 */
export function filterValidRows(rows, opts = {}) {
  const skipZeroDisabled = opts.skipZeroDisabled !== false;
  return rows.filter((r) => {
    if (!r) return false;
    if (!r.campaign) return false;
    const lower = r.campaign.toLowerCase();
    if (['total', '合计', '总计', '汇总', 'summary', 'all'].includes(lower)) {
      return false;
    }
    if (skipZeroDisabled) {
      const ps = normalizePlanStatus(r.planStatus);
      const spend = Number(r.spend) || 0;
      const revenue = Number(r.revenue) || 0;
      if (ps === 'off' && spend === 0 && revenue === 0) return false;
    }
    return true;
  });
}
