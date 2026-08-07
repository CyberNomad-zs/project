/* Click Compass top-nav by visible label. Ziniao page exec.
 * Return { ok, action, beforeUrl, afterUrl, matchedText, error }
 * Usage: set window.__QQ_CLICK_NAV_LABEL__ = '内容分析' before exec, or edit DEFAULT_LABEL.
 */
(function () {
  var DEFAULT_LABEL = '内容分析';
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function label() {
    try {
      if (typeof window.__QQ_CLICK_NAV_LABEL__ === 'string' && window.__QQ_CLICK_NAV_LABEL__) {
        return String(window.__QQ_CLICK_NAV_LABEL__);
      }
    } catch (e) {}
    return DEFAULT_LABEL;
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
  try {
    var want = clean(label());
    var beforeUrl = location.href || '';
    var candidates = [];
    var nodes = document.querySelectorAll('div, span, a, button, li');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var tx = clean(el.innerText || el.textContent);
      if (!tx || tx.length > 30) continue;
      if (tx === want || tx.indexOf(want) === 0) {
        var cls = String(el.className || '');
        var score = 0;
        if (cls.indexOf('navButton') >= 0 || cls.indexOf('_navButton') >= 0) score += 5;
        if (cls.indexOf('menu') >= 0 || cls.indexOf('Menu') >= 0) score += 2;
        if (el.tagName === 'SPAN' && el.parentElement) score += 1;
        if (tx === want) score += 3;
        candidates.push({ el: el, text: tx, score: score, cls: cls.slice(0, 80) });
      }
    }
    candidates.sort(function (a, b) {
      return b.score - a.score;
    });
    if (!candidates.length) {
      return JSON.stringify({
        ok: false,
        action: 'click_nav',
        want: want,
        beforeUrl: beforeUrl,
        afterUrl: beforeUrl,
        error: 'no element with label ' + want
      });
    }
    var pick = candidates[0];
    var target = pick.el;
    // prefer clickable parent navButton
    var p = target;
    for (var d = 0; d < 4 && p; d++) {
      var pc = String(p.className || '');
      if (pc.indexOf('navButton') >= 0 || pc.indexOf('_navButton') >= 0 || pc.indexOf('cursor-pointer') >= 0) {
        target = p;
        break;
      }
      p = p.parentElement;
    }
    var clicked = clickEl(target);
    return JSON.stringify({
      ok: !!clicked,
      action: 'click_nav',
      want: want,
      matchedText: pick.text,
      matchedCls: pick.cls,
      score: pick.score,
      beforeUrl: beforeUrl,
      afterUrl: location.href || '',
      candidateCount: candidates.length,
      error: clicked ? null : 'click dispatch failed'
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      action: 'click_nav',
      error: String(e && e.message ? e.message : e)
    });
  }
})();
