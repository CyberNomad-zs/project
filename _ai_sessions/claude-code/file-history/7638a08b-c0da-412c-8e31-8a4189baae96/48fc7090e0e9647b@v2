/* Set TikTok ads dashboard date range. Sync IIFE for ziniao page exec.
 * Placeholders replaced by PowerShell: __DATE_MODE__ (yesterday|today), __ACTION__ (open|pick|status), __BIZ_TZ__ (IANA e.g. Europe/London)
 * No // comments (minified to one line). */
(function () {
  var MODE = '__DATE_MODE__';
  var ACTION = '__ACTION__';
  var BIZ_TZ = '__BIZ_TZ__';

  function cleanText(t) {
    return String(t == null ? '' : t)
      .replace(/\s+/g, ' ')
      .trim();
  }

  function pad2(n) {
    return (n < 10 ? '0' : '') + n;
  }

  function formatYmd(d) {
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  /* 业务日按广告后台时区（英区 Europe/London），避免中国本地日历日错位 */
  function formatYmdInTz(date, timeZone) {
    try {
      return new Intl.DateTimeFormat('en-CA', {
        timeZone: timeZone || 'Europe/London',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }).format(date);
    } catch (e) {
      return formatYmd(date);
    }
  }

  function shiftYmd(ymd, deltaDays) {
    var p = String(ymd).split('-');
    var utc = new Date(Date.UTC(Number(p[0]), Number(p[1]) - 1, Number(p[2]), 12, 0, 0));
    utc.setUTCDate(utc.getUTCDate() + deltaDays);
    return utc.getUTCFullYear() + '-' + pad2(utc.getUTCMonth() + 1) + '-' + pad2(utc.getUTCDate());
  }

  function targetMeta(mode) {
    var tz = BIZ_TZ && BIZ_TZ.indexOf('__') < 0 ? BIZ_TZ : 'Europe/London';
    var todayStr = formatYmdInTz(new Date(), tz);
    if (mode === 'today') {
      return { start: todayStr, end: todayStr, labels: ['今天', '今日', 'Today', 'today'], tz: tz };
    }
    var y = shiftYmd(todayStr, -1);
    return {
      start: y,
      end: y,
      labels: ['昨天', '昨日', 'Yesterday', 'yesterday'],
      tz: tz
    };
  }

  function parseRangeFromText(text) {
    var t = cleanText(text);
    var m = t.match(/(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})\s*[-–~至到]\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})/);
    if (!m) return null;
    function norm(s) {
      var p = s.replace(/\//g, '-').split('-');
      return p[0] + '-' + pad2(Number(p[1])) + '-' + pad2(Number(p[2]));
    }
    return { start: norm(m[1]), end: norm(m[2]), raw: m[0] };
  }

  function isVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    var st = window.getComputedStyle(el);
    if (!st || st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) {
      return false;
    }
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function clickEl(el) {
    if (!el) return false;
    try {
      el.scrollIntoView({ block: 'center', inline: 'center' });
    } catch (e) {}
    try {
      if (el.focus) el.focus();
    } catch (e2) {}
    var opts = { bubbles: true, cancelable: true, view: window };
    try {
      el.dispatchEvent(new MouseEvent('mousedown', opts));
      el.dispatchEvent(new MouseEvent('mouseup', opts));
      el.dispatchEvent(new MouseEvent('click', opts));
    } catch (e3) {
      try {
        el.click();
      } catch (e4) {
        return false;
      }
    }
    return true;
  }

  function readDisplayedRange() {
    var nodes = document.querySelectorAll('input, button, div, span, p, a');
    var best = null;
    for (var i = 0; i < nodes.length && i < 5000; i++) {
      var el = nodes[i];
      if (!isVisible(el)) continue;
      var text = '';
      if (el.tagName === 'INPUT') text = el.value || el.getAttribute('placeholder') || '';
      else text = el.innerText || el.textContent || '';
      text = cleanText(text).slice(0, 80);
      var rg = parseRangeFromText(text);
      if (!rg) continue;
      var r = el.getBoundingClientRect();
      if (r.top > window.innerHeight * 0.55) continue;
      best = { el: el, range: rg, text: text };
      if (el.tagName === 'INPUT' || /picker|date|calendar|range/i.test(el.className || '')) break;
    }
    return best;
  }

  function findDateTrigger() {
    var shown = readDisplayedRange();
    if (shown && shown.el) {
      var cur = shown.el;
      for (var d = 0; d < 6 && cur; d++) {
        if (
          cur.matches &&
          cur.matches(
            'button, [role="button"], input, .arco-picker, .arco-picker-range, [class*="picker"], [class*="Picker"], [class*="date"], [class*="Date"]'
          )
        ) {
          return { el: cur, range: shown.range, via: 'range-text' };
        }
        cur = cur.parentElement;
      }
      return { el: shown.el, range: shown.range, via: 'range-text' };
    }
    var sels = [
      '.arco-picker-range',
      '.arco-picker',
      '[class*="RangePicker"]',
      '[class*="range-picker"]',
      '[class*="DatePicker"]',
      'input[placeholder*="日期"]',
      'input[placeholder*="Date"]'
    ];
    for (var s = 0; s < sels.length; s++) {
      var list = document.querySelectorAll(sels[s]);
      for (var j = 0; j < list.length; j++) {
        if (isVisible(list[j])) return { el: list[j], range: null, via: sels[s] };
      }
    }
    return null;
  }

  function findShortcut(labels) {
    var nodes = document.querySelectorAll(
      'button, a, li, div, span, [role="button"], [role="option"], [role="menuitem"]'
    );
    var candidates = [];
    for (var i = 0; i < nodes.length && i < 8000; i++) {
      var el = nodes[i];
      if (!isVisible(el)) continue;
      var t = cleanText(el.innerText || el.textContent || '');
      if (!t || t.length > 20) continue;
      for (var k = 0; k < labels.length; k++) {
        if (t === labels[k] || t.toLowerCase() === String(labels[k]).toLowerCase()) {
          candidates.push({ el: el, text: t, exact: true });
          break;
        }
      }
    }
    if (!candidates.length) {
      for (var i2 = 0; i2 < nodes.length && i2 < 8000; i2++) {
        var el2 = nodes[i2];
        if (!isVisible(el2)) continue;
        var t2 = cleanText(el2.innerText || el2.textContent || '');
        if (!t2 || t2.length > 20) continue;
        for (var k2 = 0; k2 < labels.length; k2++) {
          var lab = String(labels[k2]);
          if (t2.indexOf(lab) >= 0 || t2.toLowerCase().indexOf(lab.toLowerCase()) >= 0) {
            candidates.push({ el: el2, text: t2, exact: false });
            break;
          }
        }
      }
    }
    if (!candidates.length) return null;
    candidates.sort(function (a, b) {
      return (b.exact ? 1 : 0) - (a.exact ? 1 : 0) || a.text.length - b.text.length;
    });
    return candidates[0];
  }

  function panelOpen() {
    var panelSels = [
      '.arco-picker-container',
      '.arco-trigger-popup',
      '.arco-panel-date',
      '[class*="picker-container"]',
      '[class*="PickerDropdown"]',
      '[class*="datepicker"]',
      '[class*="DatePicker"]',
      '[class*="calendar-panel"]',
      '[class*="shortcut"]'
    ];
    for (var i = 0; i < panelSels.length; i++) {
      var els = document.querySelectorAll(panelSels[i]);
      for (var j = 0; j < els.length; j++) {
        if (isVisible(els[j])) return true;
      }
    }
    return !!findShortcut(['今天', '昨天', '近7天', 'Today', 'Yesterday', 'Last 7 days']);
  }

  var mode = String(MODE || 'yesterday').toLowerCase();
  if (mode !== 'today' && mode !== 'yesterday') mode = 'yesterday';
  var action = String(ACTION || 'status').toLowerCase();
  var target = targetMeta(mode);
  var shown = readDisplayedRange();
  var range = shown ? shown.range : null;

  if (action === 'status') {
    var matchedStatus =
      !!(range && range.start === target.start && range.end === target.end);
    return JSON.stringify({
      ok: true,
      action: 'status',
      mode: mode,
      tz: target.tz || BIZ_TZ,
      range: range,
      target: { start: target.start, end: target.end },
      matched: matchedStatus,
      panelOpen: panelOpen()
    });
  }

  if (
    range &&
    range.start === target.start &&
    range.end === target.end &&
    action !== 'pick'
  ) {
    return JSON.stringify({
      ok: true,
      skipped: true,
      action: action,
      mode: mode,
      before: range,
      after: range,
      message: 'already on target range'
    });
  }

  if (action === 'open') {
    var trigger = findDateTrigger();
    if (!trigger || !trigger.el) {
      return JSON.stringify({
        ok: false,
        action: 'open',
        mode: mode,
        before: range,
        error: '未找到日期选择器（页面上无日期区间控件）'
      });
    }
    clickEl(trigger.el);
    if (!panelOpen() && trigger.el.parentElement) {
      clickEl(trigger.el.parentElement);
    }
    if (!panelOpen()) {
      var icon =
        document.querySelector('[class*="calendar"]') ||
        document.querySelector('[class*="Calendar"]');
      if (icon) {
        clickEl(icon.closest ? icon.closest('button, div, span') || icon : icon);
      }
    }
    return JSON.stringify({
      ok: true,
      action: 'open',
      mode: mode,
      before: range,
      triggerVia: trigger.via,
      panelOpen: panelOpen(),
      message: 'date picker open clicked'
    });
  }

  if (action === 'pick') {
    if (!panelOpen()) {
      var trigger2 = findDateTrigger();
      if (trigger2 && trigger2.el) clickEl(trigger2.el);
    }
    var sc = findShortcut(target.labels);
    if (!sc) {
      return JSON.stringify({
        ok: false,
        action: 'pick',
        mode: mode,
        before: range,
        panelOpen: panelOpen(),
        error: '未找到快捷项: ' + target.labels.join('/')
      });
    }
    clickEl(sc.el);
    var applyBtns = findShortcut(['确定', '应用', 'Apply', 'OK', '确认', 'Done']);
    if (applyBtns && /确定|应用|Apply|OK|确认|Done/i.test(applyBtns.text)) {
      clickEl(applyBtns.el);
    }
    var afterShown = readDisplayedRange();
    var after = afterShown ? afterShown.range : null;
    var matched =
      !!(after && after.start === target.start && after.end === target.end);
    var changed =
      !!(after && range && (after.start !== range.start || after.end !== range.end));
    return JSON.stringify({
      ok: true,
      softOk: true,
      action: 'pick',
      mode: mode,
      clicked: sc.text,
      before: range,
      after: after,
      target: { start: target.start, end: target.end },
      matched: matched,
      changed: changed,
      message: 'clicked ' + sc.text
    });
  }

  return JSON.stringify({
    ok: false,
    action: action,
    mode: mode,
    error: 'unknown action (use open|pick|status)'
  });
})();
