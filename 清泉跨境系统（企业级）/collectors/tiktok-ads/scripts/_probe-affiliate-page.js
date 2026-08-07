/* Coarse DOM dump for affiliate performance POC tuning (P3.0). Ziniao page exec. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  try {
    var body = clean((document.body && (document.body.innerText || document.body.textContent)) || '');
    var links = Array.prototype.slice
      .call(document.querySelectorAll('a[href]'))
      .slice(0, 50)
      .map(function (a) {
        return { text: clean(a.innerText).slice(0, 80), href: a.href || a.getAttribute('href') };
      });
    var tables = Array.prototype.slice.call(document.querySelectorAll('table')).map(function (t, i) {
      var ths = Array.prototype.slice.call(t.querySelectorAll('thead th, tr th')).map(function (th) {
        return clean(th.innerText).slice(0, 60);
      });
      var firstRow = [];
      var tr0 = t.querySelector('tbody tr');
      if (tr0) {
        firstRow = Array.prototype.slice.call(tr0.querySelectorAll('td')).slice(0, 12).map(function (td) {
          return clean(td.innerText).slice(0, 80);
        });
      }
      return {
        i: i,
        headers: ths.slice(0, 20),
        rowApprox: t.querySelectorAll('tbody tr').length,
        firstRow: firstRow
      };
    });
    var cards = [];
    var cardNodes = document.querySelectorAll(
      '[class*="card"], [class*="Card"], [class*="metric"], [class*="Metric"], [class*="kpi"], [class*="KPI"], [class*="statistic"], [class*="Statistic"]'
    );
    for (var ci = 0; ci < Math.min(cardNodes.length, 40); ci++) {
      var ct = clean(cardNodes[ci].innerText).slice(0, 120);
      if (ct && ct.length >= 4 && ct.length <= 100) cards.push(ct);
    }
    return JSON.stringify({
      ok: true,
      module: 'affiliate_probe',
      url: location.href || '',
      title: document.title || '',
      host: location.host || '',
      bodyLen: body.length,
      sample: body.slice(0, 1500),
      hasPerformanceWord: /表现|Performance|归因\s*GMV|Attributed\s*GMV|预计佣金|Estimat(ed)?\s*commission|动销达人/i.test(body),
      hasCreatorWord: /达人|Creator|Influencer|联盟/i.test(body),
      tables: tables.slice(0, 15),
      cards: cards.slice(0, 30),
      links: links,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'affiliate_probe',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
