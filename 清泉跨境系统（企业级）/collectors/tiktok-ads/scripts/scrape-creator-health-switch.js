/* Switch TikTok creator health account by display name, then scrape score + violations.
 * Placeholder __CREATOR_TARGET__ is replaced by PowerShell before page exec.
 */
(function () {
  var TARGET = String('__CREATOR_TARGET__' || '').trim();
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function visible(el) {
    if (!el || el.nodeType !== 1) return false;
    var st = window.getComputedStyle(el);
    if (!st || st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  }
  function parseScore(body) {
    var m =
      body.match(/(?:健康|Health)[^0-9]{0,40}?(\d{2,4})\b/) ||
      body.match(/\b(200|1\d{2}|[5-9]\d)\b\s*(?:\/\s*1000)?/) ||
      body.match(/\b(\d{2,4})\s*(?:起评分|默认)/);
    if (!m) return null;
    var n = Number(m[1]);
    if (!isFinite(n) || n < 0 || n > 1000) return null;
    return n;
  }
  function openSwitcher() {
    var nodes = document.querySelectorAll('button, div, span, a');
    for (var i = 0; i < nodes.length && i < 4000; i++) {
      var el = nodes[i];
      if (!visible(el)) continue;
      var t = clean(el.innerText || el.textContent || '');
      if (t === '切换账号' || t.indexOf('切换账号') === 0 || /Switch\s*account/i.test(t)) {
        try {
          el.click();
          return true;
        } catch (e) {}
      }
    }
    return false;
  }
  function clickAccount(name) {
    var want = clean(name);
    if (!want) return false;
    var nodes = document.querySelectorAll('button, div, span, label, li, [role="radio"], [role="option"]');
    var best = null;
    for (var i = 0; i < nodes.length && i < 8000; i++) {
      var el = nodes[i];
      if (!visible(el)) continue;
      var t = clean(el.innerText || el.textContent || '');
      if (!t || t.length > 100) continue;
      // exact or starts with name line
      var first = t.split(/\s+/)[0] || t;
      if (first === want || t.indexOf(want) === 0 || t.indexOf(want + ' ') >= 0) {
        // prefer compact cards with 违规次数 / 账号
        var score = 0;
        if (/违规次数|官方账号|营销账号|Official|Marketing/i.test(t)) score += 2;
        if (first === want) score += 3;
        if (t.length < 60) score += 1;
        if (!best || score > best.score) best = { el: el, score: score, text: t };
      }
    }
    if (!best) return false;
    try {
      best.el.click();
      return true;
    } catch (e) {
      try {
        var p = best.el.closest('button, [role="radio"], label, div');
        if (p) {
          p.click();
          return true;
        }
      } catch (e2) {}
    }
    return false;
  }
  function scrapeViolations() {
    var out = [];
    var rows = document.querySelectorAll('tr, [class*="table"] [class*="row"], [class*="list"] > div');
    for (var r = 0; r < rows.length && out.length < 40; r++) {
      var rt = clean(rows[r].innerText || '');
      if (!rt || rt.length < 12) continue;
      if (/违规类型|日期和时间|操作|近\s*90\s*天/.test(rt) && rt.length < 50) continue;
      if (/视频违规|政策违规|一般违规|降低|曝光|申诉|enforcement/i.test(rt)) {
        out.push({
          type: /视频违规|video/i.test(rt) ? '视频违规' : '违规',
          text: rt.slice(0, 300)
        });
      }
    }
    return out;
  }
  try {
    if (!TARGET) {
      return JSON.stringify({ ok: false, error: 'empty TARGET' });
    }
    var opened = openSwitcher();
    // wait ~400ms
    var until = Date.now() + 450;
    while (Date.now() < until) {}
    var clicked = clickAccount(TARGET);
    if (!clicked) {
      // try open again (panel closed)
      openSwitcher();
      until = Date.now() + 400;
      while (Date.now() < until) {}
      clicked = clickAccount(TARGET);
    }
    // wait SPA
    until = Date.now() + 1800;
    while (Date.now() < until) {}

    var body = bodyText();
    var healthScore = parseScore(body);
    var statusLabel = null;
    var st = body.match(/需要关注|账号信誉良好|你的账号信誉良好|健康\s*>|At\s*risk|Good/i);
    if (st) statusLabel = clean(st[0]).slice(0, 40);
    var violations = scrapeViolations();
    var vCount = null;
    var vm = body.match(new RegExp(TARGET.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\s\\S]{0,40}?违规次数\\s*[:：]?\\s*(\\d+)'));
    if (vm) vCount = Number(vm[1]);

    var ok = healthScore != null || violations.length > 0 || clicked;
    return JSON.stringify({
      ok: ok,
      switched: clicked,
      switcherOpened: opened,
      creatorName: TARGET,
      creator_key: TARGET,
      healthScore: healthScore,
      statusLabel: statusLabel,
      violationCount: vCount,
      violations: violations,
      url: location.href || '',
      raw: { bodyLen: body.length, sample: body.slice(0, 220) },
      error: ok ? null : 'switch/scrape failed for ' + TARGET
    });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String((e && e.message) || e), creatorName: TARGET });
  }
})();
