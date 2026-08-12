/* TikTok account health · 违规记录 tab. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    var st = window.getComputedStyle(el);
    return st && st.visibility !== 'hidden' && st.display !== 'none';
  }
  function clickTab() {
    var nodes = document.querySelectorAll('a,button,div,span,[role="tab"]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!visible(el)) continue;
      var t = clean(el.textContent || el.getAttribute('aria-label') || '');
      if (!t || t.length > 20) continue;
      if (/^违规记录$|^Violations?$|^Violation\s*records?$/i.test(t)) {
        try { el.click(); return t; } catch (e) {}
      }
    }
    return '';
  }
  function parseScore(text) {
    var s = clean(text);
    var m =
      s.match(/AHR\s*违规分\s*[:：]?\s*(\d+(?:\.\d+)?)/i) ||
      s.match(/违规分\s*[:：]?\s*(\d+(?:\.\d+)?)/) ||
      s.match(/(\d+(?:\.\d+)?)\s*分/);
    return m ? Number(m[1]) : null;
  }
  function parseProductId(text) {
    var s = clean(text);
    var m = s.match(/(?:商品\s*)?ID\s*[:：]\s*(\d{10,22})/i) || s.match(/\b(17\d{15,20})\b/);
    return m ? m[1] : '';
  }
  function parseOrderId(text) {
    var s = clean(text);
    var m = s.match(/(?:订单|Order)\s*ID\s*[:：]?\s*(\d{10,22})/i) || s.match(/\b(576\d{15,18})\b/);
    return m ? m[1] : '';
  }
  function parseDate(text) {
    var s = clean(text);
    var m =
      s.match(/(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?/i) ||
      s.match(/(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?/i);
    if (!m) return { raw: s.slice(0, 40), iso: null };
    var y, mo, d, hh = 0, mm = 0, ss = 0;
    if (m[1].length === 4) {
      y = +m[1]; mo = +m[2]; d = +m[3];
      if (m[4]) hh = +m[4]; if (m[5]) mm = +m[5]; if (m[6]) ss = +m[6];
    } else {
      mo = +m[1]; d = +m[2]; y = +m[3];
      if (m[4]) hh = +m[4]; if (m[5]) mm = +m[5]; if (m[6]) ss = +m[6];
    }
    var ap = (m[7] || '').toUpperCase();
    if (ap === 'PM' && hh < 12) hh += 12;
    if (ap === 'AM' && hh === 12) hh = 0;
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    var iso = y + '-' + pad(mo) + '-' + pad(d) + 'T' + pad(hh) + ':' + pad(mm) + ':' + pad(ss);
    return { raw: m[0], iso: iso, bizDate: y + '-' + pad(mo) + '-' + pad(d) };
  }
  function simpleHash(s) {
    var h = 0;
    s = String(s || '');
    for (var i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return 'h' + Math.abs(h).toString(36);
  }
  function rowFromCells(cells) {
    var vals = cells.map(function (c) { return clean(c.textContent); }).filter(function (x) { return x; });
    if (vals.length < 2) return null;
    var blob = vals.join(' | ');
    if (/处罚|违规原因|日期|状态|Penalty|Reason|Status/i.test(blob) && vals.length <= 5 && !/\d{4}|\d{2}\/\d{2}/.test(blob)) {
      return null; // header
    }
    var penalty = vals[0] || '';
    var reason = vals[1] || '';
    var dateCell = vals[2] || '';
    var status = vals[3] || '';
    // 若列序不同，用关键词兜底
    for (var i = 0; i < vals.length; i++) {
      if (/申诉|强制|处理|失败|成功|Pending|Appeal|Closed/i.test(vals[i]) && vals[i].length < 40) status = vals[i];
      if (/\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}/.test(vals[i])) dateCell = vals[i];
    }
    if (!penalty && !reason) return null;
    if (/没有|暂无|No\s+data|No\s+records/i.test(blob) && blob.length < 40) return null;
    var dt = parseDate(dateCell || blob);
    var productId = parseProductId(blob);
    var orderId = parseOrderId(blob);
    var score = parseScore(penalty + ' ' + blob);
    var platformId = '';
    var idm = blob.match(/(?:罚单|记录|Violation)\s*ID\s*[:：]?\s*([A-Za-z0-9_-]{6,})/i);
    if (idm) platformId = idm[1];
    if (!platformId && productId && dt.bizDate) platformId = productId + ':' + dt.bizDate + ':' + simpleHash(penalty + reason);
    if (!platformId) platformId = simpleHash([penalty, reason, dateCell, status, productId].join('|'));
    return {
      violationKey: platformId,
      penaltyText: penalty.slice(0, 300),
      penaltyScore: score,
      reason: reason.slice(0, 300),
      status: status.slice(0, 80),
      violationAt: dt.iso,
      bizDate: dt.bizDate,
      productId: productId || null,
      orderId: orderId || null,
      rawCells: vals.slice(0, 8),
      rawText: blob.slice(0, 400)
    };
  }
  function parseTables() {
    var rows = [], seen = {};
    var trs = Array.prototype.slice.call(document.querySelectorAll('table tr, [role="row"]'));
    for (var i = 0; i < trs.length; i++) {
      var cells = Array.prototype.slice.call(trs[i].querySelectorAll('td,th,[role="cell"],[role="gridcell"]'));
      if (cells.length < 2) continue;
      var r = rowFromCells(cells);
      if (!r || !r.violationKey || seen[r.violationKey]) continue;
      // skip pure header
      if (/^处罚$|^违规原因$|^日期$|^状态$/i.test(r.penaltyText)) continue;
      seen[r.violationKey] = true;
      rows.push(r);
    }
    return rows;
  }
  function parseCards() {
    var rows = [], seen = {};
    var nodes = Array.prototype.slice.call(document.querySelectorAll('div,li,section,article'));
    for (var i = 0; i < nodes.length; i++) {
      var t = clean(nodes[i].textContent || '');
      if (t.length < 20 || t.length > 800) continue;
      if (!/(违规|处罚|AHR|冻结|禁售|Violation|Penalty)/i.test(t)) continue;
      if (!/\d{1,2}[\/\-.]\d{1,2}|\d{4}[\/\-.]\d{1,2}/.test(t)) continue;
      var dt = parseDate(t);
      var penalty = '';
      var pm = t.match(/((?:商品|账号|店铺)?[^|]{0,40}(?:冻结|禁售|扣分|处罚)[^|]{0,40})/);
      if (pm) penalty = clean(pm[1]).slice(0, 200);
      if (!penalty) penalty = t.slice(0, 120);
      var reason = '';
      var rm = t.match(/(?:违规原因|原因|Reason)\s*[:：]?\s*([^\n]{4,120})/i);
      if (rm) reason = clean(rm[1]);
      var status = '';
      var sm = t.match(/(申诉失败|申诉成功|已强制处罚|处理中|未读|Appeal\s*failed|Closed)/i);
      if (sm) status = sm[1];
      var productId = parseProductId(t);
      var key = productId && dt.bizDate ? productId + ':' + dt.bizDate + ':' + simpleHash(penalty) : simpleHash(t.slice(0, 180));
      if (seen[key]) continue;
      seen[key] = true;
      rows.push({
        violationKey: key,
        penaltyText: penalty,
        penaltyScore: parseScore(t),
        reason: reason,
        status: status,
        violationAt: dt.iso,
        bizDate: dt.bizDate,
        productId: productId || null,
        orderId: parseOrderId(t) || null,
        rawText: t.slice(0, 400)
      });
      if (rows.length >= 50) break;
    }
    return rows;
  }
  try {
    var url = location.href || '';
    var title = document.title || '';
    var tab = '';
    // 尽量切到违规记录
    if (!/violation|违规/i.test(url + bodyText().slice(0, 500))) {
      tab = clickTab();
      var until = Date.now() + 900;
      while (Date.now() < until) {}
    } else {
      tab = clickTab() || 'already';
      until = Date.now() + 400;
      while (Date.now() < until) {}
    }
    var body = bodyText();
    var rows = parseTables();
    if (!rows.length) rows = parseCards();
    var ok = rows.length > 0 || /暂无|没有违规|No\s+(violation|record|data)/i.test(body);
    return JSON.stringify({
      ok: ok,
      module: 'violation_records',
      source: 'health-violation',
      url: url,
      title: title,
      tab: tab,
      rows: rows,
      rowCount: rows.length,
      emptyOk: rows.length === 0 && /暂无|没有违规|No\s+(violation|record|data)/i.test(body),
      diag: { bodyLen: body.length, sample: body.slice(0, 220) },
      error: ok ? null : 'no violation rows. url=' + url
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'violation_records',
      url: location.href || '',
      rows: [],
      error: String(e && e.message ? e.message : e)
    });
  }
})();
