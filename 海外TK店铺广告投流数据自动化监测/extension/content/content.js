/**
 * Content Script（isolated world）
 * - 注入 fetch hook
 * - 响应 SCRAPE_PAGE：DOM + 缓存 API 数据
 *
 * 注意：不使用 ES module import，保证紫鸟/各 Chromium 版本兼容
 */

(() => {
  const HEADER_ALIASES = {
    campaign: [
      '品名',
      '广告计划名称',
      '广告系列',
      '广告系列名称',
      '系列名称',
      'campaign',
      'campaign name',
      'ad group',
      'product',
      '产品',
      '名称',
      'name'
    ],
    spend: [
      '广告花费',
      '广告成本',
      '花费',
      '成本',
      '消耗',
      'cost',
      'spend',
      'ad spend',
      'ad cost',
      'amount spent',
      'budget spent',
      'stat cost'
    ],
    orders: [
      '销量',
      '订单',
      '订单数',
      'sku 订单',
      'sku订单',
      'sku orders',
      'orders',
      'units',
      'units sold',
      'sold',
      'conversions',
      'purchases'
    ],
    roi: [
      'roi',
      'roas',
      '投资回报率',
      '投资回报',
      '回报率',
      'return on ad spend',
      'return on investment'
    ],
    revenue: [
      '销售额',
      '总收入',
      '销售收入',
      '收入',
      'gmv',
      'revenue',
      'gross revenue',
      'ads gross revenue',
      'gross merchandise',
      'sales'
    ],
    planStatus: ['开关', '投放开关', 'enable', 'enabled', 'switch', 'on/off', 'toggle']
  };

  const KEY_MAP = {
    campaign: [
      'campaign_name',
      'campaignName',
      'ad_name',
      'adName',
      'name',
      'title',
      'product_name',
      'productName'
    ],
    spend: [
      'spend',
      'cost',
      'ad_spend',
      'adSpend',
      'ad_cost',
      'stat_cost',
      'statCost',
      'amount_spent',
      'consume'
    ],
    orders: [
      'orders',
      'order_count',
      'orderCount',
      'sku_order_count',
      'skuOrderCount',
      'units',
      'units_sold',
      'unitsSold',
      'paid_order_count',
      'conversions'
    ],
    roi: ['roi', 'roas', 'ROI', 'ROAS', 'complete_payment_roas', 'net_roi'],
    revenue: [
      'revenue',
      'gmv',
      'gross_revenue',
      'grossRevenue',
      'total_revenue',
      'onsite_shopping_value',
      'sales',
      'income'
    ],
    planStatus: [
      'status',
      'opt_status',
      'optStatus',
      'operation_status',
      'operationStatus',
      'campaign_status',
      'campaignStatus',
      'enable',
      'enabled',
      'is_enable',
      'isEnable'
    ]
  };

  /** @type {{url:string, body:any, at:number}[]} */
  const apiCache = [];
  const API_CACHE_MAX = 30;

  // —— utils ——
  function cleanText(text) {
    return String(text ?? '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function detectCurrency(text) {
    const s = String(text ?? '');
    if (/[£]|GBP|英镑/i.test(s)) return 'GBP';
    if (/[€]|EUR|欧元/i.test(s)) return 'EUR';
    if (/[¥￥]|CNY|RMB|元/i.test(s) && !/\$/.test(s)) return 'CNY';
    if (/\$|USD|美金|美元/i.test(s)) return 'USD';
    return null;
  }

  function parseNumber(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    let s = String(value).trim();
    if (!s || s === '-' || s === '—') return null;
    s = s
      .replace(/[,\s]/g, '')
      .replace(/[¥$€£￥]/g, '')
      .replace(/USD|GBP|EUR|CNY|RMB|美金|美元|英镑|欧元/gi, '')
      .replace(/%/g, '');
    const paren = s.match(/^\((.+)\)$/);
    if (paren) s = `-${paren[1]}`;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  function parseSwitchFromEl(el) {
    if (!el) return null;
    const input = el.matches?.('input')
      ? el
      : el.querySelector?.('input[type="checkbox"], input[role="switch"]');
    if (input) {
      const aria = input.getAttribute('aria-checked');
      if (aria === 'true') return 'on';
      if (aria === 'false') return 'off';
      return input.checked ? 'on' : 'off';
    }
    const sw =
      (el.matches?.('[role="switch"], [class*="switch"], [class*="Switch"]') && el) ||
      el.querySelector?.(
        '[role="switch"], [class*="switch"], [class*="Switch"], [class*="toggle"]'
      );
    if (sw) {
      const aria = sw.getAttribute('aria-checked');
      if (aria === 'true') return 'on';
      if (aria === 'false') return 'off';
      const cls = `${sw.className || ''} ${sw.parentElement?.className || ''}`;
      if (
        /\b(checked|is-checked|switch-checked|arco-switch-checked|ant-switch-checked|is-on)\b/i.test(
          cls
        )
      ) {
        return 'on';
      }
      if (/\b(unchecked|is-unchecked|is-off)\b/i.test(cls)) return 'off';
    }
    const text = cleanText((el.innerText || el.textContent || '').slice(0, 40));
    if (/^(开|开启|on|enable|enabled|投放中|投放)$/i.test(text)) return 'on';
    if (/^(关|关闭|off|disable|disabled|已关闭|暂停)$/i.test(text)) return 'off';
    return null;
  }

  function detectPlanStatusFromRow(tr, cells, switchColIndex) {
    if (switchColIndex != null && cells[switchColIndex]) {
      const s = parseSwitchFromEl(cells[switchColIndex]);
      if (s) return s;
    }
    for (const cell of cells) {
      const s = parseSwitchFromEl(cell);
      if (s) return s;
    }
    return parseSwitchFromEl(tr) || 'unknown';
  }

  function matchHeaderField(headerText) {
    const t = cleanText(headerText).toLowerCase();
    if (!t) return null;
    // 排除「平均下单成本」等非广告花费列
    if (/平均下单|cost per|per order|\bcpc\b|\bcpa\b|\bcpm\b|出价|budget(?!.*spent)/i.test(t)) {
      if (!/^(成本|花费|消耗|cost|spend|广告花费|广告成本)$/i.test(t)) {
        // 仍允许纯「成本/花费」通过；带「平均」的直接跳过 spend 匹配
      }
    }
    const order = ['planStatus', 'roi', 'spend', 'orders', 'revenue', 'campaign'];
    for (const field of order) {
      if (!HEADER_ALIASES[field]) continue;
      for (const a of HEADER_ALIASES[field]) {
        const al = a.toLowerCase();
        if (!(t === al || t.includes(al) || (al.length >= 2 && al.includes(t)))) {
          continue;
        }
        if (field === 'planStatus') {
          if (/投放状态|计划状态|delivery|operation status/.test(t)) return field;
          if (t === al || t === '开关' || t === 'switch' || t === 'enable' || t === 'enabled') {
            return field;
          }
          if (/开关|switch|toggle|on\/off/.test(t) && t.length <= 12) return field;
          continue;
        }
        if (field === 'spend') {
          if (/平均下单|cost per|per order|\bcpc\b|\bcpa\b|\bcpm\b/.test(t)) continue;
          if (
            t.includes('budget') &&
            !t.includes('spent') &&
            !t.includes('spend') &&
            !t.includes('cost') &&
            !t.includes('成本')
          ) {
            continue;
          }
        }
        // 「名称」太宽，要求更像广告系列
        if (field === 'campaign' && (al === '名称' || al === 'name')) {
          if (
            !/系列|campaign|广告|活动|product|品名|计划/.test(t) &&
            t !== '名称' &&
            t !== 'name'
          ) {
            continue;
          }
        }
        // 「sales」勿抢销量列以外的无关列
        if (field === 'revenue' && al === 'sales' && /order|unit|sku|销量|订单/.test(t)) {
          continue;
        }
        return field;
      }
    }
    return null;
  }

  function extractTableHeaders(table) {
    let headerRow = table.querySelector('thead tr') || table.querySelector('tr');
    if (!headerRow) return { fields: [] };
    const cells = [...headerRow.querySelectorAll('th, td')];
    return {
      fields: cells.map((c) => matchHeaderField(c.innerText || c.textContent || ''))
    };
  }

  function parseHtmlTable(table) {
    const { fields } = extractTableHeaders(table);
    if (!fields.some(Boolean)) return [];
    let switchColIndex = fields.indexOf('planStatus');
    if (switchColIndex < 0) switchColIndex = null;
    const bodyRows = table.querySelectorAll('tbody tr');
    const rows = bodyRows.length
      ? [...bodyRows]
      : [...table.querySelectorAll('tr')].slice(1);
    const results = [];
    for (const tr of rows) {
      const cells = [...tr.querySelectorAll('td, th')];
      if (!cells.length) continue;
      const row = {};
      fields.forEach((field, i) => {
        if (!field || !cells[i]) return;
        if (field === 'planStatus') {
          row.planStatus = parseSwitchFromEl(cells[i]) || 'unknown';
          return;
        }
        row[field] = cleanText(cells[i].innerText || cells[i].textContent || '');
      });
      if (!row.planStatus) {
        row.planStatus = detectPlanStatusFromRow(tr, cells, switchColIndex);
      }
      if (Object.keys(row).length) results.push(row);
    }
    return results;
  }

  function parseRoleTable(root) {
    const headerCells = [
      ...root.querySelectorAll(
        '[role="columnheader"], .ant-table-thead th, [class*="table-header"] th'
      )
    ];
    if (!headerCells.length) return [];
    const fields = headerCells.map((c) =>
      matchHeaderField(c.innerText || c.textContent || '')
    );
    if (!fields.some(Boolean)) return [];
    let switchColIndex = fields.indexOf('planStatus');
    if (switchColIndex < 0) switchColIndex = null;
    const dataRows = [
      ...root.querySelectorAll(
        '[role="row"], .ant-table-tbody tr, tbody tr'
      )
    ].filter((r) => r.querySelectorAll('[role="cell"], td').length && !r.querySelector('[role="columnheader"]'));

    const results = [];
    for (const tr of dataRows) {
      const cells = [...tr.querySelectorAll('[role="cell"], td')];
      if (!cells.length) continue;
      const row = {};
      fields.forEach((field, i) => {
        if (!field || !cells[i]) return;
        if (field === 'planStatus') {
          row.planStatus = parseSwitchFromEl(cells[i]) || 'unknown';
          return;
        }
        row[field] = cleanText(cells[i].innerText || cells[i].textContent || '');
      });
      if (!row.planStatus) {
        row.planStatus = detectPlanStatusFromRow(tr, cells, switchColIndex);
      }
      if (Object.keys(row).length) results.push(row);
    }
    return results;
  }

  function scoreRows(rows) {
    if (!rows?.length) return 0;
    let score = rows.length;
    for (const r of rows.slice(0, 5)) {
      if (r.campaign) score += 2;
      if (r.spend != null && r.spend !== '') score += 2;
      if (r.roi != null && r.roi !== '') score += 2;
      if (r.revenue != null && r.revenue !== '') score += 2;
      if (r.orders != null && r.orders !== '') score += 1;
    }
    return score;
  }

  function scrapeTablesFromDocument(doc) {
    const candidates = [];
    for (const table of doc.querySelectorAll('table')) {
      const rows = parseHtmlTable(table);
      const score = scoreRows(rows);
      if (score > 0) candidates.push({ rows, score, source: 'html-table' });
    }
    for (const el of doc.querySelectorAll(
      '.ant-table, [class*="Table"], [role="table"], [class*="campaign"]'
    )) {
      const rows = parseRoleTable(el);
      const score = scoreRows(rows);
      if (score > 0) candidates.push({ rows, score, source: 'role-table' });
    }
    candidates.sort((a, b) => b.score - a.score);
    if (!candidates.length) return { rows: [], source: 'none' };
    return { rows: candidates[0].rows, source: candidates[0].source };
  }

  function detectStoreName(doc) {
    // 1) 广告面板「xxx 主要账号」
    const allTextEls = [...doc.querySelectorAll('div, span, h1, h2, h3, a, p')].slice(0, 400);
    for (const el of allTextEls) {
      const t = cleanText(el.innerText || '');
      if (!t || t.length > 120) continue;
      if (/主要账号|主账号|main account/i.test(t)) {
        const name = t
          .replace(/主要账号|主账号|main account/gi, '')
          .replace(/\s+/g, ' ')
          .trim();
        if (name.length >= 2 && name.length < 80) return name;
        const parent = cleanText(el.parentElement?.innerText || '');
        const m = parent.match(/([^\n]{2,80}?)\s*(主要账号|主账号)/);
        if (m) return cleanText(m[1]);
      }
    }

    // 2) 常见店铺名节点
    for (const el of doc.querySelectorAll(
      '[class*="shop-name"], [class*="store-name"], [class*="seller-name"], [class*="account-name"], [data-e2e*="shop"]'
    )) {
      const t = cleanText(el.innerText || '');
      if (t && t.length >= 2 && t.length < 80 && !/tiktok|seller center/i.test(t)) return t;
    }

    // 3) title 拆分
    const title = cleanText(doc.title || '');
    const parts = title.split(/[-|–—]/).map(cleanText).filter(Boolean);
    const skip = /tiktok|seller|ads|shop ads|campaign|dashboard|homepage|商家中心|广告/i;
    for (const p of parts) {
      if (!skip.test(p) && p.length > 1 && p.length < 80) return p;
    }

    // 4) 标签页 / 顶栏残留（紫鸟窗口名有时带店名）
    try {
      const bar = cleanText(doc.querySelector('title')?.textContent || '');
      if (bar && !skip.test(bar) && bar.length < 80) return bar;
    } catch (_) {
      /* ignore */
    }
    return '';
  }

  // —— API parse ——
  function flattenObject(obj, prefix = '', out = {}, depth = 0) {
    if (!obj || typeof obj !== 'object' || depth > 4) return out;
    for (const [k, v] of Object.entries(obj)) {
      const key = prefix ? `${prefix}.${k}` : k;
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        if (v.value != null) out[k] = v.value;
        flattenObject(v, key, out, depth + 1);
      } else if (!Array.isArray(v)) {
        out[k] = v;
        out[key] = v;
      }
    }
    return out;
  }

  function normalizeApiPlanStatus(v) {
    if (v == null || v === '') return null;
    if (typeof v === 'boolean') return v ? 'on' : 'off';
    if (typeof v === 'number') {
      if (v === 1) return 'on';
      if (v === 0) return 'off';
    }
    const s = String(v).trim().toLowerCase();
    if (/^(on|1|true|enable|enabled|open|active|running)$/i.test(s)) return 'on';
    if (/^(off|0|false|disable|disabled|close|closed|paused|inactive)$/i.test(s)) return 'off';
    return null;
  }

  function extractRow(obj) {
    const flat = flattenObject(obj);
    const row = {};
    for (const [field, keys] of Object.entries(KEY_MAP)) {
      for (const k of keys) {
        if (flat[k] != null && flat[k] !== '') {
          if (field === 'campaign') row[field] = cleanText(flat[k]);
          else if (field === 'planStatus') {
            row[field] = normalizeApiPlanStatus(flat[k]) || flat[k];
          } else row[field] = parseNumber(flat[k]) ?? flat[k];
          break;
        }
      }
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

  function looksLikeReportRows(objs) {
    let hits = 0;
    for (const o of objs.slice(0, 5)) {
      const keys = Object.keys(o).join(' ').toLowerCase();
      if (/campaign|spend|cost|roi|roas|gmv|revenue|order|name/.test(keys)) hits += 1;
      if (o.metrics || o.stats || o.stat) hits += 1;
    }
    return hits >= 1;
  }

  function findArrayOfObjects(data, depth = 0) {
    if (depth > 8 || data == null) return [];
    if (Array.isArray(data)) {
      const objs = data.filter((x) => x && typeof x === 'object' && !Array.isArray(x));
      if (objs.length >= 1 && looksLikeReportRows(objs)) return objs;
      for (const item of data.slice(0, 20)) {
        const found = findArrayOfObjects(item, depth + 1);
        if (found.length) return found;
      }
      return objs.length >= 1 ? objs : [];
    }
    if (typeof data === 'object') {
      const prefer = ['list', 'rows', 'data', 'items', 'records', 'campaigns', 'result', 'table'];
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

  function parseApiPayload(payload) {
    let data = payload;
    if (typeof payload === 'string') {
      try {
        data = JSON.parse(payload);
      } catch {
        return [];
      }
    }
    const list = findArrayOfObjects(data);
    const rows = [];
    for (const item of list) {
      const row = extractRow(item);
      if (row.campaign || row.spend != null || row.revenue != null) rows.push(row);
    }
    return rows;
  }

  function injectHook() {
    try {
      const s = document.createElement('script');
      s.src = chrome.runtime.getURL('content/inject-fetch-hook.js');
      s.onload = () => s.remove();
      (document.documentElement || document.head).appendChild(s);
    } catch (e) {
      console.warn('[TK-Ad] inject hook failed', e);
    }
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== 'tk-ad-scraper-hook' || data.type !== 'API_PAYLOAD') return;
    apiCache.unshift({ url: data.url, body: data.body, at: Date.now() });
    if (apiCache.length > API_CACHE_MAX) apiCache.length = API_CACHE_MAX;
  });

  function waitForTable(timeoutMs = 8000) {
    return new Promise((resolve) => {
      const start = Date.now();
      const tick = () => {
        const { rows, source } = scrapeTablesFromDocument(document);
        if (rows.length || Date.now() - start > timeoutMs) {
          resolve({ rows, source });
          return;
        }
        setTimeout(tick, 400);
      };
      tick();
    });
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function pad2(n) {
    return (n < 10 ? '0' : '') + n;
  }

  function formatYmd(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

  function parseRangeFromText(text) {
    const t = cleanText(text);
    const m = t.match(
      /(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})\s*[-–~至到]\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})/
    );
    if (!m) return null;
    const norm = (s) => {
      const p = s.replace(/\//g, '-').split('-');
      return `${p[0]}-${pad2(Number(p[1]))}-${pad2(Number(p[2]))}`;
    };
    return { start: norm(m[1]), end: norm(m[2]), raw: m[0] };
  }

  function isVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    const st = window.getComputedStyle(el);
    if (!st || st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) {
      return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function clickEl(el) {
    if (!el) return false;
    try {
      el.scrollIntoView({ block: 'center', inline: 'center' });
    } catch {
      /* ignore */
    }
    const opts = { bubbles: true, cancelable: true, view: window };
    try {
      el.dispatchEvent(new MouseEvent('mousedown', opts));
      el.dispatchEvent(new MouseEvent('mouseup', opts));
      el.dispatchEvent(new MouseEvent('click', opts));
    } catch {
      try {
        el.click();
      } catch {
        return false;
      }
    }
    return true;
  }

  function readDisplayedRange() {
    const nodes = document.querySelectorAll('input, button, div, span, p, a');
    let best = null;
    for (let i = 0; i < nodes.length && i < 5000; i++) {
      const el = nodes[i];
      if (!isVisible(el)) continue;
      let text = '';
      if (el.tagName === 'INPUT') text = el.value || el.getAttribute('placeholder') || '';
      else text = el.innerText || el.textContent || '';
      text = cleanText(text).slice(0, 80);
      const rg = parseRangeFromText(text);
      if (!rg) continue;
      const r = el.getBoundingClientRect();
      if (r.top > window.innerHeight * 0.55) continue;
      best = { el, range: rg, text };
      if (el.tagName === 'INPUT' || /picker|date|calendar|range/i.test(el.className || '')) break;
    }
    return best;
  }

  function findDateTrigger() {
    const shown = readDisplayedRange();
    if (shown?.el) {
      let cur = shown.el;
      for (let d = 0; d < 6 && cur; d++) {
        if (
          cur.matches?.(
            'button, [role="button"], input, .arco-picker, .arco-picker-range, [class*="picker"], [class*="Picker"], [class*="date"], [class*="Date"]'
          )
        ) {
          return { el: cur, range: shown.range, via: 'range-text' };
        }
        cur = cur.parentElement;
      }
      return { el: shown.el, range: shown.range, via: 'range-text' };
    }
    const sels = [
      '.arco-picker-range',
      '.arco-picker',
      '[class*="RangePicker"]',
      '[class*="range-picker"]',
      'input[placeholder*="日期"]',
      'input[placeholder*="Date"]'
    ];
    for (const sel of sels) {
      for (const el of document.querySelectorAll(sel)) {
        if (isVisible(el)) return { el, range: null, via: sel };
      }
    }
    return null;
  }

  function findShortcut(labels) {
    const nodes = document.querySelectorAll(
      'button, a, li, div, span, [role="button"], [role="option"], [role="menuitem"]'
    );
    const candidates = [];
    for (let i = 0; i < nodes.length && i < 8000; i++) {
      const el = nodes[i];
      if (!isVisible(el)) continue;
      const t = cleanText(el.innerText || el.textContent || '');
      if (!t || t.length > 20) continue;
      for (const lab of labels) {
        if (t === lab || t.toLowerCase() === String(lab).toLowerCase()) {
          candidates.push({ el, text: t, exact: true });
          break;
        }
      }
    }
    if (!candidates.length) {
      for (let i = 0; i < nodes.length && i < 8000; i++) {
        const el = nodes[i];
        if (!isVisible(el)) continue;
        const t = cleanText(el.innerText || el.textContent || '');
        if (!t || t.length > 20) continue;
        for (const lab of labels) {
          if (t.includes(lab) || t.toLowerCase().includes(String(lab).toLowerCase())) {
            candidates.push({ el, text: t, exact: false });
            break;
          }
        }
      }
    }
    if (!candidates.length) return null;
    candidates.sort(
      (a, b) => (b.exact ? 1 : 0) - (a.exact ? 1 : 0) || a.text.length - b.text.length
    );
    return candidates[0];
  }

  function panelOpen() {
    const panelSels = [
      '.arco-picker-container',
      '.arco-trigger-popup',
      '[class*="picker-container"]',
      '[class*="PickerDropdown"]',
      '[class*="datepicker"]'
    ];
    for (const sel of panelSels) {
      for (const el of document.querySelectorAll(sel)) {
        if (isVisible(el)) return true;
      }
    }
    return !!findShortcut(['今天', '昨天', '近7天', 'Today', 'Yesterday', 'Last 7 days']);
  }

  /**
   * 按业务时区（默认 Europe/London）得到 YYYY-MM-DD，避免中国本地日历日错位。
   * @param {Date} [date]
   * @param {string} [timeZone]
   */
  function formatYmdInTz(date = new Date(), timeZone = 'Europe/London') {
    try {
      return new Intl.DateTimeFormat('en-CA', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }).format(date);
    } catch {
      return formatYmd(date);
    }
  }

  function shiftYmd(ymd, deltaDays) {
    const [y, m, d] = String(ymd).split('-').map(Number);
    const utc = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
    utc.setUTCDate(utc.getUTCDate() + deltaDays);
    return `${utc.getUTCFullYear()}-${String(utc.getUTCMonth() + 1).padStart(2, '0')}-${String(utc.getUTCDate()).padStart(2, '0')}`;
  }

  /**
   * 广告数据面板默认常为近 7 天；按 dateMode 点快捷项（昨天/今天）。
   * 目标日期按 bizTimeZone（英区后台），不是浏览器本地时区。
   * @param {'yesterday'|'today'|string} mode
   * @param {{ bizTimeZone?: string }} [opts]
   */
  async function setPageDateRange(mode = 'yesterday', opts = {}) {
    let m = String(mode || 'yesterday').toLowerCase();
    if (m !== 'today' && m !== 'yesterday') m = 'yesterday';
    const tz = opts.bizTimeZone || 'Europe/London';
    const todayStr = formatYmdInTz(new Date(), tz);
    const target =
      m === 'today'
        ? { start: todayStr, end: todayStr, labels: ['今天', '今日', 'Today', 'today'] }
        : {
            start: shiftYmd(todayStr, -1),
            end: shiftYmd(todayStr, -1),
            labels: ['昨天', '昨日', 'Yesterday', 'yesterday']
          };

    const before = readDisplayedRange();
    const beforeRange = before?.range || null;
    if (
      beforeRange &&
      beforeRange.start === target.start &&
      beforeRange.end === target.end
    ) {
      return {
        ok: true,
        skipped: true,
        mode: m,
        before: beforeRange,
        after: beforeRange,
        message: 'already on target range'
      };
    }

    const trigger = findDateTrigger();
    if (!trigger?.el) {
      return {
        ok: false,
        mode: m,
        before: beforeRange,
        error: '未找到日期选择器'
      };
    }

    clickEl(trigger.el);
    await sleep(450);
    if (!panelOpen() && trigger.el.parentElement) {
      clickEl(trigger.el.parentElement);
      await sleep(450);
    }

    const sc = findShortcut(target.labels);
    if (!sc) {
      return {
        ok: false,
        mode: m,
        before: beforeRange,
        panelOpen: panelOpen(),
        error: `未找到快捷项: ${target.labels.join('/')}`
      };
    }

    clickEl(sc.el);
    await sleep(900);
    const applyBtns = findShortcut(['确定', '应用', 'Apply', 'OK', '确认', 'Done']);
    if (applyBtns && /确定|应用|Apply|OK|确认|Done/i.test(applyBtns.text)) {
      clickEl(applyBtns.el);
      await sleep(600);
    }

    let after = null;
    for (let w = 0; w < 20; w++) {
      await sleep(400);
      after = readDisplayedRange()?.range || null;
      if (after && after.start === target.start && after.end === target.end) break;
      if (
        after &&
        beforeRange &&
        (after.start !== beforeRange.start || after.end !== beforeRange.end)
      ) {
        break;
      }
    }

    const matched = !!(after && after.start === target.start && after.end === target.end);
    const changed = !!(
      after &&
      beforeRange &&
      (after.start !== beforeRange.start || after.end !== beforeRange.end)
    );
    return {
      ok: matched || changed,
      skipped: false,
      mode: m,
      clicked: sc.text,
      before: beforeRange,
      after,
      target: { start: target.start, end: target.end },
      error: matched || changed ? null : `点击「${sc.text}」后日期未变为目标区间`
    };
  }

  async function scrapePage(options = {}) {
    const waitMs = options.waitMs ?? 8000;
    let dateMode = options.dateMode || 'yesterday';
    const setDate = options.setPageDateRange !== false;
    const bizTimeZone = options.bizTimeZone || 'Europe/London';
    const minUkHourForToday = options.minUkHourForToday ?? 20;
    let dateRangeMeta = null;

    // 防早抓：dateMode=today 且英国时未到 minUkHourForToday → 改 yesterday
    // 中国早上 8 点 ≈ 英国 0 点，此时「今天」花费几乎为空
    if (String(dateMode).toLowerCase() === 'today') {
      try {
        const ukHour = Number(
          new Intl.DateTimeFormat('en-GB', {
            timeZone: bizTimeZone,
            hour: 'numeric',
            hour12: false
          }).format(new Date())
        );
        if (Number.isFinite(ukHour) && ukHour < minUkHourForToday) {
          console.warn(
            `[TK-Ad] dateMode=today but UK hour=${ukHour} < ${minUkHourForToday}; force yesterday`
          );
          dateMode = 'yesterday';
        }
      } catch (e) {
        console.warn('[TK-Ad] UK hour check failed', e);
      }
    }

    if (setDate) {
      try {
        dateRangeMeta = await setPageDateRange(dateMode, { bizTimeZone });
        if (dateRangeMeta?.ok && !dateRangeMeta.skipped) {
          // 等表格按新日期重载
          await sleep(options.waitAfterDateChangeMs ?? 5000);
        }
      } catch (e) {
        dateRangeMeta = { ok: false, error: String(e.message || e) };
        console.warn('[TK-Ad] setPageDateRange failed', e);
      }
    }

    let { rows, source } = await waitForTable(waitMs);

    // API 兜底 / 补充
    let apiRows = [];
    for (const item of apiCache) {
      const parsed = parseApiPayload(item.body);
      if (parsed.length > apiRows.length) {
        apiRows = parsed;
        source = source === 'none' ? 'api' : `${source}+api`;
      }
    }

    // 若 DOM 很弱而 API 更强，用 API
    if (scoreRows(apiRows) > scoreRows(rows)) {
      rows = apiRows;
      source = 'api';
    } else if (!rows.length && apiRows.length) {
      rows = apiRows;
      source = 'api';
    }

    const storeName = detectStoreName(document);
    const loginHint =
      /login|sign in|登录/i.test(document.body?.innerText?.slice(0, 500) || '') &&
      !rows.length;

    // 金额单位：与广告后台一致默认美金；从单元格文本识别 $ / £ 等
    const currencyHits = { USD: 0, GBP: 0, EUR: 0, CNY: 0 };
    for (const r of rows.slice(0, 30)) {
      for (const key of ['spend', 'revenue']) {
        const cur = detectCurrency(r[key]);
        if (cur && currencyHits[cur] != null) currencyHits[cur] += 1;
      }
    }
    let pageCurrency = 'USD';
    let maxHit = 0;
    for (const k of Object.keys(currencyHits)) {
      if (currencyHits[k] > maxHit) {
        maxHit = currencyHits[k];
        pageCurrency = k;
      }
    }

    return {
      ok: rows.length > 0,
      error: rows.length
        ? null
        : loginHint
          ? '页面可能未登录或未打开广告数据列表'
          : '未识别到广告数据表格，请打开广告系列/报表列表页后重试',
      rawRows: rows,
      source,
      currency: pageCurrency,
      storeName,
      pageTitle: document.title,
      url: location.href,
      apiCacheSize: apiCache.length,
      scrapedAt: new Date().toISOString(),
      dateRange: dateRangeMeta
    };
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || !msg.type) return;

    if (msg.type === 'PING') {
      sendResponse({ ok: true, url: location.href });
      return;
    }

    if (msg.type === 'SCRAPE_PAGE') {
      scrapePage(msg.options || {})
        .then((result) => sendResponse(result))
        .catch((e) =>
          sendResponse({
            ok: false,
            error: String(e.message || e),
            rawRows: [],
            url: location.href
          })
        );
      return true; // async
    }
  });

  injectHook();
  console.log('[TK-Ad] content script ready', location.href);
})();
