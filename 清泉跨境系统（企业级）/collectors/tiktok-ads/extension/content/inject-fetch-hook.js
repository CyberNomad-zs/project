/**
 * 注入到页面主世界：hook fetch / XHR，把疑似报表响应 post 给 content script
 * 注意：此文件不能用 ES module
 */
(function () {
  if (window.__TK_AD_FETCH_HOOKED__) return;
  window.__TK_AD_FETCH_HOOKED__ = true;

  const REPORT_RE =
    /report|stat|metric|campaign|gmv|ads?\/api|shop_ads|analytics|performance|overview|data_list|getlist|insight/i;

  function isLikely(url) {
    try {
      return REPORT_RE.test(String(url || ''));
    } catch {
      return false;
    }
  }

  function emit(url, body) {
    try {
      window.postMessage(
        {
          source: 'tk-ad-scraper-hook',
          type: 'API_PAYLOAD',
          url: String(url || ''),
          body
        },
        '*'
      );
    } catch (_) {
      /* ignore */
    }
  }

  const rawFetch = window.fetch;
  if (typeof rawFetch === 'function') {
    window.fetch = async function (...args) {
      const res = await rawFetch.apply(this, args);
      try {
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
        if (isLikely(url)) {
          const clone = res.clone();
          clone
            .text()
            .then((text) => {
              let body = text;
              try {
                body = JSON.parse(text);
              } catch (_) {
                /* keep text */
              }
              emit(url, body);
            })
            .catch(() => {});
        }
      } catch (_) {
        /* ignore */
      }
      return res;
    };
  }

  const XO = XMLHttpRequest.prototype.open;
  const XS = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__tkAdUrl = url;
    return XO.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener('load', function () {
      try {
        if (!isLikely(this.__tkAdUrl)) return;
        let body = this.responseText;
        try {
          body = JSON.parse(this.responseText);
        } catch (_) {
          /* keep */
        }
        emit(this.__tkAdUrl, body);
      } catch (_) {
        /* ignore */
      }
    });
    return XS.apply(this, args);
  };
})();
