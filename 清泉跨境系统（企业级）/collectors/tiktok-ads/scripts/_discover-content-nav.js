/* Discover content-analysis nav URLs from seller center (P2.0). Ziniao page exec. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function scoreLink(text, href) {
    var t = (text + ' ' + href).toLowerCase();
    var s = 0;
    if (/content-analysis|content_analysis|\/content\//i.test(href)) s += 5;
    if (/视频和照片|video.*photo|videos?\s*and\s*photos|短视频|video-overview|video_overview|\/video/i.test(t)) s += 4;
    if (/商品卡|product-card|product_card|product-analytics|商品数据/i.test(t)) s += 4;
    if (/内容分析|content\s*analytics|content\s*analysis/i.test(t)) s += 3;
    if (/compass|数据分析|data-overview|analytics/i.test(t)) s += 1;
    if (/ads-creation|order|product\/manage|finance|health|homepage|login/i.test(href)) s -= 3;
    return s;
  }
  try {
    var body = clean((document.body && (document.body.innerText || document.body.textContent)) || '');
    var anchors = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
    var seen = {};
    var links = [];
    for (var i = 0; i < anchors.length; i++) {
      var a = anchors[i];
      var href = a.href || a.getAttribute('href') || '';
      if (!href || href.indexOf('javascript:') === 0 || href === '#') continue;
      var text = clean(a.innerText || a.textContent).slice(0, 100);
      var sc = scoreLink(text, href);
      if (sc < 2) continue;
      var key = href.split('?')[0];
      if (seen[key]) continue;
      seen[key] = 1;
      links.push({ text: text, href: href, score: sc });
    }
    links.sort(function (x, y) {
      return y.score - x.score;
    });

    // also scan menu-like elements with data attributes
    var menuHints = [];
    var nodes = document.querySelectorAll('[class*="menu"], [class*="nav"], [role="menuitem"], [class*="Menu"]');
    for (var mi = 0; mi < Math.min(nodes.length, 80); mi++) {
      var nt = clean(nodes[mi].innerText).slice(0, 80);
      if (/内容|视频|商品卡|Content|Video|Product\s*card/i.test(nt)) {
        menuHints.push(nt);
      }
    }

    var tables = Array.prototype.slice.call(document.querySelectorAll('table')).slice(0, 8).map(function (tb, idx) {
      var ths = Array.prototype.slice.call(tb.querySelectorAll('thead th, tr th')).map(function (th) {
        return clean(th.innerText).slice(0, 40);
      });
      return { i: idx, headers: ths.slice(0, 15), rows: tb.querySelectorAll('tbody tr').length };
    });

    return JSON.stringify({
      ok: true,
      module: 'content_nav_discover',
      url: location.href || '',
      title: document.title || '',
      bodyLen: body.length,
      sample: body.slice(0, 800),
      hasContentWord: /内容分析|Content\s*analytics|视频和照片|商品卡/i.test(body),
      links: links.slice(0, 30),
      menuHints: menuHints.slice(0, 20),
      tables: tables,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'content_nav_discover',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
