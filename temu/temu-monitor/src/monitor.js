/**
 * 单店完整扫描（对齐插件能力，在 Playwright 页内执行）
 *  - onSaleCount：countStatus 接口 / tab
 *  - trafficWatchCount + watchItems：chip + 可选主动筛选扫明细
 *  - trafficDeclineCount + declineItems：行内徽标
 */
import { log } from './logger.js';
import { closePopups } from './popups.js';
import { readPassiveTraffic, scanWatchList, waitForGrid } from './domScan.js';

const COUNT_STATUS_RE = /visage-agent-seller\/product\/skc\/countStatus/;

/**
 * 页面级持续捕获 countStatus（切店/SPA 刷新时接口常在 scan 挂 waitForResponse 之前就发出）。
 * 在整轮多店循环外 attach 一次，每店用 captureMark 只采纳「这店开始之后」的包。
 * @param {import('playwright').Page} page
 */
export function attachCountStatusCapture(page) {
  const state = { json: null, at: 0 };
  const handler = (response) => {
    try {
      if (response.request().method() !== 'POST') return;
      if (!COUNT_STATUS_RE.test(response.url())) return;
    } catch {
      return;
    }
    response
      .json()
      .then((json) => {
        state.json = json;
        state.at = Date.now();
      })
      .catch(() => {});
  };
  page.on('response', handler);
  return {
    state,
    dispose() {
      page.off('response', handler);
    },
    /** 等到 at > sinceTs 的新包；超时返回 null（不回落旧包，避免串店） */
    async waitFresh(sinceTs, timeoutMs = 20000) {
      const t0 = Date.now();
      while (Date.now() - t0 < timeoutMs) {
        if (state.at > sinceTs && state.json) return state.json;
        await page.waitForTimeout(200);
      }
      return state.at > sinceTs && state.json ? state.json : null;
    },
  };
}

/**
 * @param {import('playwright').Page} page
 * @param {string} storeName
 * @param {object} cfg
 * @param {{
 *   forceWatchScan?: boolean,
 *   prevWatch?: number|null,
 *   countCapture?: ReturnType<typeof attachCountStatusCapture>,
 *   captureMark?: number,
 * }} [opts]
 */
export async function scanStore(page, storeName, cfg, opts = {}) {
  const ownCapture = opts.countCapture || attachCountStatusCapture(page);
  const disposeOwn = !opts.countCapture;
  try {
    const mark = typeof opts.captureMark === 'number' ? opts.captureMark : Date.now();
    let statusJson =
      ownCapture.state.at > mark && ownCapture.state.json ? ownCapture.state.json : null;

    // 切店过程常已打过 countStatus → 直接用，免再 reload
    // 否则：同 URL goto 经常不重发，已在列表页就 reload 强制拉一次
    if (!statusJson) {
      statusJson = await triggerCountStatus(page, cfg, ownCapture);
    }

    await closePopups(page);
    await waitForGrid(page);
    await page.waitForTimeout(1500);

    // 关弹窗/等网格期间迟到的包
    if (!statusJson && ownCapture.state.at > mark) {
      statusJson = ownCapture.state.json;
    }

    let onSaleCount = readOnSaleFromStatus(statusJson);
    if (onSaleCount != null) {
      log.info(`[${storeName}] 在售读自 countStatus：${onSaleCount}`);
    } else {
      onSaleCount = await readOnSaleCount(page);
      log.warn(`[${storeName}] countStatus 回落 tab：${onSaleCount}`);
    }

    // 被动读 chip + 徽标 + 当前页明细
    let passive = await readPassiveTraffic(page);
    if (!passive.gridReady) {
      await waitForGrid(page);
      await page.waitForTimeout(1200);
      passive = await readPassiveTraffic(page);
    }

    let trafficWatchCount = passive.trafficWatch;
    let watchItems = passive.watchItems || [];
    let trafficDeclineCount =
      typeof passive.trafficDecline === 'number' ? passive.trafficDecline : null;
    let declineItems = passive.declineItems || [];

    if (trafficWatchCount == null) {
      const legacy = await readTrafficByClickFilter(page);
      if (legacy != null) trafficWatchCount = legacy;
    }

    const prevWatch = opts.prevWatch;
    const watchIncreased =
      typeof prevWatch === 'number' &&
      typeof trafficWatchCount === 'number' &&
      trafficWatchCount > prevWatch;
    const needWatchScan =
      opts.forceWatchScan ||
      watchIncreased ||
      (typeof trafficWatchCount === 'number' &&
        trafficWatchCount > 0 &&
        watchItems.length === 0);

    if (needWatchScan && trafficWatchCount !== 0) {
      log.info(`[${storeName}] 主动扫待关注明细…`);
      const scan = await scanWatchList(page);
      if (scan.applied && Array.isArray(scan.items) && scan.items.length) {
        watchItems = scan.items;
        if (typeof scan.total === 'number') trafficWatchCount = scan.total;
      }
    }

    const declineBtn = page.getByText('批量处理流量下降商品', { exact: false }).first();
    const declineBtnVisible = await declineBtn.isVisible({ timeout: 1000 }).catch(() => false);
    const trafficDeclineExists =
      (typeof trafficDeclineCount === 'number' && trafficDeclineCount > 0) || declineBtnVisible;

    const trafficAnomalyTotal =
      (typeof trafficWatchCount === 'number' ? trafficWatchCount : 0) +
      (typeof trafficDeclineCount === 'number' ? trafficDeclineCount : 0);

    return {
      store: storeName,
      onSaleCount,
      trafficWatchCount,
      trafficDeclineCount,
      trafficDeclineExists,
      trafficAnomalyTotal,
      watchItems,
      declineItems,
    };
  } finally {
    if (disposeOwn) ownCapture.dispose();
  }
}

