/* Click next page on TK product manage list. */
(function () {
  function clean(t) {
    return String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
  }
  function isDisabled(el) {
    if (!el) return true;
    if (el.disabled) return true;
    var aria = (el.getAttribute && el.getAttribute('aria-disabled')) || '';
    if (String(aria).toLowerCase() === 'true') return true;
    var cls = (el.className || '').toString();
    if (/disabled|is-disabled|p-disabled|btn-disabled|arco-disabled/i.test(cls)) return true;
    var parent = el.parentElement;
    if (parent) {
      var pcls = (parent.className || '').toString();
      if (/disabled|is-disabled|p-disabled|arco-disabled/i.test(pcls)) return true;
    }
    return false;
  }
  function visible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    return r.width >= 1 && r.height >= 1;
  }
  try {
    var candidates = [];
    var nodes = document.querySelectorAll('button, a, li, div, span, [role="button"]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var text = clean(el.textContent);
      var aria = clean((el.getAttribute && el.getAttribute('aria-label')) || '');
      var title = clean(el.getAttribute ? el.getAttribute('title') || '' : '');
      var cls = (el.className || '').toString();
      if (text.length > 16 && aria.length > 24) continue;
      var hit =
        text === '下一页' ||
        text === '下页' ||
        text === '›' ||
        text === '>' ||
        text === '»' ||
        text === ' sup>' ||
        /^next$/i.test(text) ||
        /下一页|next page|go to next/i.test(aria + ' ' + title) ||
        /pagination-next|btn-next|arco-pagination-item-next|chevron-right|right-arrow/i.test(cls);
      if (hit) candidates.push(el);
    }
    // 当前页码 + 1
    var active = document.querySelector(
      '.arco-pagination-item-active, .p-pagination-item-active, [class*="pagination"] [class*="active"]'
    );
    if (active) {
      var cur = parseInt(clean(active.textContent), 10);
      if (isFinite(cur)) {
        var allPage = document.querySelectorAll(
          '.arco-pagination-item, .p-pagination li, [class*="pagination"] li, [class*="pagination"] button'
        );
        for (var pi = 0; pi < allPage.length; pi++) {
          var pt = clean(allPage[pi].textContent);
          if (pt === String(cur + 1)) candidates.unshift(allPage[pi]);
        }
      }
    }
    var clicked = null;
    for (var k = 0; k < candidates.length; k++) {
      var c = candidates[k];
      if (isDisabled(c) || !visible(c)) continue;
      try {
        c.click();
        clicked = {
          tag: c.tagName,
          text: clean(c.textContent).slice(0, 40),
          cls: (c.className || '').toString().slice(0, 80)
        };
        break;
      } catch (e1) {}
    }
    var page = null;
    var active2 = document.querySelector(
      '.arco-pagination-item-active, .p-pagination-item-active, [class*="pagination"] [class*="active"]'
    );
    if (active2) {
      var pn = parseInt(clean(active2.textContent), 10);
      if (isFinite(pn)) page = pn;
    }
    if (!clicked) {
      return JSON.stringify({
        ok: false,
        hasNext: false,
        clicked: false,
        page: page,
        error: 'next button not found or disabled',
        candidateCount: candidates.length
      });
    }
    return JSON.stringify({
      ok: true,
      hasNext: true,
      clicked: true,
      page: page,
      control: clicked,
      error: null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      hasNext: false,
      clicked: false,
      error: String(e && e.message ? e.message : e)
    });
  }
})();
