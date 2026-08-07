/* TikTok ads dashboard scraper for ziniao-cli page exec. No // comments (minified to one line). */
(function () {
  function cleanText(t) {
    return String(t ?? '')
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

  const HEADER_ALIASES = {
    planStatus: ['开关', '投放开关', 'enable', 'enabled', 'switch', 'on/off', 'toggle'],
    campaign: [
      '品名',
      '广告计划名称',
      '广告系列',
      '广告系列名称',
      '系列名称',
      'campaign',
      'campaign name',
      'product',
      '名称'
    ],
    spend: ['广告花费', '广告成本', '花费', '成本', '消耗', 'cost', 'spend', 'ad spend'],
    orders: [
      '销量',
      '订单',
      'sku 订单',
      'sku订单',
      'sku 订单数',
      'sku订单数',
      'orders',
      'units',
      'units sold'
    ],
    roi: ['roi', 'roas', '投资回报率', '投资回报', '回报率'],
    revenue: ['销售额', '总收入', '销售收入', '收入', 'gmv', 'revenue', 'gross revenue']
  };

  function matchHeaderField(headerText) {
    const t = cleanText(headerText).toLowerCase();
    if (!t) return null;
    const order = ['planStatus', 'roi', 'spend', 'orders', 'revenue', 'campaign'];
    for (const field of order) {
      for (const a of HEADER_ALIASES[field]) {
        const al = a.toLowerCase();
        if (!(t === al || t.includes(al) || (al.length >= 2 && al.includes(t)))) continue;
        if (field === 'spend' && /平均下单|cost per|per order|\bcpc\b|\bcpa\b/.test(t)) continue;
        if (field === 'planStatus') {
          if (/投放状态|计划状态|delivery|operation status/.test(t)) return field;
          if (t === al || t === '开关' || t === 'switch' || t === 'enable' || t === 'enabled') {
            return field;
          }
          if (/开关|switch|toggle|on\/off/.test(t) && t.length <= 12) return field;
          continue;
        }
        if (field === 'campaign' && (al === '名称' || al === 'name')) {
          if (!/系列|campaign|广告|活动|product|品名|计划/.test(t) && t !== '名称' && t !== 'name') {
            continue;
          }
        }
        return field;
      }
    }
    return null;
  }

  function classOf(el) {
    if (!el) return '';
    return String(el.className || (el.getAttribute && el.getAttribute('class')) || '');
  }

  function readSwitchState(sw) {
    if (!sw) return null;
    const aria = sw.getAttribute && sw.getAttribute('aria-checked');
    if (aria === 'true') return 'on';
    if (aria === 'false') return 'off';
    if (sw.tagName === 'INPUT') {
      if (sw.type === 'checkbox' || sw.getAttribute('role') === 'switch') {
        return sw.checked ? 'on' : 'off';
      }
    }
    const cls =
      classOf(sw) +
      ' ' +
      classOf(sw.parentElement) +
      ' ' +
      classOf(sw.parentElement && sw.parentElement.parentElement);
    if (
      /\b(checked|is-checked|switch-checked|arco-switch-checked|ant-switch-checked|is-on|switch_on|switch-on|isOpen|is-open)\b/i.test(
        cls
      )
    ) {
      return 'on';
    }
    if (
      /\b(unchecked|is-unchecked|is-off|switch_off|switch-off|isClose|is-close)\b/i.test(cls)
    ) {
      return 'off';
    }
    const ds = (sw.getAttribute && sw.getAttribute('data-state')) || '';
    if (ds === 'checked' || ds === 'on' || ds === 'open') return 'on';
    if (ds === 'unchecked' || ds === 'off' || ds === 'closed') return 'off';
    const dc = sw.getAttribute && sw.getAttribute('data-checked');
    if (dc === 'true' || dc === '1') return 'on';
    if (dc === 'false' || dc === '0') return 'off';
    // Arco / custom: child handle position sometimes only style; treat presence of
    // green-ish inline style as weak signal (skip if ambiguous)
    return null;
  }

  function parseSwitchFromEl(el) {
    if (!el) return null;
    if (el.nodeType !== 1) return null;

    // Self is switch-like
    let st = null;
    if (
      el.matches &&
      el.matches(
        '[role="switch"], input[type="checkbox"], button[aria-checked], [aria-checked="true"], [aria-checked="false"], .arco-switch, .ant-switch, [class*="switch"], [class*="Switch"]'
      )
    ) {
      st = readSwitchState(el);
      if (st) return st;
    }

    // Prefer explicit switch nodes inside
    const candidates = el.querySelectorAll
      ? el.querySelectorAll(
          '[role="switch"], input[type="checkbox"], button[aria-checked], [aria-checked="true"], [aria-checked="false"], .arco-switch, .ant-switch, [class*="arco-switch"], [class*="ant-switch"], [class*="Switch"], [class*="switch"], [data-testid*="switch"], [data-e2e*="switch"]'
        )
      : [];
    for (let i = 0; i < candidates.length; i++) {
      st = readSwitchState(candidates[i]);
      if (st) return st;
      // checkbox without aria: use checked property
      const c = candidates[i];
      if (c.tagName === 'INPUT' && c.type === 'checkbox') {
        return c.checked ? 'on' : 'off';
      }
      // role=switch without aria-checked still use class/default off
      if (c.getAttribute && c.getAttribute('role') === 'switch') {
        st = readSwitchState(c);
        if (st) return st;
        // last resort: assume off if no checked class
        return 'off';
      }
    }

    const text = cleanText((el.innerText || el.textContent || '').slice(0, 40));
    if (/^(开|开启|on|enable|enabled|投放中|投放|开启中)$/i.test(text)) return 'on';
    if (/^(关|关闭|off|disable|disabled|已关闭|暂停|关闭中)$/i.test(text)) return 'off';
    return null;
  }

  function listPageSwitches(root) {
    root = root || document;
    const sel =
      '[role="switch"], input[type="checkbox"], button[aria-checked], .arco-switch, .ant-switch, [class*="arco-switch"], [class*="ant-switch"], [data-testid*="switch"], [data-e2e*="switch"]';
    const raw = [...root.querySelectorAll(sel)];
    // Drop nested duplicates (keep outermost switch widget)
    const filtered = [];
    for (const n of raw) {
      if (raw.some((o) => o !== n && o.contains(n))) continue;
      // Skip filter/header toolbars far above tables when possible later
      filtered.push(n);
    }
    return filtered;
  }

  function findStatusByCampaignName(campaign) {
    const name = cleanText(campaign);
    if (!name || name.length < 1) return null;
    // Search compact text nodes / cells that equal or start with campaign name
    const nodes = [...document.querySelectorAll('td, th, div, span, a, p')].slice(0, 4000);
    for (const node of nodes) {
      const t = cleanText(node.innerText || node.textContent || '');
      if (!t || t.length > 120) continue;
      if (t !== name && !t.startsWith(name) && !name.startsWith(t)) continue;
      // Walk up a few levels; fixed-column tables often share a virtual row wrapper
      let cur = node;
      for (let d = 0; d < 8 && cur; d++) {
        const s = parseSwitchFromEl(cur);
        if (s) return s;
        // previous siblings (switch column left of name)
        let sib = cur.previousElementSibling;
        let steps = 0;
        while (sib && steps < 4) {
          const ss = parseSwitchFromEl(sib);
          if (ss) return ss;
          sib = sib.previousElementSibling;
          steps++;
        }
        cur = cur.parentElement;
      }
    }
    return null;
  }

  function detectPlanStatusFromRow(tr, cells, switchColIndex, rowIndex, pageSwitches) {
    if (switchColIndex != null && cells[switchColIndex]) {
      const s = parseSwitchFromEl(cells[switchColIndex]);
      if (s) return s;
    }
    for (let i = 0; i < cells.length; i++) {
      const s = parseSwitchFromEl(cells[i]);
      if (s) return s;
    }
    const sTr = parseSwitchFromEl(tr);
    if (sTr) return sTr;

    // Fixed-column layout: switch lives in another table; pair by body row index
    if (pageSwitches && pageSwitches.length && rowIndex != null) {
      // Prefer switches whose vertical position is close to this tr
      try {
        const trRect = tr.getBoundingClientRect && tr.getBoundingClientRect();
        if (trRect && trRect.height > 0) {
          let best = null;
          let bestDist = 1e9;
          for (const sw of pageSwitches) {
            const r = sw.getBoundingClientRect && sw.getBoundingClientRect();
            if (!r || r.height <= 0) continue;
            const dist = Math.abs(r.top + r.height / 2 - (trRect.top + trRect.height / 2));
            if (dist < bestDist) {
              bestDist = dist;
              best = sw;
            }
          }
          // Same row roughly within 28px center distance
          if (best && bestDist <= 28) {
            const st = readSwitchState(best) || parseSwitchFromEl(best.parentElement || best);
            if (st) return st;
            if (best.tagName === 'INPUT') return best.checked ? 'on' : 'off';
            if (best.getAttribute('role') === 'switch') {
              const a = best.getAttribute('aria-checked');
              if (a === 'true') return 'on';
              if (a === 'false') return 'off';
            }
          }
        }
      } catch (e) {
        /* ignore geometry errors */
      }
      if (pageSwitches[rowIndex]) {
        const st =
          readSwitchState(pageSwitches[rowIndex]) ||
          parseSwitchFromEl(pageSwitches[rowIndex].parentElement || pageSwitches[rowIndex]);
        if (st) return st;
      }
    }
    return 'unknown';
  }

  function parseHtmlTable(table, pageSwitches) {
    let headerRow = table.querySelector('thead tr') || table.querySelector('tr');
    if (!headerRow) return { rows: [], currencyHits: {}, trs: [] };
    const headerCells = [...headerRow.querySelectorAll('th, td')];
    const fields = headerCells.map((c) => matchHeaderField(c.innerText || ''));
    if (!fields.some(Boolean)) return { rows: [], currencyHits: {}, trs: [] };
    let switchColIndex = fields.indexOf('planStatus');
    if (switchColIndex < 0) switchColIndex = null;
    const bodyRows = table.querySelectorAll('tbody tr');
    const trList = bodyRows.length ? [...bodyRows] : [...table.querySelectorAll('tr')].slice(1);
    const results = [];
    const usedTrs = [];
    const currencyHits = { USD: 0, GBP: 0, EUR: 0, CNY: 0 };
    let dataIdx = 0;
    for (const tr of trList) {
      const cells = [...tr.querySelectorAll('td, th')];
      if (!cells.length) continue;
      const row = {};
      fields.forEach((field, i) => {
        if (!field || !cells[i]) return;
        if (field === 'planStatus') {
          row.planStatus = parseSwitchFromEl(cells[i]) || 'unknown';
          return;
        }
        const text = cleanText(cells[i].innerText || '');
        if (field === 'campaign') {
          row[field] = text;
          return;
        }
        if (field === 'spend' || field === 'revenue') {
          const cur = detectCurrency(text);
          if (cur && currencyHits[cur] != null) currencyHits[cur] += 1;
        }
        row[field] = parseNumber(text) ?? text;
      });
      if (!row.campaign && row.spend == null && row.revenue == null) continue;
      if (!row.planStatus || row.planStatus === 'unknown') {
        row.planStatus = detectPlanStatusFromRow(
          tr,
          cells,
          switchColIndex,
          dataIdx,
          pageSwitches
        );
      }
      if ((!row.planStatus || row.planStatus === 'unknown') && row.campaign) {
        const byName = findStatusByCampaignName(row.campaign);
        if (byName) row.planStatus = byName;
      }
      if (!row.planStatus) row.planStatus = 'unknown';
      results.push(row);
      usedTrs.push(tr);
      dataIdx++;
    }
    return { rows: results, currencyHits, trs: usedTrs };
  }

  function scoreRows(rows) {
    if (!rows || !rows.length) return 0;
    let s = rows.length;
    for (const r of rows.slice(0, 5)) {
      if (r.campaign) s += 2;
      if (r.spend != null && r.spend !== '') s += 2;
      if (r.roi != null) s += 2;
      if (r.revenue != null) s += 2;
      if (r.planStatus && r.planStatus !== 'unknown') s += 1;
    }
    return s;
  }

  function pickCurrency(hits) {
    let best = null;
    let n = 0;
    for (const k of Object.keys(hits || {})) {
      if (hits[k] > n) {
        n = hits[k];
        best = k;
      }
    }
    return best;
  }

  function detectPageCurrencyHint() {
    const bodyText = cleanText((document.body && document.body.innerText) || '').slice(0, 8000);
    if (/货币|currency|展示币种|金额单位/i.test(bodyText)) {
      const m = bodyText.match(
        /(?:货币|currency|展示币种|金额单位)\s*[:：]?\s*(USD|GBP|EUR|CNY|美金|美元|英镑|欧元)/i
      );
      if (m) {
        const t = m[1].toUpperCase();
        if (t === '美金' || t === '美元') return 'USD';
        if (t === '英镑') return 'GBP';
        if (t === '欧元') return 'EUR';
        return t;
      }
    }
    const sample = bodyText.slice(0, 3000);
    const counts = {
      USD: (sample.match(/\$|USD|美金|美元/gi) || []).length,
      GBP: (sample.match(/£|GBP|英镑/gi) || []).length,
      EUR: (sample.match(/€|EUR|欧元/gi) || []).length
    };
    return pickCurrency(counts);
  }

  const pageSwitches = listPageSwitches(document);
  let best = [];
  let bestHits = {};
  let source = 'none';
  let switchProbe = {
    pageSwitchCount: pageSwitches.length,
    sample: []
  };
  for (let i = 0; i < Math.min(pageSwitches.length, 5); i++) {
    const sw = pageSwitches[i];
    switchProbe.sample.push({
      tag: sw.tagName,
      role: sw.getAttribute('role'),
      aria: sw.getAttribute('aria-checked'),
      cls: classOf(sw).slice(0, 80),
      state: readSwitchState(sw)
    });
  }

  for (const table of document.querySelectorAll('table')) {
    const parsed = parseHtmlTable(table, pageSwitches);
    if (scoreRows(parsed.rows) > scoreRows(best)) {
      best = parsed.rows;
      bestHits = parsed.currencyHits || {};
      source = 'html-table';
    }
  }

  best = best.filter(function (r) {
    const c = cleanText(r.campaign || '').toLowerCase();
    if (!c) return false;
    if (['total', '合计', '总计', '汇总', 'summary', 'all'].indexOf(c) >= 0) return false;
    return true;
  });

  // Second pass: if still all unknown but switch count matches row count, force index pair
  const unknownCount = best.filter(function (r) {
    return !r.planStatus || r.planStatus === 'unknown';
  }).length;
  if (unknownCount > 0 && pageSwitches.length >= best.length && best.length > 0) {
    for (let i = 0; i < best.length; i++) {
      if (best[i].planStatus && best[i].planStatus !== 'unknown') continue;
      const sw = pageSwitches[i];
      if (!sw) continue;
      const st = readSwitchState(sw) || parseSwitchFromEl(sw.parentElement || sw);
      if (st) best[i].planStatus = st;
      else if (sw.tagName === 'INPUT') best[i].planStatus = sw.checked ? 'on' : 'off';
      else if (sw.getAttribute('aria-checked') === 'true') best[i].planStatus = 'on';
      else if (sw.getAttribute('aria-checked') === 'false') best[i].planStatus = 'off';
    }
  }

  let storeHint = '';
  var els = document.querySelectorAll('div, span, h1, h2');
  for (var i = 0; i < els.length && i < 300; i++) {
    const t = cleanText(els[i].innerText || '');
    if (t.length > 5 && t.length < 100 && /主要账号|主账号/.test(t)) {
      storeHint = t.replace(/主要账号|主账号/g, '').trim();
      break;
    }
  }

  const cellCurrency = pickCurrency(bestHits);
  const pageCurrency = cellCurrency || detectPageCurrencyHint() || 'USD';
  const knownStatus = best.filter(function (r) {
    return r.planStatus === 'on' || r.planStatus === 'off';
  }).length;

  return JSON.stringify({
    ok: best.length > 0,
    source: source,
    storeHint: storeHint,
    currency: pageCurrency,
    currencyHits: bestHits,
    url: location.href,
    title: document.title,
    rows: best,
    switchProbe: switchProbe,
    planStatusKnown: knownStatus,
    error: best.length ? null : '未识别到广告表格，请确认已进入广告数据面板'
  });
})();
