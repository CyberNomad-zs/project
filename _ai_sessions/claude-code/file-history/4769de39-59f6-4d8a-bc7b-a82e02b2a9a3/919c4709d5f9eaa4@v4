/**
 * 入口分流（2026-07-30 起默认隔离）：
 *  - 本机默认：仅浏览器流量（待关注 / 近期下降 / 在售数字）
 *  - 赛狐上下架：独立 `npm run sellfox:*`，部署在固定 IP 服务器
 *  - 联调全量：config.fullRun=true 或 FULL_RUN=1（动态加载 fullRun，本机包可不带 sellfox）
 */
import { launchBrowser, isLoggedIn, peekSession, SESSION_KICKED_HINT } from './browser.js';
import { scanStore, attachCountStatusCapture } from './monitor.js';
import { closePopups } from './popups.js';
import { loadState, saveState, diffStore, mergeSnapshot } from './state.js';
import { sendFeishu } from './feishu.js';
import { switchSessionStore, readCurrentStoreName } from './sessionStores.js';
import { log } from './logger.js';

/** Playwright：整页/上下文/浏览器被关掉（进程没了），不是「未登录」。 */
function isBrowserGoneError(e) {
  const m = String(e?.message || e || '');
  return /has been closed|Target closed|Browser closed|context or browser/i.test(m);
}

/** 扫店出错后区分：进程没了 vs 会话被踢到登录页 */
async function explainStoreFailure(page, label, e) {
  log.error(`店铺「${label}」监测出错：`, e.message);
  if (isBrowserGoneError(e)) {
    log.error(
      '【诊断=浏览器进程已退出】监测用的 Chrome 没了（不是网页掉线）。常见：' +
        '①又开了 once/常驻/守护或工具「登录」抢 .userdata；' +
        '②任务管理器/清理软件结束了 chrome.exe（监测也走系统 Chrome）；' +
        '③休眠。日常 Chrome 只开 Temu 网页通常不会直接关掉监测进程。' +
        '本轮其余店跳过，下一轮会重新拉起浏览器。',
    );
    return 'browser_gone';
  }
  const peek = await peekSession(page);
  if (peek.kind === 'browser_gone') {
    log.error(`【诊断=浏览器进程已退出】peek：${peek.detail || ''}`);
    return 'browser_gone';
  }
  if (peek.kind === 'session_kicked') {
    log.error(
      `【诊断=会话失效/疑似被踢】url=${peek.url || '?'} (${peek.detail || ''})。` +
        '浏览器还在，但已回到登录页——更像登录过期，或同账号在日常 Chrome 登录后服务端踢了监测会话。',
    );
    log.error(SESSION_KICKED_HINT);
    return 'session_kicked';
  }
  return 'other';
}

export async function runOnce(cfg) {
  // fullRun 已在 loadConfig 里综合 env；再挡一层显式 FULL_RUN=0
  const forceOff = process.env.FULL_RUN === '0' || process.env.FULL_RUN === 'false';
  const useFull = !forceOff && cfg.fullRun === true;

  if (useFull) {
    log.info('全量监测（赛狐上下架 + 浏览器流量）— 需本机 IP 在赛狐白名单');
    // 动态加载：同事本机包可不带 src/sellfox，默认流量路径不依赖它
    try {
      const { runFullOnce } = await import('./fullRun.js');
      return runFullOnce(cfg);
    } catch (e) {
      log.error('全量模块加载失败（本机流量包可能未含赛狐代码）：', e.message);
      log.warn('回退为仅浏览器流量监测');
      return runBrowserOnly(cfg);
    }
  }

  log.info('仅浏览器流量监测（赛狐上下架请用服务器 temu-sellfox）');
  return runBrowserOnly(cfg);
}

/**
 * 仅浏览器流量/在售：多店走会话级切店（头像→切换店铺），
 * 不再用「来源店铺」筛选（那只是商品来源过滤，切不了会话）。
 */
