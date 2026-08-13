/* TikTok product manage list scraper - calibrated 2026-07-31 seller-uk. */
(function () {
  function cleanText(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function detectCurrency(text) {
    var s = String(text == null ? '' : text);
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
    // 零售价列常为 "£76.65促销价：£45.99" — 先抽第一个金额
    var money = s.match(/[¥$€£￥]\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)/) ||
      s.match(/([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:USD|GBP|EUR|CNY|RMB)/i);
    if (money) {
      var n0 = Number(String(money[1]).replace(/,/g, ''));
      if (isFinite(n0)) return n0;
    }
    s = s.replace(/[,\s]/g, '').replace(/[¥$€£￥]/g, '');
    s = s.replace(/USD|GBP|EUR|CNY|RMB/gi, '').replace(/%/g, '');
    // 去掉中文尾巴（促销价…）
    s = s.replace(/[^\d.\-].*$/, '');
    var n = Number(s);
    return isFinite(n) ? n : null;
  }
  function cleanStatus(text) {
    var s = cleanText(text);
    if (!s) return '';
    var m = s.match(/^(在售|已下架|草稿|审核中|已冻结|Active|Inactive|Draft)/i);
    return m ? m[1] : s.slice(0, 40);
  }
  function extractProductId(text) {
    var s = cleanText(text);
    // 优先 ID: 标签与 17… 商品 ID；避免把订单号 57693… 当商品 ID
    var m = s.match(/ID\s*[:：]\s*(\d{10,22})/i) || s.match(/\b(17\d{15,20})\b/);
    if (m) return m[1];
    // 裸长数字：仅当同段有可读英文/中文标题且非订单时间串时才接受
    if (isOrderLikeProductText(s)) return '';
    var bare = s.match(/\b(\d{15,22})\b/);
    if (!bare) return '';
    var hasTitle = /[A-Za-z]{4,}|[\u4e00-\u9fff]{2,}/.test(s.replace(bare[1], ' '));
    return hasTitle ? bare[1] : '';
  }
  function isOrderLikeProductText(text) {
    var s = cleanText(text);
    if (!s) return false;
    if (/件商品/.test(s)) return true;
    if (/星期[一二三四五六日天]/.test(s)) return true;
    if (/\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i.test(s)) return true;
    if (/\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\b/i.test(s)) return true;
    // 纯「长数字 + 可选时间」
    if (/^\d{14,22}(\s+\d{1,2}:\d{2}(:\d{2})?)?$/.test(s)) return true;
    if (/^\d{14,22}.{0,12}\d{1,2}:\d{2}/.test(s) && !/[A-Za-z]{4,}/.test(s)) return true;
    return false;
  }
  function sanitizeSellerSku(raw) {
    var sku = cleanText(raw);
    if (!sku) return '';
    // cut trailing UI glue: 浏览次数/销售额/分析/在售/已售出/日期
    sku = sku.replace(/(?:--)?浏览次数.*$/i, '');
    sku = sku.replace(/(?:--)?销售额.*$/i, '');
    sku = sku.replace(/(?:--)?已售出.*$/i, '');
    sku = sku.replace(/已售出.*$/i, '');
    sku = sku.replace(/(?:--)?分析.*$/i, '');
    sku = sku.replace(/(?:--)?在售.*$/i, '');
    sku = sku.replace(/--.*$/, '');
    // keep only first token-like SKU (allow * for multi-pack like JMCATYZWJ*2)
    var m = sku.match(/^([A-Za-z0-9][A-Za-z0-9_\-*]{1,48})/);
    sku = m ? m[1] : cleanText(sku).slice(0, 48);
    if (!sku || isSkuExpandNoise(sku) || /展开|全部|批量|浏览|销售|分析|已售出/i.test(sku)) return '';
    if (sku.length < 2) return '';
    return sku;
  }
  function extractSellerSku(text) {
    var s = cleanText(text);
    // 排除「N 个 SKU 展开」按钮文案，避免误抽
    if (isSkuExpandNoise(s)) return '';
    // tight capture: alnum/_/- only (avoid swallowing 浏览次数…)
    var m =
      s.match(/(?:商家\s*)?SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9_\-]{1,48})/i) ||
      s.match(/Seller\s*SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9_\-]{1,48})/i) ||
      s.match(/卖家\s*SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9_\-]{1,48})/i);
    if (!m) return '';
    return sanitizeSellerSku(m[1]);
  }
  function isSkuExpandNoise(text) {
    var s = cleanText(text);
    if (!s) return false;
    // 「2 个 SKU 展开」「SKU展开」「Expand 3 SKUs」等 UI 噪声
    if (/\d+\s*个\s*SKU/i.test(s)) return true;
    if (/SKU\s*展开|展开\s*全部|展开\s*SKU|批量操作/i.test(s)) return true;
    if (/expand\s*\d*\s*sku|show\s*sku|view\s*sku/i.test(s)) return true;
    if (/^name:.*SKU/i.test(s) && /展开|expand/i.test(s)) return true;
    return false;
  }
  function extractAllSellerSkus(text) {
    var s = cleanText(text);
    if (!s || isSkuExpandNoise(s)) return [];
    var out = [], seen = {};
    var re = /(?:商家\s*|Seller\s*|卖家\s*)?SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9_\-]{1,48})/gi;
    var m;
    while ((m = re.exec(s))) {
      var sku = sanitizeSellerSku(m[1]);
      if (!sku) continue;
      if (seen[sku]) continue;
      seen[sku] = true;
      out.push(sku);
    }
    return out;
  }
  function extractSalesQty(text) {
    var s = cleanText(text);
    var m = s.match(/已售出\s*(\d+)/) || s.match(/Sold\s*(\d+)/i);
    return m ? Number(m[1]) : null;
  }
  function extractProductName(text) {
    var s = cleanText(text);
    if (isOrderLikeProductText(s)) return '';
    if (isSkuExpandNoise(s) && !extractProductId(s)) return '';
    s = s.replace(/ID\s*[:：]\s*\d{10,22}/ig, ' ');
    s = s.replace(/(?:商家\s*)?SKU\s*[:：]\s*\S+/ig, ' ');
    // 去掉展开按钮尾巴
    s = s.replace(/\d+\s*个\s*SKU\s*展开?/gi, ' ');
    s = s.replace(/SKU\s*展开/gi, ' ');
    // 去掉状态旁粘连的星期/时间（订单列表特征）
    s = s.replace(/星期[一二三四五六日天]\s*\d{1,2}:\d{2}(:\d{2})?/g, ' ');
    s = s.replace(/\b\d{14,22}\b/g, ' ');
    s = s.replace(/\s+/g, ' ').trim();
    if (isOrderLikeProductText(s)) return '';
    return s;
  }
  var HEADER_ALIASES = {
    product: ['商品', '商品名称', '产品名称', 'product', 'product name', 'title'],
    performance: ['表现', 'performance'],
    status: ['状态', '商品状态', 'status'],
    stockQty: ['库存', '可售库存', 'stock'],
    price: ['零售价', '价格', '售价', 'price', 'retail']
  };
  function matchField(header) {
    var h = cleanText(header).toLowerCase();
    if (!h) return null;
    var best = null, bestLen = 0;
    var keys = Object.keys(HEADER_ALIASES);
    for (var i = 0; i < keys.length; i++) {
      var field = keys[i];
      var aliases = HEADER_ALIASES[field];
      for (var j = 0; j < aliases.length; j++) {
        var al = aliases[j].toLowerCase();
        if (h === al || h.indexOf(al) >= 0) {
          if (al.length >= bestLen) { best = field; bestLen = al.length; }
        }
      }
    }
    return best;
  }
  function scoreTable(table) {
    var trs = Array.prototype.slice.call(table.querySelectorAll('tr'));
    if (trs.length < 2) return 0;
    var head = Array.prototype.slice.call(trs[0].querySelectorAll('th,td')).map(function (c) { return cleanText(c.textContent); });
    var hits = 0, fields = {};
    for (var i = 0; i < head.length; i++) {
      var f = matchField(head[i]);
      if (f) { hits++; fields[f] = true; }
    }
    if (!fields.product && !fields.stockQty && !fields.price) {
      var idHits = 0;
      for (var r = 1; r < Math.min(trs.length, 6); r++) {
        if (extractProductId(trs[r].textContent || '')) idHits++;
      }
      if (idHits === 0) return 0;
      return idHits * 5 + trs.length;
    }
    return hits * 10 + Math.min(trs.length, 80);
  }
  function pickBestTable() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('table'));
    var best = null, bestScore = 0;
    for (var i = 0; i < tables.length; i++) {
      var s = scoreTable(tables[i]);
      if (s > bestScore) { bestScore = s; best = tables[i]; }
    }
    return bestScore >= 8 ? best : null;
  }
  function defaultColMap() {
    return { product: 1, performance: 2, status: 3, stockQty: 4, price: 5 };
  }
  function parseHtmlTable(table) {
    var trs = Array.prototype.slice.call(table.querySelectorAll('tr'));
    if (trs.length < 2) return { rows: [], headers: [], colMap: {} };
    var headIdx = -1;
    for (var i = 0; i < Math.min(3, trs.length); i++) {
      var cells = Array.prototype.slice.call(trs[i].querySelectorAll('th,td')).map(function (c) { return cleanText(c.textContent); });
      var hits = 0, hasPid = false;
      for (var h = 0; h < cells.length; h++) {
        if (matchField(cells[h])) hits++;
        if (extractProductId(cells[h])) hasPid = true;
      }
      if (hits >= 2 && !hasPid) { headIdx = i; break; }
    }
    var colMap = {}, headCells = [];
    if (headIdx >= 0) {
      headCells = Array.prototype.slice.call(trs[headIdx].querySelectorAll('th,td')).map(function (c) { return cleanText(c.textContent); });
      headCells.forEach(function (h, idx) {
        var f = matchField(h);
        if (f && colMap[f] == null) colMap[f] = idx;
      });
    }
    var def = defaultColMap();
    Object.keys(def).forEach(function (k) { if (colMap[k] == null) colMap[k] = def[k]; });
    if (!headCells.length) headCells = ['', 'product', 'perf', 'status', 'stock', 'price'];
    var rows = [], seen = {};
    var start = headIdx >= 0 ? headIdx + 1 : 0;
    for (var r = start; r < trs.length; r++) {
      var tds = Array.prototype.slice.call(trs[r].querySelectorAll('td,th'));
      if (!tds.length) continue;
      var vals = tds.map(function (c) { return cleanText(c.textContent); });
      function get(f) { return colMap[f] != null ? vals[colMap[f]] || '' : ''; }
      var productCell = get('product') || vals.join(' ');
      var rowBlob = vals.join(' ');
      var productId = extractProductId(productCell) || extractProductId(rowBlob);
      var sellerSkus = extractAllSellerSkus(productCell);
      if (!sellerSkus.length) sellerSkus = extractAllSellerSkus(rowBlob);
      var sellerSku = sellerSkus.length ? sellerSkus[0] : extractSellerSku(productCell);
      var productName = extractProductName(productCell);
      // 订单行误入（订单号+时间 / N 件商品）
      if (isOrderLikeProductText(productCell) || isOrderLikeProductText(productName) || isOrderLikeProductText(rowBlob)) continue;
      // 整行都是展开噪声且无真实 ID → 丢弃
      if (!productId && (isSkuExpandNoise(productCell) || isSkuExpandNoise(productName) || isSkuExpandNoise(rowBlob))) continue;
      if (!productId) {
        if (sellerSku) productId = 'sku:' + sellerSku;
        else if (productName && !isSkuExpandNoise(productName)) productId = 'name:' + productName.slice(0, 80);
      }
      if (!productId || seen[productId]) continue;
      // 跳过展开行 / 表头噪声（含 name:N个SKU展开）
      if (isSkuExpandNoise(productId) || isSkuExpandNoise(productName)) continue;
      if (isOrderLikeProductText(productId + ' ' + productName)) continue;
      if (/SKU展开|展开全部|批量操作|\d+\s*个\s*SKU/.test(productId + ' ' + productName + ' ' + productCell)) continue;
      if (/^name:/.test(productId) && /SKU|展开|expand/i.test(productId)) continue;
      // 无真实平台 ID 且名称仍像 UI → 丢弃
      if (!/^\d{10,}$/.test(productId) && !/^sku:/.test(productId) && isSkuExpandNoise(productId + productName)) continue;
      seen[productId] = true;
      var perf = get('performance');
      var priceCell = get('price');
      rows.push({
        productId: productId,
        productName: productName,
        sellerSku: sellerSku || '',
        sellerSkus: sellerSkus,
        status: cleanStatus(get('status')),
        stockQty: parseNumber(get('stockQty')),
        price: parseNumber(priceCell),
        salesQty: extractSalesQty(perf),
        currencyHint: detectCurrency(vals.join(' ')) || detectCurrency(priceCell),
        rawCells: vals.slice(0, 10)
      });
    }
    return { rows: rows, headers: headCells, colMap: colMap };
  }
  function parseIdBlocks() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('div,tr,li,section,article'));
    var rows = [], seen = {};
    for (var i = 0; i < nodes.length; i++) {
      var raw = nodes[i].textContent || '';
      if (raw.indexOf('ID:') < 0 && raw.indexOf('ID：') < 0) continue;
      var text = cleanText(raw).slice(0, 600);
      if (text.length > 550) continue;
      var productId = extractProductId(text);
      if (!productId || seen[productId]) continue;
      seen[productId] = true;
      var pm = text.match(/[£$€]\s*[0-9.]+/);
      var st = '';
      var sm = text.match(/(在售|已下架|草稿|审核中|已冻结|Active|Inactive|Draft)/);
      if (sm) st = sm[1];
      var skus = extractAllSellerSkus(text);
      rows.push({
        productId: productId,
        productName: extractProductName(text),
        sellerSku: skus[0] || extractSellerSku(text) || '',
        sellerSkus: skus,
        status: st,
        stockQty: (function () {
          var m = text.match(/库存\s*[:：]?\s*(\d+)/) || text.match(/Stock\s*[:：]?\s*(\d+)/i);
          return m ? Number(m[1]) : null;
        })(),
        price: pm ? parseNumber(pm[0]) : null,
        salesQty: extractSalesQty(text),
        currencyHint: detectCurrency(text),
        rawCells: [text.slice(0, 160)]
      });
    }
    return rows.length ? { rows: rows, headers: ['id-blocks'], colMap: {}, source: 'id-blocks' } : null;
  }
  function parseBodyTextFallback() {
    var body = cleanText((document.body && document.body.innerText) || '');
    if (!body || body.length < 20) return null;
    // split by product id markers
    var parts = body.split(/(?=ID\s*[:：]\s*\d{10,22})/i);
    var rows = [], seen = {};
    for (var i = 0; i < parts.length; i++) {
      var text = cleanText(parts[i]).slice(0, 500);
      var productId = extractProductId(text);
      if (!productId || seen[productId]) continue;
      if (isSkuExpandNoise(text) && !/^\d{10,}$/.test(productId)) continue;
      seen[productId] = true;
      var skus = extractAllSellerSkus(text);
      var pm = text.match(/[£$€]\s*[0-9.,]+/);
      rows.push({
        productId: productId,
        productName: extractProductName(text),
        sellerSku: skus[0] || extractSellerSku(text) || '',
        sellerSkus: skus,
        status: '',
        stockQty: null,
        price: pm ? parseNumber(pm[0]) : null,
        salesQty: extractSalesQty(text),
        currencyHint: detectCurrency(text),
        rawCells: [text.slice(0, 120)]
      });
    }
    return rows.length ? { rows: rows, headers: ['body-text'], colMap: {}, source: 'body-text' } : null;
  }
  /** 点击列表里的「N 个 SKU 展开」，让规格 SKU 露出来后再解析 */
  function expandSkuRows() {
    var clicked = 0;
    var texts = [];
    var nodes = Array.prototype.slice.call(document.querySelectorAll('button,a,span,div,[role="button"]'));
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var tx = cleanText(el.textContent);
      if (!tx || tx.length > 28) continue;
      if (!(/\d+\s*个\s*SKU\s*展开/.test(tx) || /^SKU\s*展开$/i.test(tx) || /Expand\s+\d+\s+SKU/i.test(tx))) continue;
      try {
        el.click();
        clicked++;
        if (texts.length < 12) texts.push(tx);
      } catch (e) { /* ignore */ }
      if (clicked >= 40) break;
    }
    // 同步短等 DOM 展开（page.exec 无法 await）
    if (clicked > 0) {
      var until = Date.now() + 900;
      while (Date.now() < until) { /* spin */ }
    }
    return { clicked: clicked, samples: texts };
  }
  function mergeSkuIntoRows(baseRows, richRows) {
    if (!baseRows || !baseRows.length) return richRows || [];
    if (!richRows || !richRows.length) return baseRows;
    var byId = {};
    for (var i = 0; i < richRows.length; i++) {
      var r = richRows[i];
      if (r && r.productId) byId[r.productId] = r;
    }
    for (var j = 0; j < baseRows.length; j++) {
      var b = baseRows[j];
      var n = byId[b.productId];
      if (!n) continue;
      var skus = [];
      var seenSku = {};
      function addSku(s) {
        s = cleanText(s);
        if (!s || isSkuExpandNoise(s) || seenSku[s]) return;
        seenSku[s] = true;
        skus.push(s);
      }
      var arr1 = b.sellerSkus || [];
      var arr2 = n.sellerSkus || [];
      for (var a = 0; a < arr1.length; a++) addSku(arr1[a]);
      for (var c = 0; c < arr2.length; c++) addSku(arr2[c]);
      addSku(b.sellerSku);
      addSku(n.sellerSku);
      if (skus.length) {
        b.sellerSkus = skus;
        b.sellerSku = skus.length === 1 ? skus[0] : skus.join('|');
      }
      if ((!b.productName || isSkuExpandNoise(b.productName)) && n.productName) b.productName = n.productName;
      if (b.stockQty == null && n.stockQty != null) b.stockQty = n.stockQty;
      if (b.price == null && n.price != null) b.price = n.price;
    }
    return baseRows;
  }
  try {
    var url = location.href || '';
    var title = document.title || '';
    if (!url || url === 'about:blank') {
      return JSON.stringify({ ok: false, source: 'none', module: 'products', url: url, rows: [], error: 'about:blank' });
    }
    // 硬拒绝非商品页：订单/健康/财务/首页/广告等（防止脏数入库）
    var forbidden =
      /\/order(\?|\/|$)/i.test(url) ||
      /[?&]tab=all/i.test(url) ||
      /\/health-center/i.test(url) ||
      /\/finance\//i.test(url) ||
      /\/homepage/i.test(url) ||
      /\/ads-creation/i.test(url) ||
      /\/compass/i.test(url) ||
      /\/creator/i.test(url);
    var onProduct =
      /\/product\/manage/i.test(url) ||
      /\/product\/(list|all)/i.test(url);
    if (forbidden || !onProduct) {
      return JSON.stringify({
        ok: false,
        source: 'none',
        module: 'products',
        url: url,
        title: title,
        rows: [],
        rowCount: 0,
        error: 'wrong_page_not_product: ' + url,
        diag: {
          tables: document.querySelectorAll('table').length,
          bodyLen: ((document.body && document.body.innerText) || '').length,
          forbidden: !!forbidden,
          onProduct: !!onProduct
        }
      });
    }
    // 先展开多规格，再解析（补全 seller_sku）
    var expandInfo = expandSkuRows();
    var table = pickBestTable();
    var parsed = null, source = 'none';
    if (table) { parsed = parseHtmlTable(table); source = 'html-table'; }
    if (!parsed || !parsed.rows || parsed.rows.length === 0) {
      var fb = parseIdBlocks();
      if (fb) { parsed = fb; source = fb.source || 'id-blocks'; }
    }
    if (!parsed || !parsed.rows || parsed.rows.length === 0) {
      var fb2 = parseBodyTextFallback();
      if (fb2) { parsed = fb2; source = fb2.source || 'body-text'; }
    }
    // 展开后用 id-blocks / body 再补一轮 SKU
    if (parsed && parsed.rows && parsed.rows.length && expandInfo.clicked > 0) {
      var rich = parseIdBlocks() || parseBodyTextFallback();
      if (rich && rich.rows && rich.rows.length) {
        parsed.rows = mergeSkuIntoRows(parsed.rows, rich.rows);
        source = source + '+sku-expand';
      }
    }
    var rows = parsed && parsed.rows ? parsed.rows : [];
    // 最终再滤一遍噪声行
    rows = rows.filter(function (r) {
      if (!r || !r.productId) return false;
      if (isSkuExpandNoise(r.productId) || isSkuExpandNoise(r.productName || '')) return false;
      if (/^name:/.test(r.productId) && /SKU|展开|expand/i.test(r.productId)) return false;
      return true;
    });
    // 多 SKU 时 sellerSku 用 | 连接，便于检索；完整数组保留 sellerSkus
    for (var si = 0; si < rows.length; si++) {
      var rr = rows[si];
      var list = rr.sellerSkus || [];
      if ((!list || !list.length) && rr.sellerSku) list = [rr.sellerSku];
      list = (list || []).filter(function (x) { return x && !isSkuExpandNoise(x); });
      rr.sellerSkus = list;
      if (list.length === 1) rr.sellerSku = list[0];
      else if (list.length > 1) rr.sellerSku = list.join('|');
      else rr.sellerSku = rr.sellerSku || '';
    }
    var currencyHits = { USD: 0, GBP: 0, EUR: 0, CNY: 0 };
    for (var ri = 0; ri < rows.length; ri++) {
      var c = rows[ri].currencyHint;
      if (c && currencyHits[c] != null) currencyHits[c]++;
    }
    var currency = 'GBP', max = -1;
    var ks = Object.keys(currencyHits);
    for (var k = 0; k < ks.length; k++) {
      if (currencyHits[ks[k]] > max) { max = currencyHits[ks[k]]; currency = ks[k]; }
    }
    if (max <= 0) currency = 'GBP';
    var ok = rows.length > 0;
    return JSON.stringify({
      ok: ok, source: source, module: 'products', url: url, title: title,
      currency: currency, currencyHits: currencyHits,
      headers: parsed && parsed.headers ? parsed.headers : [],
      colMap: parsed && parsed.colMap ? parsed.colMap : {},
      rows: rows, rowCount: rows.length,
      expand: expandInfo,
      diag: { tables: document.querySelectorAll('table').length, bodyLen: ((document.body && document.body.innerText) || '').length, expandClicked: expandInfo.clicked },
      error: ok ? null : 'no product table. url=' + url
    });
  } catch (e) {
    return JSON.stringify({ ok: false, source: 'none', module: 'products', url: location.href || '', rows: [], error: String(e && e.message ? e.message : e) });
  }
})();
