/* Discover affiliate-center nav URLs from seller center (P3.0). Ziniao page exec. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function scoreLink(text, href) {
    var t = (text + ' ' + href).toLowerCase();
    var s = 0;
    if (/affiliate|partner|联盟|达人|creator|collaboration|collab/i.test(t)) s += 5;
    if (/affiliate-center|affiliate_center|partner-center|partner_center|affiliate\.tiktok|shop\.tiktokglobalshop|affiliate-us|affiliate-eu|affiliate-uk/i.test(href)) s += 6;
    if (/表现|performance|analytics|数据分析|data/i.test(t) && /affiliate|联盟|达人|creator|partner/i.test(t)) s += 4;
    if (/样品|sample|达人触达|find\s*creators|all\s*videos|所有视频/i.test(t)) s += 2;
    if (/ads-creation|order\?|product\/manage|finance|health-center|homepage$|login/i.test(href)) s -= 3;
    if (/compass\/video|product-card-analytics/i.test(href)) s -= 2;
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
      var text = clean(a.innerText || a.textContent).slice(0, 120);
      var sc = scoreLink(text, href);
      if (sc < 2) continue;
      var key = href.split('#')[0];
      if (seen[key]) continue;
      seen[key] = 1;
      links.push({ text: text, href: href, score: sc, host: (function () {
        try { return new URL(href).host; } catch (e0) { return ''; }
      })() });
    }
    links.sort(function (x, y) {
      return y.score - x.score;
    });

    var menuHints = [];
    var nodes = document.querySelectorAll(
      '[class*="menu"], [class*="nav"], [role="menuitem"], [class*="Menu"], [class*="sidebar"], [class*="Side"]'
    );
    for (var mi = 0; mi < Math.min(nodes.length, 120); mi++) {
      var nt = clean(nodes[mi].innerText).slice(0, 100);
      if (/联盟|达人|affiliate|creator|partner|样品|sample|表现|performance/i.test(nt)) {
        menuHints.push(nt);
      }
    }

    var clickables = [];
    var candidates = document.querySelectorAll('a, button, [role="link"], [role="button"], div, span');
    for (var ci = 0; ci < Math.min(candidates.length, 400); ci++) {
      var el = candidates[ci];
      var ct = clean(el.innerText || el.textContent).slice(0, 80);
      if (!ct || ct.length > 40) continue;
      if (/^联盟$|前往联盟|联盟中心|Affiliate|Creator marketplace|Open affiliate|Go to affiliate/i.test(ct)) {
        clickables.push({
          tag: el.tagName,
          text: ct,
          href: el.href || el.getAttribute('href') || null
        });
        if (clickables.length >= 15) break;
      }
    }

    return JSON.stringify({
      ok: true,
      module: 'affiliate_nav_discover',
      url: location.href || '',
      title: document.title || '',
      host: location.host || '',
      bodyLen: body.length,
      sample: body.slice(0, 900),
      hasAffiliateWord: /联盟|Affiliate|达人|Creator|Partner\s*center|样品/i.test(body),
      links: links.slice(0, 40),
      menuHints: menuHints.slice(0, 25),
      clickables: clickables,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'affiliate_nav_discover',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
