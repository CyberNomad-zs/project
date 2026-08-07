/* Tiny location/ready check for Ziniao page exec (blank / wrong-route guard). */
(function () {
  try {
    var href = String(location.href || '');
    var ready = document.readyState || '';
    var bodyLen = 0;
    try {
      bodyLen = ((document.body && (document.body.innerText || document.body.textContent)) || '').length;
    } catch (e0) {}
    var blank = !href || href === 'about:blank' || href.indexOf('about:blank') === 0;
    return JSON.stringify({
      ok: !blank,
      href: href,
      readyState: ready,
      bodyLen: bodyLen,
      blank: blank,
      error: blank ? 'about:blank' : null
    });
  } catch (e) {
    return JSON.stringify({
      ok: false,
      href: '',
      blank: true,
      error: String(e && e.message ? e.message : e)
    });
  }
})();
