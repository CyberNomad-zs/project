/* TikTok finance / settlement daily snapshot (P3b). Heuristic DOM scrape. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function detectCurrency(text) {
    var s = String(text || '');
    if (/[£]|GBP/i.test(s)) return 'GBP';
    if (/[€]|EUR/i.test(s)) return 'EUR';
    if (/[¥￥]|CNY|RMB/i.test(s) && !/\$/.test(s)) return 'CNY';
    if (/\$|USD/i.test(s)) return 'USD';
    return null;
  }
  function parseNumber(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && isFinite(value)) return value;
    var s = String(value).trim();
    if (!s || s === '-' || s === '—') return null;
    s = s.replace(/[,\s]/g, '').replace(/[¥$€£￥]/g, '');
    s = s.replace(/USD|GBP|EUR|CNY|RMB/gi, '').replace(/%/g, '');
    var n = Number(s);
    return isFinite(n) ? n : null;
  }
  function walkTexts(limit) {
    var out = [];
    var nodes = document.querySelectorAll('div,span,p,li,td,th,h1,h2,h3,strong,label');
    for (var i = 0; i < nodes.length && out.length < limit; i++) {
      var el = nodes[i];
      if (el.children && el.children.length > 4) continue;
      var t = clean(el.textContent);
      if (!t || t.length < 2 || t.length > 100) continue;
      out.push(t);
    }
    return out;
  }
  function findNear(labels) {
    var texts = walkTexts(500);
    for (var i = 0; i < texts.length; i++) {
      var low = texts[i].toLowerCase();
      var hit = false;
      for (var j = 0; j < labels.length; j++) {
        if (low.indexOf(String(labels[j]).toLowerCase()) >= 0) { hit = true; break; }
      }
      if (!hit) continue;
      var n = parseNumber(texts[i]);
      if (n != null) return { value: n, label: texts[i] };
      for (var k = 1; k <= 3 && i + k < texts.length; k++) {
        n = parseNumber(texts[i + k]);
        if (n != null) return { value: n, label: texts[i] + ' → ' + texts[i + k] };
      }
    }
    return null;
  }
  try {
    var settled = findNear(['已结算', '结算金额', 'Settled', 'Settlement', 'Payable', '可结算']);
    var pending = findNear(['待结算', '处理中', 'Pending', 'In process', '未结算']);
    var refund = findNear(['退款', 'Refund', '退货金额']);
    var bodyCur = detectCurrency(document.body ? document.body.innerText.slice(0, 2500) : '');
    var ok = !!(settled || pending || refund);
    return JSON.stringify({
      ok: ok,
      module: 'finance_daily',
      source: 'dom-labels',
      url: location.href || '',
      title: document.title || '',
      currency: bodyCur || 'GBP',
      settlementAmount: settled ? settled.value : null,
      pendingAmount: pending ? pending.value : null,
      refundAmount: refund ? refund.value : null,
      raw: {
        settled: settled && settled.label,
        pending: pending && pending.label,
        refund: refund && refund.label
      },
      error: ok ? null : 'no finance metrics found. url=' + (location.href || '')
    });
  } catch (e) {
    return JSON.stringify({
      ok: false, module: 'finance_daily', url: location.href || '', error: String(e && e.message ? e.message : e)
    });
  }
})();
