/**
 * 会话级切店（右上角头像/店名 → 切换 →「切换店铺」弹窗）
 * 对齐 temu-plugin content.js，多 mall 共用账号时必须用此方式，不能用「来源店铺」筛选。
 *
 * 2026-07-31 加固（同事机「打不开切换店铺弹窗 / 当前=未知」）：
 *  - 切店前强制滚回顶，避免顶栏启发式因 scroll 失效
 *  - 放宽顶栏店名识别（top 阈值、排除词、假店名过滤）
 *  - openStoreModal 多策略：店名 / 箭头 / 头像 / 右上角坐标点
 *  - 失败时带回诊断串，方便对照日志
 */
import { log } from './logger.js';

// 注意：经 page.evaluate → eval(helpers) 注入。必须用 function/var，不能用 const/let
// （const/let 不泄漏到 evaluate 外层；切店回调里直接调 realClick/sleep/visible 会挂）。
const SWITCH_HELPERS = `
  function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
  function visible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function textEls(re, maxLen) {
    maxLen = maxLen == null ? 40 : maxLen;
    return [...document.querySelectorAll('*')].filter((e) => {
      const t = (e.textContent || '').trim();
      return re.test(t) && t.length <= maxLen;
    });
  }
  function clickableAncestor(el) {
    let p = el;
    for (let i = 0; i < 6 && p; i++, p = p.parentElement) {
      if (p.tagName === 'BUTTON' || p.getAttribute('role') === 'button') return p;
      // 顶栏店名常包在可点 div 上（cursor:pointer）
      try {
        const cur = window.getComputedStyle(p).cursor;
        if (cur === 'pointer') return p;
      } catch (e) {}
    }
    return el;
  }
  function realClick(el) {
    if (!el) return;
    const opts = { bubbles: true, cancelable: true, view: window };
    try { el.scrollIntoView({ block: 'center' }); } catch (e) {}
    for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
      try { el.dispatchEvent(new MouseEvent(type, opts)); } catch (e) {}
    }
    try { el.click(); } catch (e) {}
  }
  async function waitFor(fn, timeout, step) {
    timeout = timeout == null ? 8000 : timeout;
    step = step == null ? 300 : step;
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      let v = null;
      try { v = fn(); } catch (e) { v = null; }
      if (v) return v;
      await sleep(step);
    }
    return null;
  }
  function innermost(els) {
    return els.slice().sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)[0] || null;
  }
  // 假店名 / 顶栏噪声（货号、UI 标签、站点名）
  function isFakeStoreName(t) {
    if (!t) return true;
    if (/^(Seller Central|Beta|NEW|SKC|SKU|USD|Best Seller|Temu|US|EU|Global|CN|UK|DE|FR|All|More)$/i.test(t)) return true;
    if (/^[A-Z0-9]{6,}$/.test(t)) return true; // 纯大写货号
    if (/^\\d+$/.test(t)) return true;
    return false;
  }
  function findStoreNameEl() {
    const W = window.innerWidth || 1280;
    let best = null;
    // 顶栏常见高度 48–72；headless/缩放后可能略高，放宽到 120
    const TOP_MAX = 120;
    for (const el of document.querySelectorAll('span,a,div,button,p,b,strong,label')) {
      const t = (el.textContent || '').trim();
      if (!/^[A-Za-z][A-Za-z0-9]*(?:\\s[A-Za-z0-9]+){0,4}$/.test(t)) continue;
      if (t.length < 2 || t.length > 36) continue;
      if (isFakeStoreName(t)) continue;
      if (el.children.length > 3) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.top < -4 || r.top > TOP_MAX) continue;
      // 右半屏；极窄视口时放宽到 0.35
      const leftMin = W < 900 ? W * 0.35 : W * 0.45;
      if (r.left < leftMin) continue;
      if (!best || r.left > best.left) best = { el, left: r.left, t: t };
    }
    return best ? best.el : null;
  }
  function readStoreName() {
    const el = findStoreNameEl();
    if (!el) return null;
    const t = (el.textContent || '').trim();
    return isFakeStoreName(t) ? null : t;
  }
  function modalOpen() {
    return textEls(/切换店铺|您的账户存在/, 40).length > 0;
  }
  function clickTopRightHotspot() {
    // 顶栏最右侧一排：头像 / 箭头 / 店名区域，按坐标扫几个点
    const W = window.innerWidth || 1280;
    const ys = [18, 28, 40, 56];
    const xs = [W - 24, W - 48, W - 80, W - 120, W - 160];
    for (const y of ys) {
      for (const x of xs) {
        const el = document.elementFromPoint(x, y);
        if (!el) continue;
        realClick(clickableAncestor(el));
      }
    }
  }
  // 对齐插件：点顶栏店名/箭头 → 下拉「切换」→ 「切换店铺」弹窗
  // 返回 {ok, diag[]}
  async function openStoreModal() {
    const diag = [];
    diag.push('W=' + (window.innerWidth || 0) + ' H=' + (window.innerHeight || 0));
    // 确保顶栏在视口内
    try { window.scrollTo(0, 0); document.documentElement.scrollTop = 0; document.body.scrollTop = 0; } catch (e) {}
    await sleep(200);

    if (modalOpen()) { diag.push('弹窗已开'); return { ok: true, diag: diag }; }

    const nameEl = findStoreNameEl();
    diag.push('店名=' + (nameEl ? (nameEl.textContent || '').trim() : 'null'));

    // 策略 1：点店名可点祖先 + 右侧箭头
    if (nameEl) {
      const r = nameEl.getBoundingClientRect();
      realClick(clickableAncestor(nameEl));
      await sleep(150);
      const arrow = document.elementFromPoint(
        Math.min((window.innerWidth || 1280) - 3, r.right + 14),
        r.top + r.height / 2,
      );
      if (arrow && arrow !== nameEl) realClick(arrow);
      diag.push('策略1=店名+箭头');
    }

    // 等下拉里出现「切换」
    let sw = await waitFor(function () {
      const cands = textEls(/^切换$/, 6).filter(visible);
      return cands.length ? clickableAncestor(cands[cands.length - 1]) : null;
    }, 2500, 200);

    // 策略 2：读不到店名或没出「切换」→ 点右上角头像区
    if (!sw) {
      const av = [...document.querySelectorAll('img,div,span,button')].find((e) => {
        const r = e.getBoundingClientRect();
        return r.top >= 0 && r.top < 90
          && r.left > (window.innerWidth || 1280) * 0.82
          && r.width >= 18 && r.height >= 18
          && r.width <= 80 && r.height <= 80;
      });
      if (av) {
        realClick(av);
        diag.push('策略2=头像');
      } else {
        clickTopRightHotspot();
        diag.push('策略2=右上热区');
      }
      sw = await waitFor(function () {
        const cands = textEls(/^切换$/, 6).filter(visible);
        return cands.length ? clickableAncestor(cands[cands.length - 1]) : null;
      }, 3000, 200);
    }

    diag.push('下拉切换=' + !!sw);
    if (sw) realClick(sw);

    let ok = !!(await waitFor(function () { return modalOpen() ? true : null; }, 4500, 200));

    // 策略 3：仍未开 → 再扫一次右上 + 放宽「切换」匹配（含「切换店铺」入口）
    if (!ok) {
      clickTopRightHotspot();
      await sleep(400);
      const loose = textEls(/^切换/, 12).filter(visible);
      diag.push('宽松切换候选=' + loose.length);
      if (loose.length) realClick(clickableAncestor(loose[loose.length - 1]));
      ok = !!(await waitFor(function () { return modalOpen() ? true : null; }, 4000, 200));
      diag.push('策略3=' + ok);
    }

    if (!ok) {
      const cands = textEls(/切换/, 10).slice(0, 8).map((e) => {
        const b = e.getBoundingClientRect();
        return (e.tagName + '[' + (e.textContent || '').trim().slice(0, 8)
          + ',y' + Math.round(b.top) + ',v' + (visible(e) ? 1 : 0) + ']');
      });
      diag.push('切换候选=' + (cands.join(' ') || '无'));
      diag.push('模态 切换店铺=' + textEls(/切换店铺/, 20).length
        + ' 账户=' + textEls(/您的账户/, 40).length);
    }
    diag.push('弹窗打开=' + ok);
    return { ok: ok, diag: diag };
  }
`;

