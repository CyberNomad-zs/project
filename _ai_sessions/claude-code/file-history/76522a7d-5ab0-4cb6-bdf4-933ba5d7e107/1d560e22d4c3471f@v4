/* TikTok seller center: 内容分析 → 视频和照片概览 (P2.0 POC).
 * Ziniao page exec one-liner. Prefer body text + table headers; dump sample for tuning.
 * No // line comments that break minifier strip (block comment only at top).
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
  function matchVideoHeader(h) {
    var t = clean(h).toLowerCase();
    if (!t) return null;
    if (/视频|video|内容|content|作品|title|名称|name/.test(t) && !/gmv|订单|曝光|播放|点击/.test(t)) return 'title';
    if (/归因\s*gmv|视频\s*归因\s*gmv|attributed\s*gmv|video\s*gmv|\bgmv\b/.test(t)) return 'attributedGmv';
    if (/sku\s*订单|归因.*订单|attributed.*order|orders?/.test(t)) return 'attributedSkuOrders';
    if (/曝光|impression|show|展示/.test(t)) return 'impressions';
    if (/播放|play\s*count|views?/.test(t)) return 'playCount';
    if (/点击|clicks?/.test(t) && !/率|rate|ctr/.test(t)) return 'clicks';
    if (/\bctr\b|点击率|click\s*rate/.test(t)) return 'ctr';
    if (/转化|cvr|conversion/.test(t)) return 'cvr';
    if (/客户|buyer|customer/.test(t)) return 'customers';
    if (/id\b|视频\s*id|video\s*id|content\s*id/.test(t)) return 'contentId';
    return null;
  }
  function extractIdFromHref(href) {
    var s = String(href || '');
    var m =
      s.match(/[?&](?:video_id|videoId|item_id|itemId|content_id|contentId|id)=(\d{6,})/i) ||
      s.match(/\/(?:video|item|content|detail)\/(\d{6,})/i) ||
      s.match(/\/(\d{15,})(?:\?|$)/);
    return m ? m[1] : null;
  }
  function scrapeTableVideos() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('table'));
    var best = [];
    var bestHeaders = [];
    for (var ti = 0; ti < tables.length; ti++) {
      var table = tables[ti];
      var ths = table.querySelectorAll('thead th, tr th');
      if (!ths.length) continue;
      var fields = [];
      var headers = [];
      for (var hi = 0; hi < ths.length; hi++) {
        var ht = cellText(ths[hi]);
        headers.push(ht);
        fields.push(matchVideoHeader(ht));
      }
      var mapped = fields.filter(Boolean).length;
      if (mapped < 2) continue;
      var rows = table.querySelectorAll('tbody tr');
      var items = [];
      for (var ri = 0; ri < rows.length && items.length < 50; ri++) {
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
            var idA = extractIdFromHref(row.href);
            if (idA) row.contentId = row.contentId || idA;
          }
          if (!f) continue;
          if (f === 'title' || f === 'contentId') {
            row[f] = txt;
            if (!row.contentId) {
              var hm =
                String(row.href || '').match(/(?:video|item|content)[_/]?id[=/](\d+)/i) ||
                String(row.href || '').match(/\/video\/(\d+)/) ||
                String(txt).match(/\bID[:：]?\s*(\d{10,})\b/i) ||
                String(txt).match(/\b(\d{15,})\b/);
              if (hm) row.contentId = hm[1];
            }
          } else {
            row[f] = parseNumber(txt);
          }
        }
        if (row.title || row.contentId || row.attributedGmv != null || row.impressions != null) {
          items.push(row);
        }
      }
      if (items.length > best.length) {
        best = items;
        bestHeaders = headers;
      }
    }
    return { videos: best, headers: bestHeaders };
  }
  function scrapeNonTableVideoLinks() {
    var out = [];
    var seen = {};
    var anchors = document.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length && out.length < 40; i++) {
      var a = anchors[i];
      var href = a.href || a.getAttribute('href') || '';
      if (/product-card|product\/manage|order\?/i.test(href)) continue;
      var id = extractIdFromHref(href);
      if (!id || seen[id]) continue;
      if (!/video|item|content|analytics/i.test(href) && !/视频|video/i.test(a.innerText || '')) continue;
      seen[id] = true;
      out.push({
        contentId: id,
        title: cellText(a).slice(0, 160),
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
      body.match(/Yesterday|昨天|Today|今天/i);
    if (wm) windowLabel = wm[0];

    var kpis = {
      attributedGmv: findByRegex(body, [
        /视频\s*归因\s*GMV\s*([£$€]?[\d,]+\.?\d*)/i,
        /归因\s*GMV\s*([£$€]?[\d,]+\.?\d*)/i,
        /Video\s*attributed\s*GMV\s*([£$€]?[\d,]+\.?\d*)/i,
        /Attributed\s*GMV\s*([£$€]?[\d,]+\.?\d*)/i
      ]),
      attributedSkuOrders: findByRegex(body, [
        /视频\s*归因\s*SKU\s*订单数?\s*([\d,]+)/i,
        /归因\s*SKU\s*订单数?\s*([\d,]+)/i,
        /视频\s*归因\s*订单\s*([\d,]+)/i,
        /Attributed\s*SKU\s*orders?\s*([\d,]+)/i
      ]),
      customers: findByRegex(body, [
        /日均\s*客户数\s*([\d,]+)/,
        /客户数\s*([\d,]+)/,
        /Customers?\s*([\d,]+)/i
      ]),
      impressions: findByRegex(body, [
        /商品\s*曝光数?\s*([\d,.]+[KkMm万亿]?)/,
        /曝光用户数\s*([\d,.]+[KkMm万亿]?)/,
        /曝光数?\s*([\d,.]+[KkMm万亿]?)/,
        /Impressions?\s*([\d,.]+[KkMm万亿]?)/i
      ]),
      playCount: findByRegex(body, [
        /视频\s*播放量\s*([\d,.]+[KkMm万亿]?)/,
        /播放量\s*([\d,.]+[KkMm万亿]?)/,
        /播放\s*([\d,.]+[KkMm万亿]?)/,
        /Play\s*count\s*([\d,.]+[KkMm万亿]?)/i,
        /Views?\s*([\d,.]+[KkMm万亿]?)/i
      ])
    };

    var tbl = scrapeTableVideos();
    var linkVideos = scrapeNonTableVideoLinks();
    var videoById = {};
    function addVid(v) {
      if (!v) return;
      var id = v.contentId || '';
      var key = id || 't:' + String(v.title || '').slice(0, 48);
      if (!videoById[key]) videoById[key] = v;
      else {
        var cur = videoById[key];
        Object.keys(v).forEach(function (kk) {
          if (cur[kk] == null || cur[kk] === '') cur[kk] = v[kk];
        });
      }
    }
    (tbl.videos || []).forEach(addVid);
    linkVideos.forEach(addVid);
    var allVideos = Object.keys(videoById).map(function (k) {
      return videoById[k];
    });
    var withContentId = allVideos.filter(function (v) {
      return !!v.contentId;
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
      hasContentNav: /内容分析|Content\s*analytics|视频和照片|Videos?\s*and\s*photos/i.test(body),
      hasVideoWord: /视频|Video|短视频|Short\s*video/i.test(body),
      hasGmvWord: /GMV|归因/i.test(body),
      hasVideoDetailCta: /查看视频详情|视频详情/i.test(body),
      landedTopSelling: /video-top-selling/i.test(url)
    };

    var hasKpi = Object.keys(kpiFlat).some(function (k) {
      return kpiFlat[k] != null;
    });
    var hasRows = allVideos.length > 0;
    var ok = !!(hasKpi || hasRows);

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 500),
      window: windowLabel,
      kpiHits: kpiHits,
      tableHeaders: tbl.headers,
      videoRowCount: allVideos.length,
      contentIdCount: withContentId.length,
      linkVideoCount: linkVideos.length,
      pageHints: pageHints
    };

    if (!ok) {
      return JSON.stringify({
        ok: false,
        module: 'content_overview',
        source: 'content-overview-poc',
        url: url,
        title: title,
        window: windowLabel,
        currency: detectCurrency(body),
        kpis: kpiFlat,
        videos: [],
        contentIdCount: 0,
        raw: raw,
        error:
          'no content KPI or video rows. Confirm URL is 内容分析→视频和照片概览. url=' + url
      });
    }

    return JSON.stringify({
      ok: true,
      module: 'content_overview',
      source: 'content-overview-poc',
      url: url,
      title: title,
      window: windowLabel,
      currency: detectCurrency(body) || 'GBP',
      kpis: kpiFlat,
      videos: allVideos,
      contentIdCount: withContentId.length,
      raw: raw,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'content_overview',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
