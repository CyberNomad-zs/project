/**
 * Temu 跨境父体全量拉取（30 天滑窗 + 分页 + 去重）
 */
import { ymd } from './client.js';
import { log } from '../logger.js';

/** Temu 生命周期：12=已加入站点(在售) 13=已下架 */
export const SELECT_STATUS = {
  ON_SALE: '12',
  DELISTED: '13',
};

function parseYmd(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function fmtYmd(d) {
  return ymd(d);
}

/** 倒序 30 天窗口 */
export function* iterWindows(startDate, endDate, maxSpanDays = 30) {
  let end = parseYmd(endDate);
  let start = parseYmd(startDate);
  if (start > end) [start, end] = [end, start];
  let curEnd = end;
  while (curEnd >= start) {
    const curStart = new Date(curEnd);
    curStart.setDate(curStart.getDate() - (maxSpanDays - 1));
    if (curStart < start) curStart.setTime(start.getTime());
    yield { startDate: fmtYmd(curStart), endDate: fmtYmd(curEnd) };
    curEnd = new Date(curStart);
    curEnd.setDate(curEnd.getDate() - 1);
  }
}

/**
 * @param {ReturnType<import('./client.js').createSellfoxClient>} client
 * @param {{ shopIds: string[], pageSize?: number, maxPagesPerWindow?: number, dateType?: string, startDate?: string, endDate?: string, lookbackDays?: number }} opts
 */
export async function fetchAllCrossParents(client, opts) {
  const pageSize = Math.min(100, Number(opts.pageSize) || 100);
  const maxPages = Number(opts.maxPagesPerWindow) || 50;
  const dateType = opts.dateType || 'updateDate';
  const endDate = opts.endDate || fmtYmd(new Date());
  let startDate = opts.startDate;
  if (!startDate) {
    const d = parseYmd(endDate);
    d.setDate(d.getDate() - (Number(opts.lookbackDays) || 30));
    startDate = fmtYmd(d);
  }

  const all = [];
  const seen = new Set();
  const windowsMeta = [];

  for (const w of iterWindows(startDate, endDate, 30)) {
    let pageNo = 1;
    let totalSize = null;
    let totalPage = null;
    let windowRows = 0;
    while (pageNo <= maxPages) {
      const data = await client.temuCrossParentPage({
        pageNo,
        pageSize,
        shopIds: opts.shopIds,
        dateType,
        startDate: w.startDate,
        endDate: w.endDate,
      });
      const rows = (data && (data.rows || data.list)) || (Array.isArray(data) ? data : []);
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        if (totalSize == null && data.totalSize != null) totalSize = data.totalSize;
        if (totalPage == null && data.totalPage != null) totalPage = data.totalPage;
      }
      for (const r of rows) {
        if (!r || typeof r !== 'object') continue;
        const key = String(r.parentId || r.skcId || '');
        if (!key || seen.has(key)) continue;
        seen.add(key);
        all.push(normalizeParent(r));
        windowRows++;
      }
      if (!rows.length) break;
      if (totalSize != null && windowRows >= Number(totalSize)) break;
      if (totalPage != null && pageNo >= Number(totalPage)) break;
      if (rows.length < pageSize) break;
      pageNo++;
      // 避免 40019 调用超过限制
      await new Promise((r) => setTimeout(r, 350));
    }
    windowsMeta.push({ ...w, row_count: windowRows, totalSize });
    log.info(`Sellfox window ${w.startDate}~${w.endDate}: +${windowRows} (unique ${all.length})`);
  }

  return {
    items: all,
    meta: {
      dateType,
      range: `${startDate}~${endDate}`,
      windows: windowsMeta.length,
      unique: all.length,
      windowsDetail: windowsMeta,
    },
  };
}

export function normalizeParent(r) {
  return {
    parentId: r.parentId != null ? String(r.parentId) : '',
    skcId: r.skcId != null ? String(r.skcId) : '',
    shopId: r.shopId != null ? String(r.shopId) : '',
    shopName: String(r.shopName || ''),
    productName: String(r.productName || ''),
    selectStatus: r.selectStatus != null ? String(r.selectStatus) : '',
    trusteeship: r.trusteeship != null ? String(r.trusteeship) : '',
    createTime: r.createTime || '',
    updateTime: r.updateTime || '',
    extCode: r.extCode || '',
  };
}

