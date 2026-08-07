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
    s = s.replace(/[,\s]/g, '').replace(/[¥$€£￥]/g, '');
    s = s.replace(/USD|GBP|EUR|CNY|RMB/gi, '').replace(/%/g, '');
    var paren = s.match(/^\((.+)\)$/);
    if (paren) s = '-' + paren[1];
    var n = Number(s);
    return isFinite(n) ? n : null;
  }

  function extractOrderId(text) {
    var s = cleanText(text);
    if (!s) return '';
    var m = s.match(/\b(57\d{16})\b/) || s.match(/\b(\d{18})\b/) || s.match(/\b(\d{15,20})\b/);
    return m ? m[1] : '';
  }

  function extractOrderTime(text) {
    // 只从「订单」列取下单/展示时间；禁止吃物流「送达截止日期」等未来日
    var s = cleanText(text);
    if (!s) return '';
    // 订单号常与相对时间粘连：5769…72428 分钟前
    s = s.replace(/57\d{16}/g, ' ');
    s = s.replace(/\b\d{15,20}\b/g, ' ');
    s = s.replace(/\s+/g, ' ').trim();
    // 明确排除截止/送达类文案（即便混进订单列）
    if (/截止|送达日期|delivery\s*by|arrive/i.test(s) && !/分钟前|小时前|天前|今天|昨天|星期/.test(s)) {
      // 若整段主要是截止日期，仍尝试抽相对时间；无则空
    }
    var m =
      s.match(/(\d{1,4}\s*分钟前)/) ||
      s.match(/(\d{1,4}\s*小时前)/) ||
      s.match(/(\d{1,4}\s*天前)/) ||
      s.match(/(昨天\s*\d{1,2}:\d{2}(?::\d{2})?)/) ||
      s.match(/(今天\s*\d{1,2}:\d{2}(?::\d{2})?)/) ||
      // 星期X + 时分（UK 后台常见：星期一 23:32:30）
      s.match(/((?:星期|周)[一二三四五六日天]\s*\d{1,2}:\d{2}(?::\d{2})?)/) ||
      // 绝对日期：仅当不像「截止」
      (!/截止|送达日期/i.test(s)
        ? s.match(/(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\s*\d{1,2}:\d{2}(?::\d{2})?)/)
        : null) ||
      (!/截止|送达日期/i.test(s) ? s.match(/(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})/) : null);
    return m ? cleanText(m[1]) : '';
  }

  /** @deprecated use extractOrderTime — 保留名避免外部引用断裂 */
  function extractRelativeTime(text) {
    return extractOrderTime(text);
  }

  function extractQty(text) {
    var s = cleanText(text);
    var m = s.match(/(?:^|[^\d])(\d{1,3})\s*件商品/);
    return m ? Number(m[1]) : null;
  }

  var HEADER_ALIASES = {
    orderId: ['订单号', '订单编号', '订单', 'order id', 'order no', 'order number', 'order'],
    orderStatus: ['订单状态', 'order status'],
    productName: ['商品信息', '商品', '产品名称', 'product', 'product name', 'item'],
    payAmount: ['合计', '实付', '订单金额', 'total', 'pay amount'],
    shippingMethod: ['物流方式', 'shipping method', 'fulfillment type'],
    shippingOption: ['物流选项', 'shipping option'],
    buyer: ['客户', '买家', 'customer', 'buyer']
  };

  function matchField(header) {
    var h = cleanText(header).toLowerCase();
    if (!h) return null;
    var best = null;
    var bestLen = 0;
    var fields = Object.keys(HEADER_ALIASES);
    for (var fi = 0; fi < fields.length; fi++) {
      var field = fields[fi];
      var aliases = HEADER_ALIASES[field];
      for (var ai = 0; ai < aliases.length; ai++) {
        var al = aliases[ai].toLowerCase();
        if (h === al || h.indexOf(al) >= 0) {
          if (al.length >= bestLen) {
            best = field;
            bestLen = al.length;
          }
        }
      }
    }
    if (!best && (h === '状态' || h === 'status')) best = 'orderStatus';
    return best;
  }

  function defaultColMap() {
    return {
      orderId: 1,
      buyer: 2,
      productName: 3,
      orderStatus: 4,
      shippingMethod: 5,
      shippingOption: 6,
      payAmount: 7
    };
  }

  function scoreTable(table) {
    var trs = Array.prototype.slice.call(table.querySelectorAll('tr'));
    if (trs.length < 2) return 0;
    var headCells = Array.prototype.slice.call(trs[0].querySelectorAll('th,td')).map(function (c) {
      return cleanText(c.textContent);
    });
    var hits = 0;
    var fields = {};
    for (var i = 0; i < headCells.length; i++) {
      var f = matchField(headCells[i]);
      if (f) {
        hits++;
        fields[f] = true;
      }
    }
    if (!fields.orderId && !fields.orderStatus && !fields.payAmount) return 0;
    return hits * 10 + Math.min(trs.length, 80);
  }

  function pickBestTable() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('table'));
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var s = scoreTable(t);
      var oidN = t.querySelectorAll('.order_id_number, [class*="order_id"]').length;
      if (oidN > 0) s += 20 + Math.min(oidN, 30);
      if (s > bestScore) {
        bestScore = s;
        best = t;
      }
    }
    return bestScore >= 10 ? best : null;
  }

  function parseRow(tr, colMap) {
    var cellEls = Array.prototype.slice.call(tr.querySelectorAll('td,th'));
    if (!cellEls.length) return null;
    var cells = cellEls.map(function (c) {
      return cleanText(c.textContent);
    });
    function get(f) {
      return colMap[f] != null ? cells[colMap[f]] || '' : '';
    }

    var orderId = '';
    var oidEl = tr.querySelector('.order_id_number, [class*="order_id"]');
    if (oidEl) orderId = extractOrderId(oidEl.textContent);
    if (!orderId) orderId = extractOrderId(get('orderId'));
    if (!orderId) orderId = extractOrderId(cells.join(' '));
    if (!orderId) return null;

    var orderCell = get('orderId') || (colMap.orderId != null ? cells[colMap.orderId] : cells[1] || '');
    // 关键：只从订单列取时间。全行 join 会误吃「送达截止日期：2026/8/3」→ 未来 biz_date
    var createTime = extractOrderTime(orderCell);
    if (!createTime) {
      // 次选：整行里仅相对时间（分钟前/今天/星期），仍禁止绝对「截止」日
      var blobForTime = cells.join(' ');
      var relOnly = cleanText(blobForTime)
        .replace(/\b57\d{16}\b/g, ' ')
        .replace(/\b\d{15,20}\b/g, ' ');
      var rm =
        relOnly.match(/(\d+\s*分钟前)/) ||
        relOnly.match(/(\d+\s*小时前)/) ||
        relOnly.match(/(\d+\s*天前)/) ||
        relOnly.match(/(昨天\s*\d{1,2}:\d{2}(?::\d{2})?)/) ||
        relOnly.match(/(今天\s*\d{1,2}:\d{2}(?::\d{2})?)/) ||
        relOnly.match(/((?:星期|周)[一二三四五六日天]\s*\d{1,2}:\d{2}(?::\d{2})?)/);
      if (rm) createTime = cleanText(rm[1]);
    }
    var productCell = get('productName') || '';
    var quantity = extractQty(productCell);
    if (quantity == null) quantity = extractQty(cells.join(' ')) || 0;
    var productName = productCell || '';
    var payRaw = get('payAmount') || '';
    var payAmount = parseNumber(payRaw);
    var status = get('orderStatus') || '';
    var shipping = get('shippingMethod') || get('shippingOption') || '';
    var buyer = get('buyer') || '';
    var blob = cells.join(' ');

    return {
      orderId: orderId,
      orderStatus: status,
      payTime: '',
      createTime: createTime,
      createTimeRaw: orderCell.slice(0, 80),
      productName: productName,
      sellerSku: '',
      skuId: '',
      quantity: quantity,
      payAmount: payAmount != null ? payAmount : 0,
      shippingStatus: shipping,
      buyerRegion: '',
      buyer: buyer,
      currencyHint: detectCurrency(payRaw) || detectCurrency(blob),
      rawCells: cells.slice(0, 10)
    };
  }

  function parseHtmlTable(table) {
    var trs = Array.prototype.slice.call(table.querySelectorAll('tr'));
    if (trs.length < 1) return { rows: [], headers: [], colMap: {} };
    var headIdx = -1;
    var i;
    for (i = 0; i < Math.min(3, trs.length); i++) {
      var cells = Array.prototype.slice.call(trs[i].querySelectorAll('th,td')).map(function (c) {
        return cleanText(c.textContent);
      });
      var hits = 0;
      for (var hi = 0; hi < cells.length; hi++) if (matchField(cells[hi])) hits++;
      var hasOid = false;
      for (var oi = 0; oi < cells.length; oi++) if (extractOrderId(cells[oi])) hasOid = true;
      if (hits >= 2 && !hasOid) {
        headIdx = i;
        break;
      }
    }
    var colMap = {};
    var headCells = [];
    if (headIdx >= 0) {
      headCells = Array.prototype.slice.call(trs[headIdx].querySelectorAll('th,td')).map(function (c) {
        return cleanText(c.textContent);
      });
      headCells.forEach(function (h, idx) {
        var f = matchField(h);
        if (f && colMap[f] == null) colMap[f] = idx;
      });
    }
    var def = defaultColMap();
    Object.keys(def).forEach(function (k) {
      if (colMap[k] == null) colMap[k] = def[k];
    });
    if (!headCells.length) headCells = ['', '订单', '客户', '商品', '订单状态', '物流方式', '物流选项', '合计'];

    var rows = [];
    var seen = {};
    var start = headIdx >= 0 ? headIdx + 1 : 0;
    for (var r = start; r < trs.length; r++) {
      var row = parseRow(trs[r], colMap);
      if (!row || seen[row.orderId]) continue;
      seen[row.orderId] = true;
      rows.push(row);
    }
    return { colMap: colMap, rows: rows, headers: headCells };
  }

  function parseOrderIdNodes() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('.order_id_number, [class*="order_id"]'));
    if (!nodes.length) return null;
    var rows = [];
    var seen = {};
    var colMap = defaultColMap();
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var orderId = extractOrderId(n.textContent);
      if (!orderId || seen[orderId]) continue;
      seen[orderId] = true;
      var tr = n.closest('tr');
      if (tr) {
        var row = parseRow(tr, colMap);
        if (row) {
          rows.push(row);
          continue;
        }
      }
      var text = cleanText((tr || n).textContent).slice(0, 400);
      var payM = text.match(/[£$€]\s*([0-9]+(?:\.[0-9]+)?)/);
      var quantity = extractQty(text) || 0;
      var status = '';
      var sm = text.match(/(等待中|等待打包|待揽收|已发货|已完成|已取消|待发货|运输中)/);
      if (sm) status = sm[1];
      rows.push({
        orderId: orderId,
        orderStatus: status,
        payTime: '',
        createTime: extractOrderTime(text),
        createTimeRaw: text.slice(0, 80),
        productName: '',
        sellerSku: '',
        skuId: '',
        quantity: quantity,
        payAmount: payM ? parseNumber(payM[0]) : 0,
        shippingStatus: '',
        buyerRegion: '',
        buyer: '',
        currencyHint: detectCurrency(text),
        rawCells: [text.slice(0, 160)]
      });
    }
    return rows.length ? { rows: rows, headers: ['order_id_number'], colMap: {}, source: 'order-id-nodes' } : null;
  }

  try {
    var url = location.href || '';
    var title = document.title || '';
    var parsed = null;
    var source = 'none';
    var table = pickBestTable();
    if (table) {
      parsed = parseHtmlTable(table);
      source = 'html-table';
    }
    if (!parsed || !parsed.rows || parsed.rows.length === 0) {
      var fb = parseOrderIdNodes();
      if (fb) {
        parsed = fb;
        source = fb.source || 'order-id-nodes';
      }
    }

    var rows = parsed && parsed.rows ? parsed.rows : [];
    var currencyHits = { USD: 0, GBP: 0, EUR: 0, CNY: 0 };
    for (var ri = 0; ri < rows.length; ri++) {
      var c = rows[ri].currencyHint;
      if (c && currencyHits[c] != null) currencyHits[c]++;
    }
    var currency = 'GBP';
    var max = -1;
    var keys = Object.keys(currencyHits);
    for (var ki = 0; ki < keys.length; ki++) {
      var k = keys[ki];
      if (currencyHits[k] > max) {
        max = currencyHits[k];
        currency = k;
      }
    }
    if (max <= 0) currency = 'GBP';

    var ok = rows.length > 0;
    return JSON.stringify({
      ok: ok,
      source: source,
      module: 'orders',
      url: url,
      title: title,
      currency: currency,
      currencyHits: currencyHits,
      headers: parsed && parsed.headers ? parsed.headers : [],
      colMap: parsed && parsed.colMap ? parsed.colMap : {},
      rows: rows,
      rowCount: rows.length,
      error: ok ? null : 'no order table. url=' + url
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      source: 'none',
      module: 'orders',
      url: location.href || '',
      rows: [],
      error: String(e && e.message ? e.message : e)
    });
  }
})();
