/**
 * 从拦截到的报表 API JSON 中抽取广告系列字段
 * 结构因接口而异，做多层启发式遍历
 */

import { cleanText, parseNumber } from './normalize.js';

const KEY_MAP = {
  campaign: [
    'campaign_name',
    'campaignName',
    'ad_name',
    'adName',
    'name',
    'title',
    'product_name',
    'productName',
    'creative_name'
  ],
  spend: [
    'spend',
    'cost',
    'ad_spend',
    'adSpend',
    'stat_cost',
    'statCost',
    'amount_spent',
    'consume'
  ],
  orders: [
    'orders',
    'order_count',
    'orderCount',
    'units',
    'units_sold',
    'unitsSold',
    'paid_order_count',
    'conversions',
    'onsite_shopping'
  ],
  roi: ['roi', 'roas', 'ROI', 'ROAS', 'complete_payment_roas', 'onsite_roas'],
  revenue: [
    'revenue',
    'gmv',
    'gross_revenue',
    'grossRevenue',
    'total_revenue',
    'onsite_shopping_value',
    'complete_payment',
    'sales',
    'income'
  ],
  planStatus: [
    'opt_status',
    'optStatus',
    'operation_status',
    'operationStatus',
    'enable',
    'enabled',
    'is_enable',
    'isEnable',
    'switch_status',
    'switchStatus'
  ],
  deliveryStatus: [
    'delivery_status',
    'deliveryStatus',
    'campaign_status',
    'campaignStatus',
    'status_name',
    'statusName'
  ],
  dailyBudget: [
    'daily_budget',
    'dailyBudget',
    'budget',
    'current_budget',
    'currentBudget'
  ],
  targetRoi: ['target_roi', 'targetRoi', 'target_roas', 'targetRoas'],
  netCost: ['net_cost', 'netCost', 'net_spend', 'netSpend'],
  avgOrderCost: [
    'avg_order_cost',
    'avgOrderCost',
    'cost_per_order',
    'costPerOrder',
    'cpa',
    'average_order_cost'
  ]
};

/**
 * @param {unknown} payload
 * @returns {object[]}
 */
export function parseApiPayload(payload) {
  if (payload == null) return [];
  let data = payload;
  if (typeof payload === 'string') {
    try {
      data = JSON.parse(payload);
    } catch {
      return [];
    }
  }

  const list = findArrayOfObjects(data);
  if (!list.length) return [];

  const rows = [];
  for (const item of list) {
    if (!item || typeof item !== 'object') continue;
    const row = extractRow(item);
    if (row.campaign || row.spend != null || row.revenue != null) {
      rows.push(row);
    }
  }
  return rows;
}

function normalizeApiPlanStatus(v) {
  if (v == null || v === '') return null;
  if (typeof v === 'boolean') return v ? 'on' : 'off';
  if (typeof v === 'number') {
    if (v === 1) return 'on';
    if (v === 0) return 'off';
  }
  const s = String(v).trim().toLowerCase();
  if (/^(on|1|true|enable|enabled|open|active|running|delivery_ok|campaign_status_enable)$/i.test(s)) {
    return 'on';
  }
  if (
    /^(off|0|false|disable|disabled|close|closed|paused|inactive|campaign_status_disable|campaign_status_delete)$/i.test(
      s
    )
  ) {
    return 'off';
  }
  return null;
}

function extractRow(obj) {
  const flat = flattenObject(obj);
  const row = {};
  for (const [field, keys] of Object.entries(KEY_MAP)) {
    for (const k of keys) {
      if (flat[k] != null && flat[k] !== '') {
        if (field === 'campaign') row[field] = cleanText(flat[k]);
        else if (field === 'planStatus') row[field] = normalizeApiPlanStatus(flat[k]) || flat[k];
        else row[field] = parseNumber(flat[k]) ?? flat[k];
        break;
      }
    }
    // 大小写不敏感扫一遍
    if (row[field] == null) {
      const lowerKeys = Object.keys(flat);
      for (const k of keys) {
        const hit = lowerKeys.find((x) => x.toLowerCase() === k.toLowerCase());
        if (hit && flat[hit] != null && flat[hit] !== '') {
          if (field === 'campaign') row[field] = cleanText(flat[hit]);
          else if (field === 'planStatus') {
            row[field] = normalizeApiPlanStatus(flat[hit]) || flat[hit];
          } else row[field] = parseNumber(flat[hit]) ?? flat[hit];
          break;
        }
      }
    }
  }
  return row;
}

/**
 * 扁平化一层 metrics / stats 嵌套
 */
function flattenObject(obj, prefix = '', out = {}, depth = 0) {
  if (!obj || typeof obj !== 'object' || depth > 4) return out;
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      // 保留浅 key
      out[k] = out[k] ?? (typeof v.value !== 'undefined' ? v.value : undefined);
      flattenObject(v, key, out, depth + 1);
      // metrics 常见 { value: 1 }
      if (v.value != null) out[k] = v.value;
    } else if (!Array.isArray(v)) {
      out[k] = v;
      out[key] = v;
    }
  }
  return out;
}

/**
 * 在 JSON 树中找「最像报表行」的对象数组
 * @param {unknown} data
 * @returns {object[]}
 */
function findArrayOfObjects(data, depth = 0) {
  if (depth > 8 || data == null) return [];
  if (Array.isArray(data)) {
    const objs = data.filter((x) => x && typeof x === 'object' && !Array.isArray(x));
    if (objs.length >= 1 && looksLikeReportRows(objs)) return objs;
    // 继续往子项挖
    for (const item of data.slice(0, 20)) {
      const found = findArrayOfObjects(item, depth + 1);
      if (found.length) return found;
    }
    if (objs.length >= 1) return objs;
    return [];
  }
  if (typeof data === 'object') {
    // 优先常见字段
    const prefer = [
      'list',
      'rows',
      'data',
      'items',
      'records',
      'campaigns',
      'result',
      'table'
    ];
    for (const k of prefer) {
      if (data[k] != null) {
        const found = findArrayOfObjects(data[k], depth + 1);
        if (found.length) return found;
      }
    }
    for (const v of Object.values(data)) {
      const found = findArrayOfObjects(v, depth + 1);
      if (found.length) return found;
    }
  }
  return [];
}

function looksLikeReportRows(objs) {
  const sample = objs.slice(0, 5);
  let hits = 0;
  for (const o of sample) {
    const keys = Object.keys(o).join(' ').toLowerCase();
    if (/campaign|spend|cost|roi|roas|gmv|revenue|order|name/.test(keys)) hits += 1;
    // nested metrics
    if (o.metrics || o.stats || o.stat) hits += 1;
  }
  return hits >= 1;
}

/**
 * URL 是否可能是报表接口
 * @param {string} url
 */
export function isLikelyReportUrl(url) {
  if (!url) return false;
  const u = url.toLowerCase();
  return /report|stat|metric|campaign|gmv|ads?\/api|shop_ads|analytics|performance|overview|data_list|getlist/.test(
    u
  );
}
