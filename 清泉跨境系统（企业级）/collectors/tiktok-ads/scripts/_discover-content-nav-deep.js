/* Deep nav dump: anchors + [href] + data-* + text nodes near 数据分析/内容. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function pushUnique(arr, seen, obj) {
    var key = (obj.href || '') + '|' + (obj.text || '');
    if (seen[key]) return;
    seen[key] = 1;
    arr.push(obj);
  }
  try {
    var body = clean((document.body && (document.body.innerText || document.body.textContent)) || '');
    var seen = {};
    var links = [];

    var nodes = document.querySelectorAll('a[href], [href], [data-href], [data-path], [data-url], [data-to], [routerlink], [ng-reflect-router-link]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var href =
        el.href ||
        el.getAttribute('href') ||
        el.getAttribute('data-href') ||
        el.getAttribute('data-path') ||
        el.getAttribute('data-url') ||
        el.getAttribute('data-to') ||
        el.getAttribute('routerlink') ||
        el.getAttribute('ng-reflect-router-link') ||
        '';
      var text = clean(el.innerText || el.textContent).slice(0, 120);
      if (!href && !text) continue;
      if (href && href.indexOf('javascript:') === 0) continue;
      var blob = (text + ' ' + href).toLowerCase();
      if (
        /内容|视频|商品卡|compass|analytics|data-overview|content|video|product-card|数据分析|直播/.test(blob) ||
        /compass|analytics|content|video|product/i.test(href)
      ) {
        pushUnique(links, seen, {
          text: text,
          href: href,
          tag: el.tagName,
          cls: String(el.className || '').slice(0, 80)
        });
      }
    }

    // clickable divs/spans with analytics-ish text
    var all = document.querySelectorAll('div, span, li, p, button');
    var textHits = [];
    for (var j = 0; j < all.length && textHits.length < 40; j++) {
      var n = all[j];
      if (n.children && n.children.length > 3) continue;
      var tx = clean(n.innerText || n.textContent);
      if (!tx || tx.length > 40) continue;
      if (/^(内容分析|视频和照片|视频和照片概览|商品卡|商品数据分析|数据分析|短视频|直播)$/i.test(tx) ||
          /content analytics|videos? and photos|product card/i.test(tx)) {
        textHits.push({
          text: tx,
          tag: n.tagName,
          cls: String(n.className || '').slice(0, 100),
          parentCls: n.parentElement ? String(n.parentElement.className || '').slice(0, 80) : ''
        });
      }
    }

    // script src / preload hints
    var scripts = Array.prototype.slice
      .call(document.querySelectorAll('script[src]'))
      .map(function (s) {
        return s.src;
      })
      .filter(function (s) {
        return /compass|analytics|content/i.test(s);
      })
      .slice(0, 15);

    return JSON.stringify({
      ok: true,
      module: 'content_nav_deep',
      url: location.href || '',
      title: document.title || '',
      bodyLen: body.length,
      sample: body.slice(0, 1000),
      links: links.slice(0, 50),
      textHits: textHits,
      scripts: scripts,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'content_nav_deep',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