/** 滚回顶部，避免顶栏店名因 scroll 出启发式范围 */
async function ensureTop(page) {
  await page.evaluate(() => {
    try {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    } catch {}
  }).catch(() => {});
  await page.waitForTimeout(200).catch(() => {});
}

export async function readCurrentStoreName(page) {
  await ensureTop(page);
  return page.evaluate((helpers) => {
    // eslint-disable-next-line no-eval
    eval(helpers);
    return readStoreName();
  }, SWITCH_HELPERS);
}

/**
 * 切换到目标店铺（会话级）。已是当前店则 ok。
 * @returns {Promise<{ok:boolean,msg:string}>}
 */
export async function switchSessionStore(page, target) {
  await ensureTop(page);
  const cur = await readCurrentStoreName(page);
  if (cur && cur === target) {
    log.info(`已是当前店：${target}`);
    return { ok: true, msg: 'already' };
  }
  log.info(`会话切店 → ${target}（当前=${cur || '未知'}）`);

  // 先清可能挡顶栏的浮层（Esc 一轮，不走完整 closePopups 避免过慢）
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(300).catch(() => {});
  await ensureTop(page);

  // Playwright page.evaluate 只接受 1 个参数，多个值必须包成对象
  const result = await page.evaluate(async ({ helpers, targetName }) => {
    // eslint-disable-next-line no-eval
    eval(helpers);
    const opened = await openStoreModal();
    if (!opened.ok) {
      return { ok: false, msg: '打不开切换店铺弹窗 | ' + (opened.diag || []).join(' ; ') };
    }
    await sleep(400);
    const esc = String(targetName).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // 对齐插件：找含店名且含「切换」的最短节点作行容器
    const rows = textEls(new RegExp(esc), 120).filter((e) => /切换/.test(e.textContent || ''));
    const row = innermost(rows);
    if (!row) {
      return {
        ok: false,
        msg: '弹窗里没找到店铺 ' + targetName + ' | ' + (opened.diag || []).join(' ; '),
      };
    }
    let btn = [...row.querySelectorAll('button,[role=button]')].find(
      (b) => /切换/.test(b.textContent || '') && !b.disabled && b.getAttribute('aria-disabled') !== 'true',
    );
    if (!btn) {
      const allSwitch = textEls(/^切换$/, 6)
        .map(clickableAncestor)
        .filter((b) => b && !b.disabled && visible(b));
      btn =
        allSwitch.find(
          (b) =>
            row.contains(b) ||
            (b.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_CONTAINED_BY),
        ) || allSwitch[allSwitch.length - 1];
    }
    if (!btn) {
      return { ok: false, msg: '没找到可点的切换按钮（可能已是当前店）' };
    }
    realClick(btn);
    return { ok: true, msg: 'clicked', diag: opened.diag };
  }, { helpers: SWITCH_HELPERS, targetName: target });

  if (!result.ok) {
    log.warn(`切店失败：${result.msg}`);
    // 失败时再试一次 Playwright 原生点击顶栏右侧（绕过仅 JS 事件不生效的情况）
    const retry = await tryPlaywrightOpenAndSwitch(page, target);
    if (retry.ok) return retry;
    await page.keyboard.press('Escape').catch(() => {});
    return result;
  }

  // 等顶栏店名变化
  await page.waitForTimeout(2500);
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    await ensureTop(page);
    const name = await readCurrentStoreName(page);
    if (name === target) {
      log.info(`切店成功：${target}`);
      return { ok: true, msg: 'switched' };
    }
    await page.waitForTimeout(800);
  }
  const after = await readCurrentStoreName(page);
  if (after === target) return { ok: true, msg: 'switched-late' };
  // 顶栏读不到名字时：若弹窗已关且点过切换，仍可能已切成功——用「非原店」弱确认不够，报超时
  log.warn(`切店超时，当前显示=${after || '未知'}，目标=${target}`);
  return { ok: false, msg: `timeout current=${after}` };
}

