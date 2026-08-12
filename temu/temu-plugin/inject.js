// 运行在页面 MAIN world：hook window.fetch 与 XMLHttpRequest，
// 截获 Temu 后台商品接口的响应 JSON，通过 postMessage 传给 content.js（隔离世界）。
// 只读、不改请求；请求本身仍由页面自己发出（自带 cookie + anti-content 签名），故不触发风控。
//
// v22：在**发请求时**记录「商品流量待关注」是否开启。
// 旧逻辑在**响应到达**时才读 DOM：若筛选已关但迟来的 countStatus 仍是子集，
// 会把「限流在售 2」写成「全店在售」，随后恢复 12 时误报上升（Twilight 2→12）。
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

  // 与 content.js isChipSelected 对齐：请求发起瞬间的筛选态（MAIN world 可读真实 DOM）
  function isWatchFilterOnAtRequest() {
    try {
      // content 在 traffic 扫描期间会写 data-temu-force-watch-filter=1
      if (document.documentElement.getAttribute('data-temu-force-watch-filter') === '1') return true;
      if (document.documentElement.getAttribute('data-temu-watch-filter-grace') === '1') return true;
      for (const card of document.querySelectorAll('[class*="use-quick-field_tsx_card__"]')) {
        if (!/商品流量待关注/.test(card.textContent || '')) continue;
        const root = card.closest('[class*="use-quick-field"]') || card;
        const nodes = [root, card];
        for (const n of nodes) {
          if (!n) continue;
          const cls = String(n.className || '');
          if (/(?:^|[\s_-])(?:selected|is-selected|isselected|active|is-active|isactive|checked|is-checked|current)(?:[\s_-]|$)/i.test(cls)) {
            return true;
          }
          if (n.getAttribute('aria-pressed') === 'true') return true;
          if (n.getAttribute('aria-selected') === 'true') return true;
          if (n.getAttribute('data-selected') === 'true') return true;
        }
        const input = root.querySelector && root.querySelector('input[type="checkbox"],input[type="radio"]');
        if (input && input.checked) return true;
        // 选中 chip 常见主色蓝边（截图：蓝框「商品流量待关注」）
        try {
          const st = window.getComputedStyle(root);
          const bw = parseFloat(st.borderTopWidth) || parseFloat(st.outlineWidth) || 0;
          if (bw >= 1) {
            const color = st.borderTopColor || st.outlineColor || '';
            const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
            if (m) {
              const r = Number(m[1]); const g = Number(m[2]); const b = Number(m[3]);
              if (b >= 160 && b > r + 30 && b > g + 20) return true;
            }
          }
        } catch (e) { /* ignore */ }
        // 截图里选中 chip 有浅蓝背景/蓝框；对比 box-shadow 含蓝
        try {
          const st = window.getComputedStyle(root);
          const bg = st.backgroundColor || '';
          const bm = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
          if (bm) {
            const r = Number(bm[1]); const g = Number(bm[2]); const b = Number(bm[3]);
            // 浅蓝底：B 高、偏白
            if (b > 200 && r > 180 && g > 200 && b >= r && b >= g) return true;
          }
        } catch (e) { /* ignore */ }
      }
    } catch (e) { /* ignore */ }
    return false;
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

  function post(url, body, mallId, watchFilterOnAtReq) {
    const kind = kindOf(url);
    if (!kind || !body) return;
    try {
      window.postMessage({
        __temuMon: true,
        kind,
        url: String(url),
        body: String(body),
        mallId: mallId || findMallInCookie() || null,
        // 请求发起时的筛选态（优先于响应到达时 DOM）
        watchFilterOnAtReq: !!watchFilterOnAtReq,
      }, '*');
    } catch (e) { /* ignore */ }
  }

  // ---- fetch ----
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    let urlHint = '';
    try {
      urlHint = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
    } catch (e) { /* ignore */ }
    // 在发起前采样筛选态（响应可能晚到，DOM 已复位）
    const filterAtReq = MATCH.test(urlHint) ? isWatchFilterOnAtRequest() : false;
    return origFetch.apply(this, args).then((resp) => {
      try {
        let url = (resp && resp.url) || '';
        if (!url) url = urlHint;
        if (MATCH.test(url)) {
          const hdrs = headersToObj(args[1] && args[1].headers);
          const mallId = findMallInHeaders(hdrs);
          const filterFlag = filterAtReq || isWatchFilterOnAtRequest();
          resp.clone().text().then((t) => post(url, t, mallId, filterFlag)).catch(() => {});
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
    const url0 = this.__temuUrl || '';
    if (MATCH.test(url0)) {
      this.__temuWatchFilterAtReq = isWatchFilterOnAtRequest();
    }
    this.addEventListener('load', () => {
      try {
        const url = this.__temuUrl || '';
        if (MATCH.test(url)) {
          const flag = !!(this.__temuWatchFilterAtReq || isWatchFilterOnAtRequest());
          post(url, this.responseText, findMallInHeaders(this.__temuHdrs), flag);
        }
      } catch (e) { /* ignore */ }
    });
    return origSend.apply(this, a);
  };
})();
