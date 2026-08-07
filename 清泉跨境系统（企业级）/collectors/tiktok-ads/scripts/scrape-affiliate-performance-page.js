/* TikTok affiliate center: 数据分析 → 表现 (P3.0 POC).
 * Host: affiliate.tiktok.com/insights/transaction-analysis
 * Ziniao page exec. Store-level KPIs + creator rows.
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
  function normalizeMoneyText(s) {
    /* "£ 164 .96" / "£164.96" / "30.9 万" → compact */
    return String(s || '')
      .replace(/([£$€¥￥])\s+/g, '$1')
      .replace(/(\d)\s+\.\s*(\d)/g, '$1.$2')
      .replace(/(\d)\s+([KkMm万亿])/g, '$1$2');
  }
  function parseNumber(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && isFinite(value)) return value;
    var s = normalizeMoneyText(String(value).trim());
    if (!s || s === '-' || s === '—' || s === '--') return null;
    /* first token before percent-delta often is the metric */
    var first = s.split(/\s+/)[0];
    var pct = first.match(/^(-?[\d,]+(?:\.\d+)?)\s*%$/);
    if (pct) {
      var p = Number(String(pct[1]).replace(/,/g, ''));
      return isFinite(p) ? p : null;
    }
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
    var b = normalizeMoneyText(body);
    for (var i = 0; i < patterns.length; i++) {
      var m = b.match(patterns[i]);
      if (!m) continue;
      var raw = m[1] != null ? m[1] : m[0];
      var n = parseNumber(raw);
      if (n != null) return { value: n, label: String(m[0]).slice(0, 140) };
    }
    return null;
  }
  function cellText(el) {
    return clean(el && (el.innerText || el.textContent));
  }
  function extractCreatorId(href, text) {
    var s = String(href || '');
    var m =
      s.match(/[?&](?:creator_id|creatorId|author_id|authorId|uid|user_id|userId|oec_id|oecId)=([A-Za-z0-9_-]{4,})/i) ||
      s.match(/\/(?:creator|author|user|influencer)\/([A-Za-z0-9_.-]{3,})/i) ||
      s.match(/\/@([A-Za-z0-9_.]{2,})/);
    if (m) return m[1];
    var t = String(text || '');
    var tm =
      t.match(/(?:ID|id|Uid|UID)[:：\s#]*([A-Za-z0-9_-]{5,})/) ||
      t.match(/@([A-Za-z0-9_.]{2,30})/);
    return tm ? tm[1] : null;
  }
  function parseCreatorCell(txt) {
    /* "countrylass65 Gillian Dickin 家装建材, +2 1412 粉丝数" */
    var t = clean(txt);
    var handle = null;
    var displayName = null;
    var hm = t.match(/^@?([A-Za-z0-9._]{2,64})\b/);
    if (hm) handle = hm[1];
    /* display name: after handle until category/fans marker */
    if (handle) {
      var rest = clean(t.slice(handle.length));
      rest = rest.replace(/^@\s*/, '');
      var cut = rest.search(
        /\s(?:家装|居家|女装|男装|美妆|家电|数码|食品|母婴|运动|宠物|汽车|珠宝|鞋靴|箱包|服饰|内衣|粉丝数|,|\+)/
      );
      if (cut > 0) displayName = clean(rest.slice(0, cut));
      else {
        var parts = rest.split(/\s+/).filter(Boolean);
        if (parts.length) {
          var nameParts = [];
          for (var i = 0; i < parts.length && i < 4; i++) {
            if (/^\d/.test(parts[i]) || /粉丝|万|ATA|TT\s*MEDIA|Consulting/i.test(parts[i])) break;
            if (/[一-鿿]{2,}/.test(parts[i]) && /装|用|电|妆|服/.test(parts[i])) break;
            nameParts.push(parts[i]);
          }
          if (nameParts.length) displayName = nameParts.join(' ');
        }
      }
    }
    return {
      handle: handle,
      displayName: displayName || handle || t.slice(0, 80),
      raw: t
    };
  }
  function matchCreatorHeader(h) {
    var t = clean(h);
    if (!t) return null;
    var low = t.toLowerCase();
    if (/达人\s*id|creator\s*id|author\s*id|user\s*id|\buid\b/i.test(t)) return 'creatorId';
    if (/^达人$|^creator$|^influencer$|达人名称|creator\s*name|nickname|昵称/i.test(t)) return 'creatorName';
    if (/达人\s*归因\s*gmv|creator\s*attributed\s*gmv|归因\s*gmv|affiliate\s*gmv/i.test(t)) return 'gmv';
    if (/退款金额|refund\s*amount|^refunds?$/i.test(t)) return 'refundAmount';
    if (/预计\s*佣金|预估\s*佣金|estimat(ed)?\s*commission|^commission$/i.test(t)) return 'estCommission';
    if (/归因\s*订单|attributed\s*orders?|^订单数$|^orders?$/i.test(t)) return 'orders';
    if (/达人\s*归因\s*成交件数|归因\s*成交件数|成交件数|units?\s*sold|items?\s*sold/i.test(t)) return 'orderUnits';
    if (/已退款的商品件数|refunded\s*(units|items)/i.test(t)) return 'refundUnits';
    if (/^视频数$|^videos?$|video\s*count/i.test(t) && !/播放|play|view/i.test(t)) return 'videoCnt';
    if (/^直播数$|^lives?$|live\s*streams?/i.test(t)) return 'liveCnt';
    if (/商品销量|units?\s*sold|item\s*sales/i.test(t) && !/成交件/.test(t)) return 'productSold';
    if (/已发货样品|samples?\s*shipped|sample\s*sent/i.test(t)) return 'samplesShipped';
    if (/点击成交转化|cvr|conversion\s*rate/i.test(t)) return 'cvr';
    if (/样品内容|sample\s*content/i.test(t)) return 'sampleContent';
    if (/视频播放|video\s*views?|play\s*count|播放量/i.test(t)) return 'videoViews';
    if (/合作类型|collab|campaign\s*type/i.test(t)) return 'collabType';
    if (/类目|category/i.test(t)) return 'productCat';
    if (/操作|actions?|detail/i.test(t)) return 'action';
    /* loose name fallback last */
    if (/达人|creator|influencer|username|handle|name/i.test(t) && !/gmv|订单|佣金|commission|video|视频|refund|退款|成交|样品/i.test(t))
      return 'creatorName';
    if (/\bgmv\b/i.test(low)) return 'gmv';
    return null;
  }
  function scrapeCreatorTable() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('table'));
    var best = [];
    var bestHeaders = [];
    var bestFields = [];
    for (var ti = 0; ti < tables.length; ti++) {
      var table = tables[ti];
      /* prefer last header row in thead (filters often sit above) */
      var headerRow = null;
      var theadRows = table.querySelectorAll('thead tr');
      if (theadRows.length) headerRow = theadRows[theadRows.length - 1];
      var ths = headerRow
        ? headerRow.querySelectorAll('th')
        : table.querySelectorAll('tr th');
      if (!ths.length) continue;
      var fields = [];
      var headers = [];
      for (var hi = 0; hi < ths.length; hi++) {
        var ht = cellText(ths[hi]);
        headers.push(ht);
        fields.push(matchCreatorHeader(ht));
      }
      var mapped = fields.filter(Boolean).length;
      if (mapped < 2) continue;
      if (headers.join(' ').indexOf('达人归因 GMV') < 0 && headers.join(' ').indexOf('GMV') < 0) {
        /* still allow if enough creator metrics */
        if (mapped < 4) continue;
      }
      var rows = table.querySelectorAll('tbody tr');
      var items = [];
      for (var ri = 0; ri < rows.length && items.length < 80; ri++) {
        var tds = rows[ri].querySelectorAll('td');
        if (!tds.length) continue;
        var row = { rawCells: [], source: 'table' };
        for (var ci = 0; ci < tds.length; ci++) {
          var txt = cellText(tds[ci]);
          row.rawCells.push(txt);
          var f = fields[ci];
          var a = tds[ci].querySelector('a[href]');
          if (a) {
            row.href = a.href || a.getAttribute('href') || row.href || null;
            var idA = extractCreatorId(row.href, txt);
            if (idA) row.creatorId = row.creatorId || idA;
          }
          if (!f || f === 'action') continue;
          if (f === 'creatorName') {
            var pc = parseCreatorCell(txt);
            row.creatorName = pc.displayName;
            row.creatorHandle = pc.handle;
            if (pc.handle && !row.creatorId) row.creatorId = pc.handle;
            row.creatorCellRaw = pc.raw;
          } else if (f === 'creatorId' || f === 'collabType' || f === 'productCat') {
            row[f] = txt;
          } else if (f === 'cvr') {
            row[f] = parseNumber(txt);
          } else {
            row[f] = parseNumber(txt);
          }
        }
        if (!row.creatorId) {
          var idC = extractCreatorId(row.href, (row.rawCells || []).join(' '));
          if (idC) row.creatorId = idC;
        }
        if (!row.creatorId && row.rawCells[0]) {
          var pc0 = parseCreatorCell(row.rawCells[0]);
          if (pc0.handle) {
            row.creatorId = pc0.handle;
            row.creatorHandle = row.creatorHandle || pc0.handle;
            row.creatorName = row.creatorName || pc0.displayName;
          }
        }
        if (row.creatorName || row.creatorId || row.gmv != null || row.orderUnits != null || row.estCommission != null) {
          items.push(row);
        }
      }
      if (items.length > best.length) {
        best = items;
        bestHeaders = headers;
        bestFields = fields;
      }
    }
    return { creators: best, headers: bestHeaders, fields: bestFields };
  }
  function scrapeCreatorLinks() {
    var out = [];
    var seen = {};
    var anchors = document.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length && out.length < 40; i++) {
      var a = anchors[i];
      var href = a.href || a.getAttribute('href') || '';
      if (/ads-creation|order\?|product\/manage|finance|health/i.test(href)) continue;
      var id = extractCreatorId(href, a.innerText || '');
      if (!id || seen[id]) continue;
      if (!/creator|affiliate|author|@|达人|influencer/i.test(href + ' ' + (a.innerText || ''))) continue;
      seen[id] = true;
      out.push({
        creatorId: id,
        creatorName: cellText(a).slice(0, 160),
        href: href,
        source: 'link'
      });
    }
    return out;
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    var title = document.title || '';
    var windowLabel = null;
    var wm =
      body.match(/近\s*\d+\s*天/) ||
      body.match(/Last\s*\d+\s*days?/i) ||
      body.match(/\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\s*[\-~至]\s*\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}/) ||
      body.match(/Yesterday|昨天|Today|今天|本周|This\s*week/i);
    if (wm) windowLabel = wm[0];

    /* money: allow £ 164 .96 after normalize */
    var money = '([£$€¥￥]?\\s*[\\d,]+(?:\\s*\\.\\s*\\d+)?)';
    var kpis = {
      gmvAffiliate: findByRegex(body, [
        new RegExp('达人\\s*归因\\s*GMV\\s*' + money, 'i'),
        new RegExp('联盟\\s*归因\\s*GMV\\s*' + money, 'i'),
        new RegExp('归因\\s*GMV\\s*' + money, 'i'),
        new RegExp('Creator\\s*attributed\\s*GMV\\s*' + money, 'i'),
        new RegExp('Affiliate\\s*GMV\\s*' + money, 'i'),
        new RegExp('Attributed\\s*GMV\\s*' + money, 'i')
      ]),
      orderUnits: findByRegex(body, [
        /达人\s*归因\s*成交件数?\s*([\d,.]+[KkMm万亿]?)/i,
        /归因\s*成交件数?\s*([\d,.]+[KkMm万亿]?)/i,
        /Units?\s*sold\s*([\d,.]+[KkMm万亿]?)/i,
        /Items?\s*sold\s*([\d,.]+[KkMm万亿]?)/i
      ]),
      refundAmount: findByRegex(body, [
        new RegExp('退款金额\\s*' + money),
        new RegExp('Refund\\s*amount\\s*' + money, 'i')
      ]),
      videoCnt: findByRegex(body, [
        /视频数\s*([\d,.]+)/,
        /Videos?\s*([\d,.]+)/i
      ]),
      liveCnt: findByRegex(body, [
        /直播数\s*([\d,.]+)/,
        /Live\s*streams?\s*([\d,.]+)/i
      ]),
      creatorsPublished: findByRegex(body, [
        /已发布内容的达人数\s*([\d,.]+)/,
        /发布内容的达人\s*([\d,.]+)/,
        /Creators?\s*with\s*content\s*([\d,.]+)/i
      ]),
      creatorsSold: findByRegex(body, [
        /动销达人数\s*([\d,.]+)/,
        /动销达人\s*([\d,.]+)/,
        /Selling\s*creators?\s*([\d,.]+)/i,
        /Creators?\s*with\s*sales\s*([\d,.]+)/i
      ]),
      estCommission: findByRegex(body, [
        new RegExp('预计\\s*佣金\\s*' + money),
        new RegExp('预估\\s*佣金\\s*' + money),
        new RegExp('Estimat(?:ed)?\\s*commission\\s*' + money, 'i')
      ])
    };

    var tbl = scrapeCreatorTable();
    var linkCreators = scrapeCreatorLinks();
    var byKey = {};
    function addCr(c) {
      if (!c) return;
      var id = c.creatorId || c.creatorHandle || '';
      var key = id || 'n:' + String(c.creatorName || '').slice(0, 48);
      if (!byKey[key]) byKey[key] = c;
      else {
        var cur = byKey[key];
        Object.keys(c).forEach(function (kk) {
          if (cur[kk] == null || cur[kk] === '') cur[kk] = c[kk];
        });
      }
    }
    (tbl.creators || []).forEach(addCr);
    linkCreators.forEach(addCr);
    var allCreators = Object.keys(byKey).map(function (k) {
      return byKey[k];
    });
    var withId = allCreators.filter(function (c) {
      return !!c.creatorId;
    });

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
      hasAffiliateNav: /联盟|Affiliate|达人中心|Creator\s*marketplace|Partner\s*center/i.test(body),
      hasPerformanceWord: /表现|Performance|数据分析/i.test(body),
      hasGmvWord: /GMV|归因/i.test(body),
      hasCommissionWord: /佣金|commission/i.test(body),
      hasCreatorTableHint: /达人|Creator|Influencer/i.test(body),
      host: location.host || '',
      path: location.pathname || ''
    };

    var hasKpi = Object.keys(kpiFlat).some(function (k) {
      return kpiFlat[k] != null;
    });
    var hasRows = allCreators.length > 0;
    var ok = !!(hasKpi || hasRows);

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 700),
      window: windowLabel,
      kpiHits: kpiHits,
      tableHeaders: tbl.headers,
      tableFields: tbl.fields,
      creatorRowCount: allCreators.length,
      creatorIdCount: withId.length,
      linkCreatorCount: linkCreators.length,
      pageHints: pageHints
    };

    if (!ok) {
      return JSON.stringify({
        ok: false,
        module: 'affiliate_performance',
        source: 'affiliate-performance-poc',
        url: url,
        title: title,
        window: windowLabel,
        currency: detectCurrency(body),
        kpis: kpiFlat,
        creators: [],
        creatorIdCount: 0,
        raw: raw,
        error:
          'no affiliate KPI or creator rows. Confirm URL is 联盟中心→数据分析→表现. url=' + url
      });
    }

    return JSON.stringify({
      ok: true,
      module: 'affiliate_performance',
      source: 'affiliate-performance-poc',
      url: url,
      title: title,
      window: windowLabel,
      currency: detectCurrency(body) || 'GBP',
      kpis: kpiFlat,
      creators: allCreators.slice(0, 80),
      creatorIdCount: withId.length,
      raw: raw,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'affiliate_performance',
      source: 'affiliate-performance-poc',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
