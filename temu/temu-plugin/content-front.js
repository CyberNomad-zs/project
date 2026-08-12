// Temu 前台商品页 content script：解析产品 variant（颜色/尺码等）数据，发送给 background 做快照对比。
// 运行于 www.temu.com，document_idle 注入。
(function () {
  var LOG = TemuLogger.createLogger('front');
  LOG.info('content-front.js loaded -- v1');

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ---------- 工具 ----------
  function visible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function text(el) { return (el.textContent || '').trim(); }

  // ---------- 产品标题 ----------
  function readTitle() {
    // 尝试常见的标题选择器
    for (const sel of ['h1', '[data-testid*="title"]', '[class*="title" i]', '[class*="name" i]']) {
      try {
        const els = [...document.querySelectorAll(sel)].filter(visible);
        // 取最长的可见文本（通常是产品名）
        const best = els
          .filter((e) => text(e).length >= 4 && text(e).length <= 200)
          .sort((a, b) => text(b).length - text(a).length)[0];
        if (best) return text(best).slice(0, 120);
      } catch (e) {}
    }
    return document.title.slice(0, 120) || '';
  }

  // ---------- 价格 ----------
  function readPrice() {
    // 常见价格选择器：带货币符号的元素
    for (const sel of ['[class*="price" i]', '[class*="amount" i]', '[data-testid*="price"]']) {
      try {
        const els = [...document.querySelectorAll(sel)].filter(visible);
        for (const el of els) {
          const t = text(el);
          const m = t.match(/[£€$]\s*[\d,.]+/);
          if (m) return m[0];
        }
      } catch (e) {}
    }
    // 兜底：全页搜第一个货币+数字组合
    const all = [...document.querySelectorAll('span,div,p')].filter(visible);
    for (const el of all.slice(0, 200)) {
      const t = text(el);
      if (t.length > 3 && t.length < 20 && /^[£€$]/.test(t) && /\d/.test(t)) return t;
    }
    return '';
  }

  // ---------- Variant 解析 ----------
  // 策略：找页面中"一组相似的可点击子元素"的容器——通常是颜色色块组/尺码按钮组。
  // 每个 variant 组的特点：容器内有 ≥2 个外观相似的同级子元素，每个代表一个选项。

  function isClickable(el) {
    const tag = el.tagName;
    if (tag === 'BUTTON' || tag === 'A' || tag === 'INPUT' || tag === 'SELECT') return true;
    if (el.getAttribute('role') === 'button' || el.getAttribute('role') === 'radio') return true;
    if (el.tabIndex >= 0) return true;
    // 检查是否有 pointer 事件监听（间接判断可交互）
    const style = window.getComputedStyle(el);
    if (style.cursor === 'pointer') return true;
    return false;
  }

  function isProbablyDisabled(el) {
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return true;
    const cls = (el.className && typeof el.className === 'string') ? el.className.toLowerCase() : '';
    if (/disabled|sold.out|unavailable|out.of.stock|oos/i.test(cls)) return true;
    // 检查透明度（灰色=不可用）
    const style = window.getComputedStyle(el);
    if (parseFloat(style.opacity) < 0.5) return true;
    // 检查是否有点击拦截层（常见于不可用色块上的斜线/遮罩）
    const overlay = el.querySelector('[class*="sold" i],[class*="disable" i],[class*="unavailable" i]');
    if (overlay && visible(overlay)) return true;
    return false;
  }

  // 判断两个元素是否"同类型"（同标签、相似 class 前缀、相似尺寸）
  function sameType(a, b) {
    if (a.tagName !== b.tagName) return false;
    const ra = a.getBoundingClientRect();
    const rb = b.getBoundingClientRect();
    // 宽高差不超过 50%
    if (ra.width === 0 || rb.width === 0) return false;
    const ratio = Math.max(ra.width, rb.width) / Math.min(ra.width, rb.width);
    if (ratio > 1.8) return false;
    return true;
  }

  // 从元素提取 variant 名、图片、是否选中
  function extractOption(el) {
    const t = text(el).slice(0, 40);
    const selected = !!(
      el.getAttribute('aria-selected') === 'true' ||
      el.getAttribute('aria-checked') === 'true' ||
      /selected|active|current|checked|chosen/i.test((el.className && typeof el.className === 'string') ? el.className : '')
    );
    const disabled = isProbablyDisabled(el);
    // 找图片（色块背景图或 img 子元素）
    let img = '';
    const bg = window.getComputedStyle(el).backgroundImage;
    if (bg && bg !== 'none' && /url\(/.test(bg)) {
      const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
      if (m) img = m[1];
    }
    if (!img) {
      const childImg = el.querySelector('img');
      if (childImg) img = childImg.src || '';
    }
    // 背景色 fallback（色块常用纯色背景代替图片）
    let color = '';
    if (!img) {
      const bgc = window.getComputedStyle(el).backgroundColor;
      if (bgc && bgc !== 'rgba(0, 0, 0, 0)' && bgc !== 'transparent') {
        color = bgc;
      }
    }
    return { name: t, selected, disabled, img: img.slice(0, 500), color };
  }

  // 判断一组元素是否是 variant 选择器（排除导航、分类菜单等）
  function looksLikeVariantGroup(container, children) {
    if (children.length < 2) return false;
    if (children.length > 60) return false; // 不太可能有 60+ 种颜色
    const texts = children.map((c) => text(c)).filter(Boolean);
    // variant 文本通常很短：颜色名(3-15字符)、尺码(1-4字符)
    const avgLen = texts.reduce((s, t) => s + t.length, 0) / Math.max(1, texts.length);
    if (avgLen > 30) return false; // 文字太长 → 不是 variant 选择器
    // 排除导航菜单（文本含 "Home", "Cart", "Account" 等）
    const navWords = texts.filter((t) => /home|cart|account|login|sign|menu|search|category|help/i.test(t));
    if (navWords.length >= 2) return false;
    // variant 容器通常在页面中部（top 在 200-1500 范围），不在顶栏/底栏
    const r = container.getBoundingClientRect();
    if (r.top < 80 || r.top > window.innerHeight * 0.85) return false;
    return true;
  }

  function findVariantGroups() {
    const groups = [];
    // 策略 1：找含有 data-testid / class 包含 variant/sku/spec/swatch/color/size 的容器
    const hintSelectors = [
      '[data-testid*="sku" i]', '[data-testid*="spec" i]', '[data-testid*="variant" i]',
      '[class*="sku" i]', '[class*="spec" i]', '[class*="variant" i]',
      '[class*="swatch" i]', '[class*="color" i]', '[class*="size" i]',
      '[class*="option" i]', '[class*="selector" i]', '[class*="picker" i]',
    ];
    const seen = new Set();
    for (const sel of hintSelectors) {
      try {
        for (const container of document.querySelectorAll(sel)) {
          if (!visible(container) || seen.has(container)) continue;
          // 收集该容器下的直接可交互子元素（或孙子元素，如果直接子元素很少）
          let children = [...container.children].filter((c) => visible(c) && isClickable(c));
          // 如果直接子元素不多，往下一层找
          if (children.length < 2) {
            const subChildren = [];
            for (const ch of [...container.children]) {
              subChildren.push(...[...ch.querySelectorAll('*')].filter((c) => visible(c) && isClickable(c)));
            }
            // 取出现最多的标签类型
            const tagCount = {};
            for (const c of subChildren) tagCount[c.tagName] = (tagCount[c.tagName] || 0) + 1;
            const bestTag = Object.entries(tagCount).sort((a, b) => b[1] - a[1])[0];
            if (bestTag && bestTag[1] >= 2) {
              children = subChildren.filter((c) => c.tagName === bestTag[0]);
            }
          }
          if (children.length < 2) continue;
          children = children.filter((c) => sameType(c, children[0]));
          if (!looksLikeVariantGroup(container, children)) continue;
          const options = children.map(extractOption);
          // 推断组名：从容器内找 label / title 文本
          let groupName = '';
          const label = container.querySelector('[class*="label" i],[class*="title" i],[class*="name" i],label,span');
          if (label) { const lt = text(label).replace(/[:：]\s*$/, ''); if (lt.length >= 1 && lt.length <= 20) groupName = lt; }
          if (!groupName && options.length > 0) {
            // 从选项推测：如果选项文本都很短(1-3字符) → Size；如果多有图片/颜色 → Color
            const hasImg = options.filter((o) => o.img || o.color).length;
            if (hasImg >= options.length * 0.5) groupName = 'Color';
            else if (options.every((o) => o.name.length <= 4)) groupName = 'Size';
          }
          groups.push({ group: groupName || 'Variant', options });
          seen.add(container);
        }
      } catch (e) {}
    }

    // 策略 2（兜底）：扫全页，找"多个同标签+同尺寸的可点击元素群"作为 variant 组
    if (groups.length === 0) {
      const allClickable = [...document.querySelectorAll('*')].filter((el) => visible(el) && isClickable(el));
      // 按标签+class前缀+尺寸分组
      const buckets = {};
      for (const el of allClickable) {
        const r = el.getBoundingClientRect();
        const key = el.tagName + '|' + Math.round(r.width) + 'x' + Math.round(r.height);
        if (!buckets[key]) buckets[key] = [];
        buckets[key].push(el);
      }
      for (const key of Object.keys(buckets)) {
        const els = buckets[key];
        if (els.length < 2 || els.length > 60) continue;
        // 找它们最近的共同祖先
        let ancestor = els[0].parentElement;
        for (let i = 0; i < 6 && ancestor; i++) {
          if (els.every((e) => ancestor.contains(e))) break;
          ancestor = ancestor.parentElement;
        }
        if (!ancestor || !visible(ancestor)) continue;
        const options = els.map(extractOption);
        if (!looksLikeVariantGroup(ancestor, els)) continue;
        const hasImg = options.filter((o) => o.img || o.color).length;
        const groupName = hasImg >= options.length * 0.5 ? 'Color' : (options.every((o) => o.name.length <= 4) ? 'Size' : 'Variant');
        groups.push({ group: groupName, options });
        if (groups.length >= 6) break; // 最多 6 组
      }
    }

    return groups;
  }

  // ---------- 提取并上报 ----------
  function extractProductData() {
    // 只对产品详情页生效（URL 含 goods_id 或 -m- 模式）
    const url = window.location.href;
    if (!/goods_id=|\/-\w{2,}-m-|product/i.test(url)) {
      LOG.info('Skipped: not a product page, url=' + url.slice(0, 80));
      return null;
    }
    const title = readTitle();
    const price = readPrice();
    const variants = findVariantGroups();
    if (!title && variants.length === 0) {
      LOG.info('Skipped: no title and no variants found');
      return null;
    }
    const data = {
      url: url.split('?')[0], // 去参数，避免 session id 等每次变化导致 diff 误判
      fullUrl: url,
      title,
      price,
      variants,
      totalOptions: variants.reduce((s, g) => s + g.options.length, 0),
      availableOptions: variants.reduce((s, g) => s + g.options.filter((o) => !o.disabled).length, 0),
    };
    LOG.info('Product data extracted: title=' + title.slice(0, 30) + ' price=' + price + ' variantGroups=' + variants.length + ' totalOptions=' + data.totalOptions + ' available=' + data.availableOptions);
    return data;
  }

  function sendToBackground(data) {
    if (!data) return;
    try {
      chrome.runtime.sendMessage({ type: 'frontCapture', data }, (resp) => {
        if (chrome.runtime.lastError) {
          // SW 可能未就绪（页面加载时 SW 刚被唤醒），静默忽略
          return;
        }
      });
    } catch (e) {}
  }

  // ---------- 初始化 ----------
  // 页面加载完成后延迟一下再扫（React 渲染需要时间）
  async function init() {
    await sleep(2500); // 等 SPA 渲染
    let data = extractProductData();
    // 如果第一次没扫到 variant（可能页面还在加载），再等几秒重试
    if (data && data.variants.length === 0) {
      await sleep(3000);
      data = extractProductData();
    }
    sendToBackground(data);
  }

  // 监听来自 background 的手动检查请求
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.cmd === 'frontCheck') {
      (async () => {
        const data = extractProductData();
        sendToBackground(data);
        sendResponse({ ok: true, data });
      })();
      return true;
    }
  });

  init();
})();
