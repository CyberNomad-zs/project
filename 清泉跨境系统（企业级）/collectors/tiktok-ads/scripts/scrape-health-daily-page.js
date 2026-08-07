/* TikTok account health from /health-center (账号健康分). */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function parseNumber(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && isFinite(value)) return value;
    var s = String(value).trim();
    if (!s || s === '-' || s === '—' || s === '--') return null;
    var pct = /%/.test(s);
    var m = s.match(/-?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*%?/);
    if (!m) return null;
    var n = Number(String(m[1]).replace(/,/g, ''));
    if (!isFinite(n)) return null;
    if (pct) n = n / 100;
    return n;
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  function findRate(body, labels) {
    for (var i = 0; i < labels.length; i++) {
      var lab = labels[i];
      // "商责取消率 0.36% 目标值" or "延迟发货率 --"
      var re = new RegExp(lab + '\\s*([\\d.]+\\s*%|--|—|-)', 'i');
      var m = body.match(re);
      if (!m) continue;
      if (m[1] === '--' || m[1] === '—' || m[1] === '-') return { value: null, label: lab + ' ' + m[1], missing: true };
      var n = parseNumber(m[1]);
      if (n != null) return { value: n, label: lab + ' ' + m[1] };
    }
    return null;
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    // Score often appears as standalone number near 账号健康分 / 健康, e.g. "健康 节点记录 你的账号很健康。 277 0 50 100"
    var healthScore = null;
    var sm =
      body.match(/账号健康分[^0-9]{0,40}?(\d{2,4})\b/) ||
      body.match(/健康分[^0-9]{0,20}?(\d{2,4})\b/) ||
      body.match(/你的账号很健康[^0-9]{0,30}?(\d{2,4})\b/) ||
      body.match(/Health\s*score[^0-9]{0,20}?(\d{2,4})/i);
    if (sm) healthScore = Number(sm[1]);
    // fallback: first 2-4 digit after 健康 section before 需要处理
    if (healthScore == null) {
      var sec = body.match(/账号健康分([\s\S]{0,200}?)需要处理/);
      if (sec) {
        var nums = sec[1].match(/\b(\d{2,4})\b/g);
        if (nums && nums.length) healthScore = Number(nums[0]);
      }
    }

    var late = findRate(body, ['延迟发货率', 'Late dispatch rate', 'Late shipment rate', '晚发率']);
    var neg = findRate(body, ['商责差评率', 'Negative feedback rate', '差评率']);
    var cancel = findRate(body, ['商责取消率', 'Seller cancellation rate', '取消率']);

    var statusLabel = null;
    var st =
      body.match(/你的账号很健康[^。！!]*[。！!]?/) ||
      body.match(/有待改进/) ||
      body.match(/需要改进/) ||
      body.match(/账号健康[：:]\s*([^\s]+)/) ||
      body.match(/(Excellent|Good|Fair|Poor|At risk)/i);
    if (st) statusLabel = clean(st[0]).slice(0, 40);

    var raw = {
      bodyLen: body.length,
      sample: body.slice(0, 280),
      late: late && late.label,
      neg: neg && neg.label,
      cancel: cancel && cancel.label,
      cancelRate: cancel ? cancel.value : null
    };

    var ok = healthScore != null || !!(late && late.value != null) || !!(neg && neg.value != null) || !!statusLabel;
    if (!ok || body.length < 100) {
      return JSON.stringify({
        ok: false,
        module: 'health_daily',
        source: 'health-center',
        url: url,
        raw: raw,
        error: 'no health metrics. url=' + url
      });
    }
    return JSON.stringify({
      ok: true,
      module: 'health_daily',
      source: 'health-center',
      url: url,
      title: document.title || '',
      healthScore: healthScore,
      lateDispatchRate: late && !late.missing ? late.value : null,
      negativeFeedbackRate: neg && !neg.missing ? neg.value : null,
      statusLabel: statusLabel,
      raw: raw,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'health_daily',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
