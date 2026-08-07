/* Deep dump for video-details SPA (virtual list / tabs / roles). Ziniao page exec. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  try {
    var body = clean((document.body && (document.body.innerText || document.body.textContent)) || '');
    var url = location.href || '';
    var tabs = [];
    var nodes = document.querySelectorAll('[role="tab"], [class*="tab"], [class*="Tab"], button, div, span');
    var seen = {};
    for (var i = 0; i < nodes.length && tabs.length < 40; i++) {
      var el = nodes[i];
      var tx = clean(el.innerText || el.textContent);
      if (!tx || tx.length > 24) continue;
      if (!/全部|已绑定|联盟|需要关注|配置指标|导出|账号|All|Bound|Affiliate|Export/i.test(tx)) continue;
      var k = tx + '|' + (el.tagName || '');
      if (seen[k]) continue;
      seen[k] = true;
      tabs.push({
        text: tx,
        tag: el.tagName,
        role: el.getAttribute('role') || '',
        cls: String(el.className || '').slice(0, 100),
        ariaSelected: el.getAttribute('aria-selected') || ''
      });
    }
    var tables = Array.prototype.slice.call(document.querySelectorAll('table')).map(function (t, idx) {
      var ths = Array.prototype.slice.call(t.querySelectorAll('thead th, tr th')).map(function (th) {
        return clean(th.innerText).slice(0, 80);
      });
      return {
        i: idx,
        headers: ths.slice(0, 20),
        rows: t.querySelectorAll('tbody tr').length,
        cls: String(t.className || '').slice(0, 80)
      };
    });
    var grids = [];
    var gnodes = document.querySelectorAll('[role="grid"], [role="rowgroup"], [class*="virtual"], [class*="Virtual"], [class*="list"], [class*="List"]');
    for (var gi = 0; gi < gnodes.length && grids.length < 15; gi++) {
      var g = gnodes[gi];
      grids.push({
        tag: g.tagName,
        role: g.getAttribute('role') || '',
        cls: String(g.className || '').slice(0, 120),
        childCount: g.children ? g.children.length : 0,
        text: clean(g.innerText || '').slice(0, 160)
      });
    }
    var links = Array.prototype.slice
      .call(document.querySelectorAll('a[href]'))
      .slice(0, 30)
      .map(function (a) {
        return { text: clean(a.innerText).slice(0, 60), href: a.href || a.getAttribute('href') };
      })
      .filter(function (x) {
        return x.href && !/javascript:|lf16-scmcdn/i.test(x.href);
      });
    var longIds = [];
    var idm = body.match(/\b\d{10,}\b/g);
    if (idm) {
      var us = {};
      for (var j = 0; j < idm.length && longIds.length < 20; j++) {
        if (!us[idm[j]]) {
          us[idm[j]] = true;
          longIds.push(idm[j]);
        }
      }
    }
    return JSON.stringify({
      ok: true,
      module: 'video_details_probe',
      url: url,
      title: document.title || '',
      bodyLen: body.length,
      sample: body.slice(0, 1500),
      tabs: tabs,
      tables: tables,
      grids: grids,
      links: links,
      longIdsInBody: longIds,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'video_details_probe',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
