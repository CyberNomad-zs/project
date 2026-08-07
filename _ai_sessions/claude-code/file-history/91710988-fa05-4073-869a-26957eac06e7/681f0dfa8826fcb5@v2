/* TikTok product ratings / 商品评分 list. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function parseStarsFromText(text) {
    var s = clean(text);
    var m = s.match(/(\d(?:\.\d)?)\s*星/) || s.match(/Rating\s*[:：]?\s*(\d(?:\.\d)?)/i);
    if (m) {
      var n = Number(m[1]);
      if (n >= 1 && n <= 5) return n;
    }
    return null;
  }
  function countStarNodes(root) {
    if (!root) return null;
    // filled stars often have active/selected/full class or yellow fill
    var icons = root.querySelectorAll(
      'svg,i,[class*="star"],[class*="Star"],[aria-label*="star"],[aria-label*="星"]'
    );
    if (!icons.length) return null;
    var filled = 0;
    var total = 0;
    for (var i = 0; i < icons.length && total < 5; i++) {
      var el = icons[i];
      var cls = (el.className && el.className.toString) ? el.className.toString() : String(el.className || '');
      var al = (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('aria-valuenow'))) || '';
      var html = '';
      try { html = el.outerHTML || ''; } catch (e) {}
      total++;
      if (
        /active|selected|filled|full|current|on\b/i.test(cls + ' ' + al) ||
        /fill\s*=\s*["']?#f|fill\s*=\s*["']?orange|fill\s*=\s*["']?gold|#ff|#f5/i.test(html)
      ) {
        filled++;
      }
    }
    // if we saw exactly 5 star-like nodes, filled count is rating
    if (total >= 5) return Math.min(5, Math.max(0, filled));
    if (filled > 0 && filled <= 5) return filled;
    return null;
  }
  function parseDate(text) {
    var s = clean(text);
    var m =
      s.match(/(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/) ||
      s.match(/(20\d{2})[\/\-.](\d{1,2})[\/\-.](\d{1,2})/) ||
      s.match(/(\d{1,2})[\/\-.](\d{1,2})[\/\-.](20\d{2})/);
    if (!m) return { raw: '', iso: null, bizDate: null };
    var y, mo, d;
    if (m[0].indexOf('年') >= 0 || m[1].length === 4) {
      y = +m[1]; mo = +m[2]; d = +m[3];
    } else {
      mo = +m[1]; d = +m[2]; y = +m[3];
    }
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    var bd = y + '-' + pad(mo) + '-' + pad(d);
    return { raw: m[0], iso: bd + 'T00:00:00', bizDate: bd };
  }
  function parseOrderId(text) {
    var s = clean(text);
    var m = s.match(/(?:订单\s*)?ID\s*[:：]\s*(\d{10,22})/i) || s.match(/\b(576\d{15,18})\b/);
    return m ? m[1] : '';
  }
  function parseProductId(text) {
    var s = clean(text);
    var m = s.match(/(?:商品\s*)?ID\s*[:：]\s*(\d{10,22})/i) || s.match(/\b(17\d{15,20})\b/);
    return m ? m[1] : '';
  }
  function simpleHash(s) {
    var h = 0;
    s = String(s || '');
    for (var i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return 'h' + Math.abs(h).toString(36);
  }
  function extractBuyer(text) {
    var s = clean(text);
    var m = s.match(/@([A-Za-z0-9_\*一-鿿.]{1,40})/) || s.match(/用户名\s*[:：]\s*(\S+)/);
    return m ? m[1] : '';
  }
  function isReviewBlob(t) {
    if (!t || t.length < 25 || t.length > 1500) return false;
    if (/(订单\s*ID|商品\s*ID|Order\s*ID|Product\s*ID)/i.test(t) && /(星|star|评价|review|回复)/i.test(t)) return true;
    if (/\d\s*星/.test(t) && /订单|商品/.test(t)) return true;
    return false;
  }
  function parseReviewNode(el) {
    var t = clean(el.textContent || '');
    if (!isReviewBlob(t)) return null;
    var orderId = parseOrderId(t);
    var productId = parseProductId(t);
    if (!orderId && !productId) return null;
    var rating = countStarNodes(el);
    if (rating == null) rating = parseStarsFromText(t);
    // fallback: count "★" like glyphs
    if (rating == null) {
      var stars = (t.match(/[★⭐]/g) || []).length;
      if (stars >= 1 && stars <= 5) rating = stars;
    }
    var dt = parseDate(t);
    var reply = '';
    var hasReply = false;
    var rm = t.match(/(?:你的回复|Your\s*reply|商家回复)\s*[:：]?\s*(.+?)(?=订单\s*ID|商品\s*ID|$)/i);
    if (rm && clean(rm[1]).length > 2) {
      reply = clean(rm[1]).slice(0, 500);
      hasReply = true;
    }
    if (/条回复|1\s*条回复|\d+\s*replies/i.test(t)) hasReply = true;
    // review text: strip meta
    var reviewText = t
      .replace(/(?:订单\s*)?ID\s*[:：]\s*\d+/gi, ' ')
      .replace(/(?:商品\s*)?ID\s*[:：]\s*\d+/gi, ' ')
      .replace(/@\S+/g, ' ')
      .replace(/\d+\s*条回复/g, ' ')
      .replace(/评价详情|Reply|回复/gi, ' ')
      .replace(/20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 400);
    var productName = '';
    var lines = t.split(/(?=\d{10,})|·/).map(clean);
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].length > 12 && lines[i].length < 120 && !/ID\s*[:：]/i.test(lines[i]) && /[A-Za-z一-鿿]/.test(lines[i])) {
        if (!/回复|评价|星/.test(lines[i])) productName = lines[i];
      }
    }
    var key = orderId && productId ? orderId + ':' + productId : orderId || productId || simpleHash(t.slice(0, 160));
    return {
      reviewKey: key,
      orderId: orderId || null,
      productId: productId || null,
      productName: productName || null,
      rating: rating,
      reviewText: reviewText,
      reviewAt: dt.iso,
      bizDate: dt.bizDate,
      buyerName: extractBuyer(t) || null,
      replyText: reply || null,
      hasReply: !!hasReply,
      rawText: t.slice(0, 500)
    };
  }
  function parseList() {
    var rows = [], seen = {};
    var nodes = Array.prototype.slice.call(
      document.querySelectorAll('tr,li,article,section,div[class*="rating"],div[class*="review"],div[class*="comment"]')
    );
    // also generic divs with order id
    if (nodes.length < 5) {
      nodes = Array.prototype.slice.call(document.querySelectorAll('div,li,tr'));
    }
    for (var i = 0; i < nodes.length; i++) {
      var r = parseReviewNode(nodes[i]);
      if (!r || !r.reviewKey || seen[r.reviewKey]) continue;
      seen[r.reviewKey] = true;
      rows.push(r);
      if (rows.length >= 80) break;
    }
    return rows;
  }
  try {
    var url = location.href || '';
    var title = document.title || '';
    var onReview =
      /rating|review|evaluation|评分|评价/i.test(url) ||
      /商品评分|Product\s*ratings?|Reviews?/i.test(title + ' ' + bodyText().slice(0, 200));
    var body = bodyText();
    var rows = parseList();
    // empty page still ok
    var emptyOk = rows.length === 0 && /暂无|没有评价|No\s+(review|rating|data)|0\s*个评分/i.test(body);
    var ok = rows.length > 0 || emptyOk;
    if (!onReview && rows.length === 0) {
      return JSON.stringify({
        ok: false,
        module: 'product_reviews',
        source: 'product-rating',
        url: url,
        title: title,
        rows: [],
        rowCount: 0,
        error: 'wrong_page_not_reviews: ' + url,
        diag: { bodyLen: body.length, sample: body.slice(0, 200) }
      });
    }
    return JSON.stringify({
      ok: ok,
      module: 'product_reviews',
      source: 'product-rating',
      url: url,
      title: title,
      rows: rows,
      rowCount: rows.length,
      emptyOk: emptyOk,
      diag: { bodyLen: body.length, sample: body.slice(0, 220) },
      error: ok ? null : 'no review rows. url=' + url
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'product_reviews',
      url: location.href || '',
      rows: [],
      error: String(e && e.message ? e.message : e)
    });
  }
})();
