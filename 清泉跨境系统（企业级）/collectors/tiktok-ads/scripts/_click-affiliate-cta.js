/* Click CTA on affiliate landing (P3.0). Ziniao page exec.
 * Prefers: 前往联盟中心首页 → 合作数据分析 → 查看表现
 * Optional: window.__QQ_AFF_CLICK_LABEL__ override exact text.
 */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function clickEl(el) {
    if (!el) return false;
    try {
      el.scrollIntoView({ block: 'center', inline: 'center' });
    } catch (e1) {}
    try {
      el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: window }));
      el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      if (typeof el.click === 'function') el.click();
      return true;
    } catch (e2) {
      return false;
    }
  }
  function scoreText(tx) {
    var t = clean(tx);
    if (!t || t.length > 48) return -1;
    var s = 0;
    /* Prefer performance path over generic affiliate home */
    if (/合作数据分析|Performance analytics|View performance data/i.test(t)) s += 30;
    if (/数据洞察|Data\s*insights?/i.test(t)) s += 28;
    if (/^查看表现$|^表现$|View performance|^Performance$/i.test(t)) s += 26;
    if (/数据分析|Analytics/i.test(t) && /表现|Performance|transaction|insights/i.test(t)) s += 22;
    if (/^前往联盟中心首页$|Go to Affiliate (Center|Home)|Open Affiliate Center/i.test(t)) s += 12;
    if (/数据分析|Analytics|Performance/i.test(t) && /合作|达人|affiliate|creator/i.test(t)) s += 10;
    if (/公开合作|定向合作|发现服务商|样品申请|达人消息|创建广告/i.test(t)) s -= 8;
    return s;
  }
  try {
    var beforeUrl = location.href || '';
    var force = '';
    try {
      if (typeof window.__QQ_AFF_CLICK_LABEL__ === 'string') force = clean(window.__QQ_AFF_CLICK_LABEL__);
    } catch (e0) {}

    var candidates = [];
    var nodes = document.querySelectorAll('a, button, div, span, [role="button"], [role="link"]');
    for (var i = 0; i < Math.min(nodes.length, 800); i++) {
      var el = nodes[i];
      var tx = clean(el.innerText || el.textContent);
      if (!tx || tx.length > 48) continue;
      var sc = force ? (tx === force || tx.indexOf(force) >= 0 ? 30 : -1) : scoreText(tx);
      if (sc < 8) continue;
      var href = el.href || el.getAttribute('href') || null;
      candidates.push({ el: el, text: tx.slice(0, 80), score: sc, href: href, tag: el.tagName });
    }
    candidates.sort(function (a, b) {
      return b.score - a.score;
    });

    // also collect all scored for debug
    var top = candidates.slice(0, 12).map(function (c) {
      return { text: c.text, score: c.score, href: c.href, tag: c.tag };
    });

    if (!candidates.length) {
      return JSON.stringify({
        ok: false,
        module: 'affiliate_enter_center',
        action: 'click_cta',
        beforeUrl: beforeUrl,
        afterUrl: beforeUrl,
        candidates: top,
        error: 'no affiliate CTA (前往联盟中心首页 / 合作数据分析)'
      });
    }

    var pick = candidates[0];
    var target = pick.el;
    // prefer anchor ancestor
    var p = target;
    for (var d = 0; d < 5 && p; d++) {
      if (p.tagName === 'A' && (p.href || p.getAttribute('href'))) {
        target = p;
        break;
      }
      p = p.parentElement;
    }
    var clicked = clickEl(target);
    var afterHref = '';
    try {
      afterHref = (target.href || target.getAttribute('href') || '') || '';
    } catch (e3) {}

    return JSON.stringify({
      ok: !!clicked,
      module: 'affiliate_enter_center',
      action: 'click_cta',
      beforeUrl: beforeUrl,
      afterUrl: location.href || beforeUrl,
      clickedText: pick.text,
      clickedHref: afterHref || pick.href,
      score: pick.score,
      candidates: top,
      error: clicked ? null : 'click failed'
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      module: 'affiliate_enter_center',
      url: location.href || '',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