/**
 * 兜底：用 Playwright 真实鼠标点顶栏右侧，再在弹窗里点目标店。
 * 解决部分环境 dispatchEvent 点不动、但真实 click 可以的情况。
 */
async function tryPlaywrightOpenAndSwitch(page, target) {
  try {
    log.info(`切店兜底：Playwright 真实点击顶栏 → ${target}`);
    await ensureTop(page);
    const vp = page.viewportSize() || { width: 1280, height: 800 };
    // 点顶栏右侧几个位置唤出菜单
    const points = [
      { x: vp.width - 40, y: 32 },
      { x: vp.width - 80, y: 32 },
      { x: vp.width - 120, y: 36 },
      { x: vp.width - 160, y: 36 },
    ];
    for (const p of points) {
      await page.mouse.click(p.x, p.y).catch(() => {});
      await page.waitForTimeout(400);
      const sw = page.getByText(/^切换$/).last();
      if (await sw.isVisible({ timeout: 600 }).catch(() => false)) {
        await sw.click({ timeout: 2000 }).catch(() => {});
        break;
      }
    }
    // 等弹窗
    const modal = page.getByText(/切换店铺|您的账户存在/).first();
    const opened = await modal.isVisible({ timeout: 5000 }).catch(() => false);
    if (!opened) {
      log.warn('切店兜底：弹窗仍未出现');
      return { ok: false, msg: '兜底也打不开弹窗' };
    }
    // 在含目标店名的行里点「切换」
    const row = page.locator('div,li,tr').filter({ hasText: target }).filter({ hasText: /切换/ }).first();
    if (await row.isVisible({ timeout: 3000 }).catch(() => false)) {
      const btn = row.getByText(/^切换$/).last();
      if (await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await btn.click({ timeout: 2000 });
      } else {
        await row.click({ timeout: 2000 });
      }
    } else {
      // 直接点文本
      const t = page.getByText(target, { exact: true }).first();
      if (await t.isVisible({ timeout: 2000 }).catch(() => false)) {
        await t.click({ timeout: 2000 }).catch(() => {});
      }
      const sw2 = page.getByText(/^切换$/).last();
      await sw2.click({ timeout: 2000 }).catch(() => {});
    }
    await page.waitForTimeout(2500);
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      await ensureTop(page);
      const name = await readCurrentStoreName(page);
      if (name === target) {
        log.info(`切店成功（兜底）：${target}`);
        return { ok: true, msg: 'switched-pw' };
      }
      await page.waitForTimeout(800);
    }
    const after = await readCurrentStoreName(page);
    if (after === target) return { ok: true, msg: 'switched-pw-late' };
    log.warn(`切店兜底超时，当前=${after || '未知'}`);
    return { ok: false, msg: `兜底 timeout current=${after}` };
  } catch (e) {
    log.warn(`切店兜底异常：${e.message || e}`);
    return { ok: false, msg: `兜底异常 ${e.message || e}` };
  }
}
