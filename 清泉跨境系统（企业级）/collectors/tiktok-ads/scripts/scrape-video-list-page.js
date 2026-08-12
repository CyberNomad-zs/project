/* TikTok seller center: 内容分析 → 视频 → 视频详情 / 列表 (P2.1b).
 * content_id = video-detail-item?id=… → ingest source tiktok_content → fact_tiktok_content_daily.
 * Ziniao page exec. Block comments only.
 */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
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
    return null;
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function extractVideoIdFromHref(href) {
    var s = String(href || '');
    /* Prefer real video detail paths (Deal 2026-08-05: video-detail-item?id=7667…) */
    var m =
      s.match(/video-detail-item[^#]*[?&]id=(\d{6,})/i) ||
      s.match(/[?&](?:video_id|videoId|item_id|itemId|content_id|contentId)=(\d{6,})/i) ||
      s.match(/\/(?:video|item|content)\/(\d{10,})(?:\?|$|\/)/i);
    return m ? m[1] : null;
  }
  function extractAnyIdFromHref(href) {
    var s = String(href || '');
    var prefer = extractVideoIdFromHref(s);
    if (prefer) return prefer;
    var m =
      s.match(/[?&](?:id)=(\d{10,})/i) ||
      s.match(/\/(\d{15,})(?:\?|$)/);
    return m ? m[1] : null;
  }
  function pickBestHref(cell) {
    var anchors = cell.querySelectorAll ? cell.querySelectorAll('a[href]') : [];
    var best = null;
    var bestScore = -1;
    for (var i = 0; i < anchors.length; i++) {
      var href = anchors[i].href || anchors[i].getAttribute('href') || '';
      if (!href || /javascript:|lf16-scmcdn/i.test(href)) continue;
      var score = 0;
      if (/video-detail-item/i.test(href)) score += 100;
      if (/video-analytics/i.test(href)) score += 40;
      if (extractVideoIdFromHref(href)) score += 50;
      if (/product-card|product\/manage|order\?/i.test(href)) score -= 80;
      if (score > bestScore) {
        bestScore = score;
        best = href;
      }
    }
    return best;
  }
  function matchVideoHeader(h) {
    var t = clean(h).toLowerCase();
    if (!t) return null;
    if (/视频\s*id|video\s*id|content\s*id/.test(t) && !/商品|product/.test(t)) return 'contentId';
    if (/^vv$|\bvv\b|播放|play\s*count|views?|观看/.test(t) && !/转化|成交|点击率/.test(t)) return 'playCount';
    if (/视频信息|视频|video|内容|content|作品|title|名称|name/.test(t) && !/gmv|订单|曝光|播放|点击|转化|商品|vv/.test(t))
      return 'title';
    if (/绑定.*归因\s*gmv|归因\s*gmv|视频\s*归因\s*gmv|attributed\s*gmv|video\s*gmv|\bgmv\b/.test(t))
      return 'attributedGmv';
    if (/sku\s*订单|归因.*订单|attributed.*order|orders?/.test(t)) return 'attributedSkuOrders';
    if (/归因成交|成交件数|units?|quantity/.test(t)) return 'attributedUnits';
    if (/商品曝光|曝光|impression|show|展示/.test(t)) return 'impressions';
    if (/商品点击|点击|clicks?/.test(t) && !/率|rate|ctr|转化/.test(t)) return 'clicks';
    if (/\bctr\b|点击率/.test(t)) return 'ctr';
    if (/转化|cvr|conversion/.test(t)) return 'cvr';
    if (/客户|buyer|customer/.test(t)) return 'customers';
    if (/发布时间|publish|posted/.test(t)) return 'publishedAt';
    if (/^商品$|product/.test(t) && !/曝光|点击|gmv/.test(t)) return 'productRef';
    return null;
  }
  function scrapeTables() {
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
        var ht = clean(ths[hi].innerText || ths[hi].textContent);
        headers.push(ht);
        fields.push(matchVideoHeader(ht));
      }
      if (fields.filter(Boolean).length < 1) continue;
      var rows = table.querySelectorAll('tbody tr');
      var items = [];
      for (var ri = 0; ri < rows.length && items.length < 80; ri++) {
        var tds = rows[ri].querySelectorAll('td');
        if (!tds.length) continue;
        var row = { rawCells: [], source: 'table' };
        /* Scan whole row for best video href first (last col 查看数据分析 often wins) */
        var rowBestHref = null;
        var rowBestScore = -1;
        for (var ai = 0; ai < tds.length; ai++) {
          var href0 = pickBestHref(tds[ai]);
          if (!href0) continue;
          var sc = /video-detail-item/i.test(href0) ? 100 : extractVideoIdFromHref(href0) ? 50 : 10;
          if (sc > rowBestScore) {
            rowBestScore = sc;
            rowBestHref = href0;
          }
        }
        if (rowBestHref) {
          row.href = rowBestHref;
          var vid = extractVideoIdFromHref(rowBestHref) || extractAnyIdFromHref(rowBestHref);
          if (vid) row.contentId = vid;
        }
        for (var ci = 0; ci < tds.length; ci++) {
          var txt = clean(tds[ci].innerText || tds[ci].textContent);
          row.rawCells.push(txt);
          var f = fields[ci];
          if (!f) continue;
          if (f === 'title' || f === 'contentId' || f === 'productRef' || f === 'publishedAt') {
            if (f === 'title') row.title = txt;
            else if (f === 'productRef') row.productRef = txt;
            else if (f === 'publishedAt') row.publishedAt = txt;
            else if (f === 'contentId' && !row.contentId) {
              var idOnly = String(txt).match(/\b(\d{10,})\b/);
              if (idOnly) row.contentId = idOnly[1];
            }
            /* Never steal random long digits from title when href already gave video id */
          } else {
            row[f] = parseNumber(txt);
          }
        }
        if (row.contentId || row.title || row.attributedGmv != null || row.playCount != null) {
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
  function scrapeLinkCandidates() {
    var out = [];
    var seen = {};
    var anchors = document.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length && out.length < 60; i++) {
      var a = anchors[i];
      var href = a.href || a.getAttribute('href') || '';
      /* only real video detail links — avoid product/shop noise ids */
      var id = extractVideoIdFromHref(href);
      if (!id || seen[id]) continue;
      if (/product-card|product\/manage|order\?/i.test(href)) continue;
      seen[id] = true;
      out.push({
        contentId: id,
        title: clean(a.innerText || a.textContent).slice(0, 160),
        href: href,
        source: 'link'
      });
    }
    return out;
  }
  function scrapeDivListHints() {
    /* virtualized lists often not <table> */
    var nodes = document.querySelectorAll('[class*="row"], [class*="list"], [class*="item"], tr');
    var hits = [];
    var seen = {};
    for (var i = 0; i < nodes.length && hits.length < 40; i++) {
      var el = nodes[i];
      var txt = clean(el.innerText || el.textContent);
      if (!txt || txt.length < 8 || txt.length > 800) continue;
      var href = pickBestHref(el) || '';
      var id = extractVideoIdFromHref(href);
      if (!id || seen[id]) continue;
      if (!/视频|video|播放|gmv|曝光|转化|vv/i.test(txt) && !/video-detail/i.test(href)) continue;
      seen[id] = true;
      hits.push({
        contentId: id,
        title: txt.slice(0, 160),
        href: href || null,
        source: 'div_list'
      });
    }
    return hits;
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    var title = document.title || '';
    var windowLabel = null;
    var wm =
      body.match(/最近\s*\d+\s*天/) ||
      body.match(/近\s*\d+\s*天/) ||
      body.match(/Last\s*\d+\s*days?/i) ||
      body.match(/Yesterday|昨天|Today|今天/i);
    if (wm) windowLabel = wm[0];

    var tbl = scrapeTables();
    var links = scrapeLinkCandidates();
    var divs = scrapeDivListHints();
    var byId = {};
    function merge(arr) {
      for (var i = 0; i < arr.length; i++) {
        var r = arr[i];
        var id = r.contentId || r.content_id;
        if (!id) {
          /* keep title-only table rows under synthetic key */
          var k = 't:' + String(r.title || '').slice(0, 40);
          if (!byId[k]) byId[k] = r;
          continue;
        }
        if (!byId[id]) byId[id] = r;
        else {
          var cur = byId[id];
          Object.keys(r).forEach(function (k) {
            if (cur[k] == null || cur[k] === '') cur[k] = r[k];
          });
        }
      }
    }
    merge(tbl.videos);
    merge(links);
    merge(divs);
    var videos = Object.keys(byId).map(function (k) {
      return byId[k];
    });
    var withId = videos.filter(function (v) {
      return !!(v.contentId || v.content_id);
    });

    var pageHints = {
      hasVideoDetailWord: /视频详情|Video\s*detail|视频列表|Video\s*list/i.test(body),
      hasRankingWord: /视频排行|排行榜|top\s*video/i.test(body),
      hasPerformanceWord: /表现|Performance/i.test(body),
      landedTopSelling: /video-top-selling|热卖|top\s*selling/i.test(url + ' ' + body.slice(0, 200)),
      landedOverview: /video-analytics(?!\/)/i.test(url) && /关键指标|视频归因\s*GMV/i.test(body)
    };

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 800),
      window: windowLabel,
      tableHeaders: tbl.headers,
      tableRowCount: tbl.videos.length,
      linkCandidateCount: links.length,
      divCandidateCount: divs.length,
      videoRowCount: videos.length,
      withContentIdCount: withId.length,
      pageHints: pageHints
    };

    var ok = videos.length > 0 || pageHints.hasVideoDetailWord || pageHints.landedOverview;
    return JSON.stringify({
      ok: ok,
      module: 'video_list',
      source: 'video-list-poc',
      url: url,
      title: title,
      window: windowLabel,
      videos: videos,
      contentIdCount: withId.length,
      raw: raw,
      error: ok
        ? null
        : 'no video list/detail signals. url=' + url
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'video_list',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