export async function runBrowserOnly(cfg) {
  const { context, page } = await launchBrowser(cfg);
  // 整轮尽早挂：登录 goto / 切店触发的 countStatus 都能接到
  const countCapture = attachCountStatusCapture(page);
  try {
    if (!(await isLoggedIn(page, cfg))) {
      const err = new Error(
        '未登录。请先停常驻，再运行 `npm run login`（或启动器「登录 Temu」）。' +
          '若刚在日常 Chrome 登录过同一账号，也可能是服务端踢了监测会话。',
      );
      err.code = 'NOT_LOGGED_IN';
      throw err;
    }
    // 切店依赖商品列表顶栏店名/头像；isLoggedIn 已 goto 过，再等渲染
    await page.waitForTimeout(1500);
    await closePopups(page);

    let stores = Array.isArray(cfg.storeList)
      ? cfg.storeList.map(String).filter(Boolean)
      : [];
    if (!stores.length) {
      const cur = await readCurrentStoreName(page);
      stores = [cur || '(当前店铺)'];
      log.info('未配置 storeList，监测当前店：', stores[0]);
    } else if (stores.length === 1) {
      log.info('单店监测：', stores[0]);
    } else {
      log.info('多店会话轮巡：', stores.join(', '));
    }

    const state = loadState();
    state.stores = state.stores || {};
    const allEvents = [];
    const summaries = [];

    for (const store of stores) {
      const label = store || '(当前店铺)';
      try {
        // 切店前打点：只采纳本店开始后的 countStatus，避免串店
        const captureMark = Date.now();
        if (stores.length > 1 && store && store !== '(当前店铺)') {
          const sw = await switchSessionStore(page, store);
          if (!sw.ok) {
            // 首店切失败时仍尝试扫当前页（可能本来就在该店，只是顶栏名读不到）
            const isFirst = stores.indexOf(store) === 0;
            if (isFirst) {
              log.warn(`切到「${store}」失败（${sw.msg}），首店仍尝试扫描当前页`);
            } else {
              log.warn(`切到「${store}」失败（${sw.msg}），跳过`);
              continue;
            }
          }
          await closePopups(page);
          await page.waitForTimeout(1000);
        }
        const prev = state.stores[label];
        const result = await scanStore(page, label, cfg, {
          prevWatch: prev?.trafficWatchCount,
          countCapture,
          captureMark,
        });
        log.info('扫描结果：', {
          store: result.store,
          onSale: result.onSaleCount,
          watch: result.trafficWatchCount,
          decline: result.trafficDeclineCount,
          watchItems: (result.watchItems || []).length,
          declineItems: (result.declineItems || []).length,
        });
        summaries.push(result);
        const events = diffStore(prev, result, cfg.alerts, {
          editBaseUrl:
            cfg.goodsListUrl?.replace(/\/goods\/list.*/, '') ||
            'https://agentseller.temu.com',
        });
        for (const ev of events) allEvents.push({ store: label, ...ev });
        state.stores[label] = mergeSnapshot(prev, result);
      } catch (e) {
        const kind = await explainStoreFailure(page, label, e);
        if (kind === 'browser_gone' || kind === 'session_kicked') {
          break; // 进程没了或已回登录页，继续切店无意义
        }
      }
    }

    saveState(state);

    if (allEvents.length > 0) {
      const lines = [];
      const byStore = {};
      for (const ev of allEvents) (byStore[ev.store] ||= []).push(ev);
      for (const [store, evs] of Object.entries(byStore)) {
        lines.push(`**🏬 ${store}**`);
        for (const ev of evs) {
          const icon =
            ev.type === 'onSaleDrop' ? '📉' : ev.type === 'trafficDecline' ? '🔴' : '⚠️';
          lines.push(`${icon} ${ev.text}`);
        }
        lines.push('');
      }
      lines.push(`_扫描时间：${new Date().toLocaleString('zh-CN')}_`);
      await sendFeishu(cfg, {
        title: '🔔 Temu 店铺监测告警',
        template: 'red',
        lines,
      });
    } else {
      log.info('本轮无异常，未发送告警。');
    }

    return { summaries, events: allEvents };
  } finally {
    countCapture.dispose();
    await context.close().catch(() => {});
  }
}
