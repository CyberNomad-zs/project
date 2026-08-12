/* Coarse DOM dump for content/product-traffic POC tuning. Ziniao page exec. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  try {
    var body = clean((document.body && (document.body.innerText || document.body.textContent)) || '');
    var links = Array.prototype.slice
      .call(document.querySelectorAll('a[href]'))
      .slice(0, 40)
      .map(function (a) {
        return { text: clean(a.innerText).slice(0, 80), href: a.href || a.getAttribute('href') };
      });
    var tables = Array.prototype.slice.call(document.querySelectorAll('table')).map(function (t, i) {
      var ths = Array.prototype.slice.call(t.querySelectorAll('thead th, tr th')).map(function (th) {
        return clean(th.innerText).slice(0, 60);
      });
      return { i: i, headers: ths.slice(0, 20), rowApprox: t.querySelectorAll('tbody tr').length };
    });
    return JSON.stringify({
      ok: true,
      module: 'content_probe',
      url: location.href || '',
      title: document.title || '',
      bodyLen: body.length,
      sample: body.slice(0, 1200),
      tables: tables.slice(0, 15),
      links: links,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'content_probe',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
