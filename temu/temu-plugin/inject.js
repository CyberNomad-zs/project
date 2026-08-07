// 运行在页面 MAIN world：hook window.fetch 与 XMLHttpRequest，
// 截获 Temu 后台商品接口的响应 JSON，通过 postMessage 传给 content.js（隔离世界）。
// 只读、不改请求；请求本身仍由页面自己发出（自带 cookie + anti-content 签名），故不触发风控。
(function () {
  if (window.__temuMonHooked) return;
  window.__temuMonHooked = true;

  // 关注接口：countStatus（各状态计数）、pageQuery（商品列表）、skuSpecList（SKU 规格列表）、skuPriceQuery（SKU 建议价）
  const MATCH = /(visage-agent-seller\/product\/skc\/(countStatus|pageQuery)|anniston-agent-seller\/sku\/spec\/parent\/list|visage-agent-seller\/product\/sku\/site\/suggestedPrice\/gray\/query)\b/;
  function kindOf(url) {
    if (/countStatus/.test(url)) return 'countStatus';
    if (/skc\/pageQuery/.test(url)) return 'pageQuery';
    if (/sku\/spec\/parent\/list/.test(url)) return 'skuSpecList';
    if (/suggestedPrice\/gray\/query/.test(url)) return 'skuPriceQuery';
    return null;
  }

  // 从请求头 / cookie 里找出当前店铺 id（多店铺时用来区分是哪个店）
  function findMallInHeaders(hdrs) {
    if (!hdrs) return null;
    for (const k of Object.keys(hdrs)) {
      if (/mall.?id/i.test(k) && /^\d{6,}$/.test(String(hdrs[k]).trim())) return String(hdrs[k]).trim();
    }
    return null;
  }
  function findMallInCookie() {
    try {
      const m = document.cookie.match(/(?:^|;\s*)[^=]*mall[^=]*id[^=]*=(\d{6,})/i);
      if (m) return m[1];
    } catch (e) { /* ignore */ }
    return null;
  }
  function headersToObj(h) {
    const o = {};
    try {
      if (!h) return o;
      if (typeof Headers !== 'undefined' && h instanceof Headers) h.forEach((v, k) => (o[String(k).toLowerCase()] = v));
      else if (Array.isArray(h)) for (const pair of h) o[String(pair[0]).toLowerCase()] = pair[1];
      else for (const k of Object.keys(h)) o[String(k).toLowerCase()] = h[k];
    } catch (e) { /* ignore */ }
    return o;
  }

  function post(url, body, mallId) {
    const kind = kindOf(url);
    if (!kind || !body) return;
    try {
      window.postMessage({ __temuMon: true, kind, url: String(url), body: String(body), mallId: mallId || findMallInCookie() || null }, '*');
    } catch (e) { /* ignore */ }
  }

  // ---- fetch ----
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    return origFetch.apply(this, args).then((resp) => {
      try {
        let url = (resp && resp.url) || '';
        if (!url) url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        if (MATCH.test(url)) {
          const hdrs = headersToObj(args[1] && args[1].headers);
          const mallId = findMallInHeaders(hdrs);
          resp.clone().text().then((t) => post(url, t, mallId)).catch(() => {});
        }
      } catch (e) { /* ignore */ }
      return resp;
    });
  };

  // ---- XMLHttpRequest ----
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__temuUrl = url;
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
    try { (this.__temuHdrs = this.__temuHdrs || {})[String(name).toLowerCase()] = value; } catch (e) { /* ignore */ }
    return origSetHeader.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (...a) {
    this.addEventListener('load', () => {
      try {
        const url = this.__temuUrl || '';
        if (MATCH.test(url)) post(url, this.responseText, findMallInHeaders(this.__temuHdrs));
      } catch (e) { /* ignore */ }
    });
    return origSend.apply(this, a);
  };
})();
