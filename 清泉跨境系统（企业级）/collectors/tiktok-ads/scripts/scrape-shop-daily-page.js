/* TikTok shop daily KPI from seller homepage (近 N 天卡片).
 * Preferred URL: /homepage — compass/data-overview often stays on Key metrics placeholders.
 */
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
    var m = s.match(/-?\s*[¥$€£￥]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)/);
    if (m) {
      var n0 = Number(String(m[1]).replace(/,/g, ''));
      if (isFinite(n0)) return n0;
    }
    s = s.replace(/[,\s]/g, '').replace(/[¥$€£￥]/g, '').replace(/%/g, '');
    var n = Number(s);
    return isFinite(n) ? n : null;
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function findByRegex(body, patterns) {
    for (var i = 0; i < patterns.length; i++) {
      var m = body.match(patterns[i]);
      if (!m) continue;
      var raw = m[1] != null ? m[1] : m[0];
      var n = parseNumber(raw);
      if (n != null) return { value: n, label: String(m[0]).slice(0, 100) };
    }
    return null;
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    // Homepage cards: GMV £5,295.27 / 客户数 423 / SKU 订单数 430 / 访客数 10,037
    var gmv =
      findByRegex(body, [
        /GMV\s*([£$€][\d,]+\.?\d*)/i,
        /成交额\s*([£$€]?[\d,]+\.?\d*)/,
        /销售额\s*([£$€]?[\d,]+\.?\d*)/
      ]);
    var orders =
      findByRegex(body, [
        /SKU\s*订单数\s*([\d,]+)/i,
        /订单数\s*([\d,]+)/,
        /Paid\s*orders?\s*([\d,]+)/i,
        /Orders?\s*([\d,]+)/i
      ]);
    var buyers =
      findByRegex(body, [
        /客户数\s*([\d,]+)/,
        /买家数\s*([\d,]+)/,
        /Buyers?\s*([\d,]+)/i,
        /Customers?\s*([\d,]+)/i
      ]);
    var visitors =
      findByRegex(body, [
        /访客数\s*([\d,]+)/,
        /Visitors?\s*([\d,]+)/i
      ]);
    var refund =
      findByRegex(body, [
        /退款金额\s*([£$€\-]?[\d,]+\.?\d*)/,
        /Refund\s*([£$€\-]?[\d,]+\.?\d*)/i
      ]);
    var windowLabel = null;
    var wm = body.match(/近\s*\d+\s*天/) || body.match(/Last\s*\d+\s*days?/i) || body.match(/更新日期[：:]\s*[^\s]+/);
    if (wm) windowLabel = wm[0];

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 240),
      window: windowLabel,
      visitors: visitors ? visitors.value : null
    };
    if (gmv) raw.gmvHit = gmv.label;
    if (orders) raw.ordersHit = orders.label;
    if (buyers) raw.buyersHit = buyers.label;

    var ok = !!(gmv || orders || buyers);
    if (!ok) {
      return JSON.stringify({
        ok: false,
        module: 'shop_daily',
        source: 'homepage-cards',
        url: url,
        title: document.title || '',
        raw: raw,
        error: 'no homepage KPI cards. url=' + url
      });
    }
    return JSON.stringify({
      ok: true,
      module: 'shop_daily',
      source: 'homepage-cards',
      url: url,
      title: document.title || '',
      currency: detectCurrency(body) || 'GBP',
      gmv: gmv ? gmv.value : null,
      ordersCnt: orders ? orders.value : null,
      buyersCnt: buyers ? buyers.value : null,
      refundAmount: refund ? refund.value : null,
      raw: raw,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'shop_daily',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