/**
 * 规范化 getChildInfo 单条 SKU
 * @param {object} r
 */
export function normalizeChildSku(r) {
  if (!r || typeof r !== 'object') return null;
  const skuId = r.skuId != null ? String(r.skuId) : (r.productSkuId != null ? String(r.productSkuId) : '');
  if (!skuId && !r.specName && !r.extCode) return null;
  return {
    parentId: r.parentId != null ? String(r.parentId) : '',
    skuId,
    specName: String(r.specName || '').trim(),
    name: String(r.name || '').trim(),
    extCode: String(r.extCode || '').trim(),
    commoditySku: String(r.commoditySku || '').trim(),
    stockQuantity: r.stockQuantity != null && r.stockQuantity !== '' ? String(r.stockQuantity) : '',
    supplyPrice: r.supplyPrice != null ? String(r.supplyPrice) : '',
    supplyCurrency: String(r.supplyCurrency || '').trim(),
  };
}

/**
 * 解析 getChildInfo 响应为 SKU 数组
 * @param {unknown} data
 * @returns {Array<object>}
 */
export function parseChildInfo(data) {
  let rows = [];
  if (Array.isArray(data)) rows = data;
  else if (data && typeof data === 'object') {
    rows = data.rows || data.list || data.skuList || data.children || [];
    if (!Array.isArray(rows) && data.skuId) rows = [data];
  }
  if (!Array.isArray(rows)) return [];
  return rows.map(normalizeChildSku).filter(Boolean);
}

/**
 * 仅对变动的 parentId 补拉 getChildInfo（控制 40019 限流）。
 * @param {{ temuCrossChildInfo: (parentId: string) => Promise<unknown> }} client
 * @param {string[]} parentIds
 * @param {{ delayMs?: number, onError?: (pid: string, err: Error) => void }} [opts]
 * @returns {Promise<Record<string, object[]>>} parentId → skus[]
 */
export async function fetchChildrenByParentIds(client, parentIds, opts = {}) {
  const delayMs = typeof opts.delayMs === 'number' ? opts.delayMs : 450;
  const uniq = [...new Set((parentIds || []).map(String).filter(Boolean))];
  const out = {};
  for (let i = 0; i < uniq.length; i++) {
    const pid = uniq[i];
    try {
      const raw = await client.temuCrossChildInfo(pid);
      out[pid] = parseChildInfo(raw);
    } catch (e) {
      out[pid] = [];
      if (typeof opts.onError === 'function') opts.onError(pid, e);
    }
    if (i < uniq.length - 1 && delayMs > 0) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  return out;
}

/**
 * 把 SKU 明细挂到告警 items 上（就地修改）
 * @param {Array} alertEvents
 * @param {Record<string, object[]>} childMap
 */
export function attachSkusToAlertEvents(alertEvents, childMap) {
  const map = childMap || {};
  for (const ev of alertEvents || []) {
    if (!ev || !Array.isArray(ev.items)) continue;
    for (const it of ev.items) {
      if (!it) continue;
      const pid = String(it.parentId || '');
      const skus = pid && map[pid] ? map[pid] : [];
      it.skus = skus;
    }
  }
  return alertEvents;
}

/** 按店分组；onSale = selectStatus === 12 */
export function groupByShop(items, shopNameMap = {}) {
  const shops = {};
  for (const it of items) {
    const sid = it.shopId || '?';
    if (!shops[sid]) {
      shops[sid] = {
        shopId: sid,
        shopName: shopNameMap[sid] || it.shopName || sid,
        onSaleMap: {},
        allMap: {},
        statusCounts: {},
      };
    }
    const g = shops[sid];
    if (!g.shopName && it.shopName) g.shopName = it.shopName;
    const id = it.skcId || it.parentId;
    if (!id) continue;
    const row = {
      skcId: it.skcId,
      parentId: it.parentId,
      name: it.productName,
      selectStatus: it.selectStatus,
    };
    g.allMap[id] = row;
    g.statusCounts[it.selectStatus || '<empty>'] = (g.statusCounts[it.selectStatus || '<empty>'] || 0) + 1;
    if (it.selectStatus === SELECT_STATUS.ON_SALE) {
      g.onSaleMap[id] = row;
    }
  }
  return shops;
}
