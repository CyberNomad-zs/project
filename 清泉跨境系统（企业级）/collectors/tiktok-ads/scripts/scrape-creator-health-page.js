/* TikTok creator health: list switcher accounts + current score/violations.
 * Multi-account full scores: run-shop-modules loops scrape-creator-health-switch.js
 */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function visible(el) {
    if (!el || el.nodeType !== 1) return false;
    var st = window.getComputedStyle(el);
    if (!st || st.display === 'none' || st.visibility === 'hidden') return false;
    var r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  }
  function parseScore(body) {
    var m =
      body.match(/(?:健康|Health)[^0-9]{0,40}?(\d{2,4})\b/) ||
      body.match(/\b(200|1\d{2}|[5-9]\d)\b/);
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
  function collectAccounts() {
    var accounts = [];
    var seen = {};
    function pushAcc(name, role, vc) {
      name = clean(name);
      if (!name || name.length < 2 || name.length > 40) return;
      if (/切换账号|ScoreHub|违规次数|官方账号|营销账号|了解更多|需要关注/.test(name)) return;
      var k = name.toLowerCase();
      if (seen[k]) return;
      seen[k] = 1;
      accounts.push({
        name: name,
        violationCount: vc == null || !isFinite(Number(vc)) ? null : Number(vc),
        role: role || ''
      });
    }
    var nodes = document.querySelectorAll('button, div, span, label, li, [role="radio"], [role="option"]');
    for (var i = 0; i < nodes.length && accounts.length < 40; i++) {
      var el = nodes[i];
      if (!visible(el)) continue;
      var t = clean(el.innerText || el.textContent || '');
      if (!t || t.length > 90) continue;
      if (!/违规次数|官方账号|营销账号|Official|Marketing/i.test(t)) continue;
      var vM = t.match(/违规次数\s*[:：]?\s*(\d+)/);
      var role = /官方|Official/i.test(t) ? 'official' : /营销|Marketing/i.test(t) ? 'marketing' : '';
      var nameLine = t
        .replace(/官方账号|营销账号|Official|Marketing|账号/gi, ' ')
        .replace(/违规次数\s*[:：]?\s*\d+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
      var name = (nameLine.split(/\s+/)[0] || '').trim();
      if (name) pushAcc(name, role, vM ? vM[1] : null);
    }
    if (!accounts.length) {
      var body = bodyText();
      var re = /([A-Za-z0-9_\u4e00-\u9fff.\-]{2,30})\s*(官方账号|营销账号)?\s*违规次数\s*[:：]?\s*(\d+)/g;
      var mm;
      while ((mm = re.exec(body)) && accounts.length < 40) {
        pushAcc(mm[1], mm[2] || '', mm[3]);
      }
    }
    return accounts;
  }
  try {
    var url = location.href || '';
    var opened = openSwitcher();
    var until = Date.now() + 500;
    while (Date.now() < until) {}
    var accounts = collectAccounts();
    var body = bodyText();
    var healthScore = parseScore(body);
    var statusLabel = null;
    var st = body.match(/需要关注|账号信誉良好|你的账号信誉良好|健康/);
    if (st) statusLabel = clean(st[0]).slice(0, 40);

    var violations = [];
    var rows = document.querySelectorAll('tr, [class*="table"] [class*="row"]');
    for (var r = 0; r < rows.length && violations.length < 50; r++) {
      var rt = clean(rows[r].innerText || '');
      if (!rt || rt.length < 10) continue;
      if (/违规类型|日期和时间|操作/.test(rt) && rt.length < 40) continue;
      if (/视频违规|政策违规|一般违规|降低|曝光|申诉/.test(rt)) {
        violations.push({
          type: /视频违规/.test(rt) ? '视频违规' : '违规',
          text: rt.slice(0, 300)
        });
      }
    }

    var selectedName = '';
    var sel = document.querySelector('[class*="selected"], [aria-checked="true"]');
    if (sel) selectedName = clean(sel.innerText || '').split(/\s+/)[0] || '';
    if (!selectedName && accounts.length === 1) selectedName = accounts[0].name;

    // attach current score to selected account when listing
    if (selectedName && healthScore != null) {
      for (var a = 0; a < accounts.length; a++) {
        if (accounts[a].name === selectedName) accounts[a].healthScore = healthScore;
      }
    }

    var ok = healthScore != null || accounts.length > 0 || violations.length > 0;
    if (!ok || body.length < 50) {
      return JSON.stringify({
        ok: false,
        error: 'no creator health',
        url: url,
        bodyLen: body.length,
        sample: body.slice(0, 200)
      });
    }
    return JSON.stringify({
      ok: true,
      switcherOpened: opened,
      healthScore: healthScore,
      statusLabel: statusLabel,
      selectedName: selectedName,
      accounts: accounts,
      violations: violations,
      url: url,
      raw: { bodyLen: body.length, sample: body.slice(0, 240) }
    });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String((e && e.message) || e) });
  }
})();
