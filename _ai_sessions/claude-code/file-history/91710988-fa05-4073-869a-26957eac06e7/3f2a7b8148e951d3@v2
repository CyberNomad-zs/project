/* Probe product manage page: multi-SKU expand controls + order detail links shape. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  var out = {
    url: location.href || '',
    title: document.title || '',
    expandButtons: [],
    skuTexts: [],
    productRows: [],
    orderLinks: [],
    apiHints: []
  };
  var nodes = document.querySelectorAll('button,a,span,div,td');
  for (var i = 0; i < nodes.length && out.expandButtons.length < 30; i++) {
    var el = nodes[i];
    var tx = clean(el.textContent).slice(0, 40);
    if (!tx) continue;
    if (/\d+\s*个\s*SKU|SKU\s*展开|展开\s*SKU|Expand\s*SKU|SKU/i.test(tx) && tx.length <= 30) {
      out.expandButtons.push({
        tag: el.tagName,
        text: tx,
        cls: String(el.className || '').slice(0, 80),
        role: el.getAttribute('role') || '',
        aria: el.getAttribute('aria-expanded') || ''
      });
    }
  }
  // sample first product table rows
  var table = document.querySelector('table');
  if (table) {
    var trs = table.querySelectorAll('tr');
    for (var r = 0; r < Math.min(trs.length, 8); r++) {
      var tds = trs[r].querySelectorAll('td,th');
      var cells = [];
      for (var c = 0; c < Math.min(tds.length, 8); c++) cells.push(clean(tds[c].textContent).slice(0, 80));
      out.productRows.push(cells);
    }
  }
  // seller sku occurrences
  var body = clean((document.body && document.body.innerText) || '').slice(0, 5000);
  var m;
  var re = /(?:商家\s*)?SKU\s*[:：]\s*([^\s]+)/gi;
  while ((m = re.exec(body)) && out.skuTexts.length < 20) {
    out.skuTexts.push(m[1]);
  }
  var expandRe = /(\d+)\s*个\s*SKU\s*展开/g;
  var expands = [];
  while ((m = expandRe.exec(body)) && expands.length < 20) expands.push(m[0]);
  out.expandPhrases = expands;

  // order page links if any
  var as = document.querySelectorAll('a[href]');
  for (var a = 0; a < as.length && out.orderLinks.length < 20; a++) {
    var href = as[a].href || '';
    if (/order/i.test(href) && /detail|manage|id=/i.test(href)) {
      out.orderLinks.push({ href: href.slice(0, 160), text: clean(as[a].textContent).slice(0, 40) });
    }
  }
  return JSON.stringify(out);
})();
