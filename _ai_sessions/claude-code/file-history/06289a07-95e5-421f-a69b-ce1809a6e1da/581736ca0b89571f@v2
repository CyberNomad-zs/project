/* TikTok seller center: 内容分析 → 商品卡 / 商品数据分析 (P2.0 POC).
 * Ziniao page exec. Card KPIs + product table (exposure/CTR/CVR).
 */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function detectCurrency(text) {
    var s = String(text || '');
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
    var pct = s.match(/^(-?[\d,]+(?:\.\d+)?)\s*%$/);
    if (pct) {
      var p = Number(String(pct[1]).replace(/,/g, ''));
      return isFinite(p) ? p : null;
    }
    /* 24.50K / 1.2万 / 3M */
    var km = s.match(/-?\s*[¥$€£￥]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*([KkMm万亿])/);
    if (km) {
      var base = Number(String(km[1]).replace(/,/g, ''));
      if (isFinite(base)) {
        var u = km[2];
        if (u === 'K' || u === 'k') return base * 1000;
        if (u === 'M' || u === 'm') return base * 1000000;
        if (u === '万') return base * 10000;
        if (u === '亿') return base * 100000000;
      }
    }
    var m = s.match(/-?\s*[¥$€£￥]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)/);
    if (m) {
      var n0 = Number(String(m[1]).replace(/,/g, ''));
      if (isFinite(n0)) return n0;
    }
    s = s.replace(/[,\s]/g, '').replace(/[¥$€£￥]/g, '').replace(/%/g, '');
    var n = Number(s);
    return isFinite(n) ? n : null;
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function findByRegex(body, patterns) {
    for (var i = 0; i < patterns.length; i++) {
      var m = body.match(patterns[i]);
      if (!m) continue;
      var raw = m[1] != null ? m[1] : m[0];
      var n = parseNumber(raw);
      if (n != null) return { value: n, label: String(m[0]).slice(0, 120) };
    }
    return null;
  }
  function cellText(el) {
    return clean(el && (el.innerText || el.textContent));
  }
  function matchProductHeader(h) {
    var t = clean(h).toLowerCase();
    if (!t) return null;
    /* 操作列 */
    if (/^action$|^操作$|^详情$|^details?$/.test(t)) return null;
    if (/商品\s*id|product\s*id|\bid\b/.test(t) && !/视频|video|card\s*name/.test(t)) return 'productId';
    /* 英文 UK 站：View-to-paid rate / Viewers（≠ 视频 Views） */
    if (
      /曝光\s*到\s*成交|曝光.*转化|\bcvr\b|转化率|conversion\s*rate|view[\s\-]*to[\s\-]*paid|paid\s*rate|viewers?\s*to\s*paid/i.test(
        t
      )
    )
      return 'cvr';
    if (
      /曝光\s*用户|曝光数|impression|show|展示|viewers?\b|unique\s*viewers?|product\s*views?\b/i.test(t) &&
      !/paid|转化|rate|ctr|cvr/.test(t)
    )
      return 'impressions';
    if (/点击|clicks?/.test(t) && !/率|rate|ctr/.test(t)) return 'clicks';
    if (/\bctr\b|点击率|click-?through/.test(t)) return 'ctr';
    if (/订单|orders?|销量|units?|sku\s*订单/.test(t)) return 'orders';
    if (/\bgmv\b|销售额|成交额|revenue/.test(t)) return 'gmv';
    if (/渠道|channel|来源|source|流量来源/.test(t) && !/resource/.test(t)) return 'channel';
    if (/日\s*客户|客户数|customers?/.test(t)) return 'customers';
    if (
      /商品卡\s*名称|product\s*card\s*name|商品名称|product\s*name|名称|title|name/.test(t) &&
      !/曝光|点击|gmv|订单|ctr|cvr|转化|viewer|paid|impression/.test(t)
    )
      return 'title';
    if (/商品|product/.test(t) && !/曝光|点击|gmv|订单|ctr|cvr|转化|viewer|paid|impression|card\s*analytics/.test(t))
      return 'title';
    return null;
  }
  /** 经典 5 列：名称 | GMV | CVR% | 曝光 | 操作 — 表头映射不全时按单元格形态回填 */
  function enrichProductRowFromCells(row) {
    var cells = row.rawCells || [];
    if (!cells.length) return row;
    var money = null;
    var pct = null;
    var bigNum = null;
    for (var i = 0; i < cells.length; i++) {
      var t = clean(cells[i]);
      if (!t || /details?|详情|操作/i.test(t)) continue;
      /* 长标题 / 含 ID: 不当指标 */
      if (/\bID:\s*\d{6,}/i.test(t) && t.length > 24) continue;
      if (/^[£$€¥￥]/.test(t) || (/[£$€¥￥]/.test(t) && parseNumber(t) != null)) {
        if (money == null) money = parseNumber(t);
        continue;
      }
      if (/%\s*$/.test(t) || /^\d+(\.\d+)?\s*%$/.test(t)) {
        if (pct == null) pct = parseNumber(t);
        continue;
      }
      if (/[KkMm万亿]/.test(t)) {
        var nK = parseNumber(t);
        if (nK != null && (bigNum == null || nK > bigNum)) bigNum = nK;
        continue;
      }
      if (/^\d[\d,]*(\.\d+)?$/.test(t)) {
        var n2 = parseNumber(t);
        var digits = String(t).replace(/[^\d]/g, '');
        if (
          n2 != null &&
          n2 >= 100 &&
          n2 < 1000000000 &&
          digits.length <= 9 &&
          (bigNum == null || n2 > bigNum)
        ) {
          bigNum = n2;
        }
      }
    }
    if (row.gmv == null && money != null) row.gmv = money;
    if (row.cvr == null && pct != null) row.cvr = pct;
    if (row.impressions == null && bigNum != null) row.impressions = bigNum;
    return row;
  }
  function scrapeProductTable() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('table'));
    var best = [];
    var bestHeaders = [];
    var bestScore = -1;
    for (var ti = 0; ti < tables.length; ti++) {
      var table = tables[ti];
      var ths = table.querySelectorAll('thead th, tr th');
      if (!ths.length) continue;
      var fields = [];
      var headers = [];
      for (var hi = 0; hi < ths.length; hi++) {
        var ht = cellText(ths[hi]);
        headers.push(ht);
        fields.push(matchProductHeader(ht));
      }
      var mapped = fields.filter(Boolean).length;
      if (mapped < 2) continue;
      var rows = table.querySelectorAll('tbody tr');
      var items = [];
      for (var ri = 0; ri < rows.length && items.length < 80; ri++) {
        var tds = rows[ri].querySelectorAll('td');
        if (!tds.length) continue;
        var row = { rawCells: [] };
        for (var ci = 0; ci < tds.length; ci++) {
          var txt = cellText(tds[ci]);
          row.rawCells.push(txt);
          var f = fields[ci];
          if (!f) continue;
          if (f === 'title' || f === 'productId' || f === 'channel') {
            row[f] = txt;
            if (f === 'title' || f === 'productId') {
              var a = tds[ci].querySelector('a[href]');
              if (a) {
                row.href = a.href || a.getAttribute('href') || null;
                if (!row.productId) {
                  var pm =
                    String(row.href || '').match(/(?:product-card-details|product[_/]?id)[=/](\d+)/i) ||
                    String(row.href || '').match(/[?&]id=(\d{6,})/i) ||
                    String(row.href || '').match(/\/product\/(\d+)/) ||
                    String(txt).match(/\bID:\s*(\d{6,})\b/i) ||
                    String(txt).match(/\b(\d{10,})\b/);
                  if (pm) row.productId = pm[1];
                }
              } else if (f === 'title' && !row.productId) {
                var idm = String(txt).match(/\bID:\s*(\d{6,})\b/i) || String(txt).match(/\b(\d{10,})\b/);
                if (idm) row.productId = idm[1];
              }
            }
          } else {
            row[f] = parseNumber(txt);
          }
        }
        enrichProductRowFromCells(row);
        if (
          row.productId ||
          row.title ||
          row.impressions != null ||
          row.clicks != null ||
          row.ctr != null ||
          row.gmv != null
        ) {
          items.push(row);
        }
      }
      /* 优先选「映射字段多 + 行上有曝光/转化」的表，避免只含 GMV 的弱表赢 */
      var metricRows = items.filter(function (it) {
        return it.impressions != null || it.cvr != null || it.clicks != null;
      }).length;
      var score = mapped * 100 + items.length + metricRows * 10;
      if (score > bestScore) {
        bestScore = score;
        best = items;
        bestHeaders = headers;
      }
    }
    return { products: best, headers: bestHeaders };
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    var title = document.title || '';
    var windowLabel = null;
    var wm =
      body.match(/最近\s*\d+\s*天/) ||
      body.match(/近\s*\d+\s*天/) ||
      body.match(/过去\s*\d+\s*天/) ||
      body.match(/Last\s*\d+\s*days?/i) ||
      body.match(/Past\s*\d+\s*days?/i) ||
      body.match(/GMT[+\-]?\d{0,2}:?\d{0,2}/i) && body.match(/最近\s*\d+|近\s*\d+|Last\s*\d+/i) ||
      body.match(/\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\s*[\-~至]\s*\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}/) ||
      body.match(/Yesterday|昨天|Today|今天/i);
    if (wm) windowLabel = typeof wm[0] === 'string' ? wm[0] : String(wm[0]);
    /* 商品卡页默认近 7 天窗口；未解析到文案时仍标注，避免 raw_extra.window 全空 */
    if (!windowLabel && /product-card-analytics/i.test(url)) {
      windowLabel = '最近7天(default)';
    }

    var kpis = {
      impressions: findByRegex(body, [
        /曝光用户数\s*([\d,.]+[KkMm万亿]?)/i,
        /商品\s*曝光\s*([£$€]?[\d,.]+[KkMm万亿]?)/i,
        /曝光数?\s*([\d,.]+[KkMm万亿]?)/,
        /Impressions?\s*([\d,.]+[KkMm万亿]?)/i
      ]),
      clicks: findByRegex(body, [
        /点击数?\s*([\d,.]+[KkMm万亿]?)/,
        /Clicks?\s*([\d,.]+[KkMm万亿]?)/i
      ]),
      ctr: findByRegex(body, [/点击率\s*([\d.]+)\s*%?/, /\bCTR\s*([\d.]+)\s*%?/i]),
      orders: findByRegex(body, [
        /SKU\s*订单数?\s*([\d,.]+)/i,
        /订单数?\s*([\d,.]+)/,
        /Orders?\s*([\d,.]+)/i
      ]),
      gmv: findByRegex(body, [
        /GMV\s*([£$€]?[\d,]+\.?\d*)/i,
        /成交额\s*([£$€]?[\d,]+\.?\d*)/,
        /销售额\s*([£$€]?[\d,]+\.?\d*)/
      ]),
      cvr: findByRegex(body, [
        /曝光到成交转化率\s*([\d.]+)\s*%?/,
        /转化率\s*([\d.]+)\s*%?/,
        /\bCVR\s*([\d.]+)\s*%?/i
      ]),
      customers: findByRegex(body, [/日客户数\s*([\d,.]+)/, /客户数\s*([\d,.]+)/i])
    };

    var tbl = scrapeProductTable();
    var kpiFlat = {};
    var kpiHits = {};
    Object.keys(kpis).forEach(function (k) {
      if (kpis[k]) {
        kpiFlat[k] = kpis[k].value;
        kpiHits[k] = kpis[k].label;
      } else {
        kpiFlat[k] = null;
      }
    });

    var pageHints = {
      hasProductCardNav: /商品卡|Product\s*card|商品数据|Product\s*analytics|商品分析/i.test(body),
      hasTrafficWord: /曝光|点击|CTR|CVR|Impression/i.test(body)
    };

    var hasKpi = Object.keys(kpiFlat).some(function (k) {
      return kpiFlat[k] != null;
    });
    var hasRows = tbl.products && tbl.products.length > 0;
    var ok = !!(hasKpi || hasRows);

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 500),
      window: windowLabel,
      kpiHits: kpiHits,
      tableHeaders: tbl.headers,
      productRowCount: tbl.products.length,
      pageHints: pageHints
    };

    if (!ok) {
      return JSON.stringify({
        ok: false,
        module: 'product_traffic',
        source: 'product-traffic-poc',
        url: url,
        title: title,
        window: windowLabel,
        currency: detectCurrency(body),
        kpis: kpiFlat,
        products: [],
        raw: raw,
        error:
          'no product traffic KPI or rows. Confirm URL is 内容分析→商品卡/商品数据. url=' + url
      });
    }

    return JSON.stringify({
      ok: true,
      module: 'product_traffic',
      source: 'product-traffic-poc',
      url: url,
      title: title,
      window: windowLabel,
      currency: detectCurrency(body) || 'GBP',
      channelDefault: 'product_card',
      kpis: kpiFlat,
      products: tbl.products,
      raw: raw,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'product_traffic',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
