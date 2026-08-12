/* TikTok shop experience score from /health-center/experience-score */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function parseNumber(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && isFinite(value)) return value;
    var s = String(value).trim();
    if (!s || s === '-' || s === '—' || s === '--') return null;
    var m = s.match(/-?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*%?/);
    if (!m) return null;
    var n = Number(String(m[1]).replace(/,/g, ''));
    return isFinite(n) ? n : null;
  }
  function bodyText() {
    return clean((document.body && (document.body.innerText || document.body.textContent)) || '');
  }
  try {
    var body = bodyText();
    var url = location.href || '';
    var experienceScore = null;
    var sm =
      body.match(/(\d(?:\.\d)?)\s*\/\s*5\.0/) ||
      body.match(/体验分[^0-9]{0,20}(\d(?:\.\d)?)/) ||
      body.match(/Experience\s*score[^0-9]{0,20}(\d(?:\.\d)?)/i);
    if (sm) experienceScore = parseNumber(sm[1]);

    function moduleScore(labels) {
      for (var i = 0; i < labels.length; i++) {
        var re = new RegExp(labels[i] + '[\\s\\S]{0,40}?(\\d(?:\\.\\d)?)\\s*\\/\\s*5', 'i');
        var m = body.match(re);
        if (m) return parseNumber(m[1]);
      }
      return null;
    }

    var productSatisfaction = moduleScore(['商品满意度', 'Product satisfaction']);
    var fulfillment = moduleScore(['履约物流', 'Fulfillment', 'Logistics']);
    var customerService = moduleScore(['客户服务', 'Customer service']);

    var metrics = {};
    var rateLabels = [
      ['60天差评率', 'bad_review_rate_60d'],
      ['商责退货退款率', 'seller_return_rate'],
      ['商责取消率', 'cancel_rate_30d'],
      ['按时送达率', 'on_time_delivery_rate'],
      ['售后处理时长', 'handle_hours_60d'],
      ['咨询不满意率', 'dissatisfaction_rate']
    ];
    for (var j = 0; j < rateLabels.length; j++) {
      var lab = rateLabels[j][0];
      var key = rateLabels[j][1];
      var rm = body.match(new RegExp(lab + '\\s*([\\d.]+\\s*%|[\\d.]+\\s*小时|[\\d.]+)', 'i'));
      if (rm) {
        var raw = rm[1];
        var n = parseNumber(raw);
        if (n != null) {
          if (/%/.test(raw)) metrics[key] = n / 100;
          else metrics[key] = n;
        }
      }
    }

    var ok =
      experienceScore != null ||
      productSatisfaction != null ||
      fulfillment != null ||
      customerService != null;
    if (!ok || body.length < 80) {
      return JSON.stringify({
        ok: false,
        error: 'no experience score',
        url: url,
        bodyLen: body.length,
        sample: body.slice(0, 200)
      });
    }
    return JSON.stringify({
      ok: true,
      experienceScore: experienceScore,
      productSatisfaction: productSatisfaction,
      fulfillmentScore: fulfillment,
      customerServiceScore: customerService,
      metrics: metrics,
      url: url,
      raw: { bodyLen: body.length, sample: body.slice(0, 240) }
    });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String((e && e.message) || e) });
  }
})();