/** 触发并等待一次新的 countStatus；同址优先 reload（goto 常不重发） */
async function triggerCountStatus(page, cfg, capture) {
  const before = capture.state.at;
  const onList = /\/goods\/list/i.test(page.url() || '');
  if (onList) {
    await page.reload({ waitUntil: 'commit' }).catch(async () => {
      await page.goto(cfg.goodsListUrl, { waitUntil: 'commit' }).catch(() => {});
    });
  } else {
    await page.goto(cfg.goodsListUrl, { waitUntil: 'commit' }).catch(() => {});
  }
  let json = await capture.waitFresh(before, 20000);
  if (json) return json;

  // 再强制 reload 一次（网关重置/SPA 吞请求时）
  const before2 = capture.state.at;
  await page.reload({ waitUntil: 'commit' }).catch(() => {});
  json = await capture.waitFresh(before2, 15000);
  return json;
}

function readOnSaleFromStatus(json) {
  const list = json?.result?.skcTopStatusCountList;
  if (!Array.isArray(list)) return null;
  const onSale = list.find((s) => s && s.skcTopStatus === 100);
  return onSale && typeof onSale.skcTotal === 'number' ? onSale.skcTotal : null;
}

async function readOnSaleCount(page) {
  const tabs = page.locator('[data-testid="beast-core-tab-itemLabel"]');
  const n = await tabs.count().catch(() => 0);
  for (let i = 0; i < n; i++) {
    const t = (await tabs.nth(i).innerText().catch(() => '')).trim();
    const m = t.match(/在售中\s*([\d,]+)/);
    if (m) return Number(m[1].replace(/,/g, ''));
  }
  const loc = page.getByText(/在售中\s*[\d,]+/).first();
  const txt = await loc.innerText({ timeout: 2000 }).catch(() => '');
  const m = txt.match(/在售中\s*([\d,]+)/);
  return m ? Number(m[1].replace(/,/g, '')) : null;
}

/** 旧路径：点 chip 读共有 N 条（chip 无 countDistance 时） */
async function readTrafficByClickFilter(page) {
  const chip = page.getByText('商品流量待关注', { exact: false }).first();
  if (!(await chip.isVisible({ timeout: 1500 }).catch(() => false))) return null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const before = await readTotal(page);
    await chip.click({ timeout: 3000 }).catch(() => {});
    await page
      .waitForFunction(
        (prev) => {
          const e = [...document.querySelectorAll('*')].find(
            (x) => x.children.length === 0 && /共有\s*[\d,]+\s*条/.test(x.textContent || ''),
          );
          if (!e) return false;
          const m = e.textContent.match(/共有\s*([\d,]+)\s*条/);
          return m && Number(m[1].replace(/,/g, '')) !== prev;
        },
        before,
        { timeout: 8000 },
      )
      .catch(() => {});
    const after = await readTotal(page);
    if (after != null && before != null && after !== before && after < before) {
      await clickReset(page);
      await page.waitForTimeout(1500);
      return after;
    }
    log.warn(`待关注筛选第 ${attempt}/3 次未生效 before=${before} after=${after}`);
    await clickReset(page);
    await page.waitForTimeout(1500);
  }
  return null;
}

async function readTotal(page) {
  const txt = await page.evaluate(() => {
    const e = [...document.querySelectorAll('*')].find(
      (x) => x.children.length === 0 && /共有\s*[\d,]+\s*条/.test(x.textContent || ''),
    );
    return e ? e.textContent.trim() : '';
  });
  const m = txt.match(/共有\s*([\d,]+)\s*条/);
  return m ? Number(m[1].replace(/,/g, '')) : null;
}

async function clickReset(page) {
  const reset = page.getByText(/^重置$/).first();
  if (await reset.isVisible({ timeout: 1000 }).catch(() => false)) {
    await reset.click({ timeout: 2000 }).catch(() => {});
  }
}
