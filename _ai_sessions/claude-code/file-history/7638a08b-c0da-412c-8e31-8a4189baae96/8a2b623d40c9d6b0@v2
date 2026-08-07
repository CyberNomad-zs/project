/**
 * Service Worker：消息路由、飞书写入、定时抓取
 */

import { ALARM_NAME, MSG } from '../lib/constants.js';
import {
  getConfig,
  saveConfig,
  getLogs,
  clearLogs,
  getLastResult,
  saveLastResult
} from '../lib/storage.js';
import { log } from '../lib/logger.js';
import {
  normalizeRow,
  filterValidRows,
  resolveBizDate,
  mapStoreName
} from '../scraper/normalize.js';
import { writeRecords, testFeishuConnection } from '../feishu/bitable.js';

const TIKTOK_URL_RE = /tiktok\.com|tiktokglobalshop\.com/i;

// —— 启动：恢复定时 ——
chrome.runtime.onInstalled.addListener(async () => {
  await syncAlarmFromConfig();
  await log('info', '插件已安装/更新');
});

chrome.runtime.onStartup.addListener(async () => {
  await syncAlarmFromConfig();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  await log('info', '定时任务触发，开始抓取');
  try {
    const result = await runFullScrape({ reason: 'schedule' });
    await notify(
      result.ok ? '定时抓取完成' : '定时抓取失败',
      result.ok
        ? `共 ${result.rows?.length || 0} 条，写入 ${result.write?.written ?? 0}`
        : result.error || '未知错误'
    );
  } catch (e) {
    await log('error', '定时抓取异常', { error: String(e.message || e) });
    await notify('定时抓取异常', String(e.message || e));
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender)
    .then(sendResponse)
    .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
  return true;
});

async function handleMessage(msg) {
  if (!msg?.type) return { ok: false, error: 'invalid message' };

  switch (msg.type) {
    case MSG.GET_CONFIG:
      return { ok: true, config: await getConfig() };

    case MSG.SAVE_CONFIG: {
      const config = await saveConfig(msg.config || {});
      await syncAlarmFromConfig();
      return { ok: true, config };
    }

    case MSG.GET_LOGS:
      return { ok: true, logs: await getLogs() };

    case MSG.CLEAR_LOGS:
      await clearLogs();
      return { ok: true };

    case MSG.GET_LAST_RESULT:
      return { ok: true, result: await getLastResult() };

    case MSG.TEST_FEISHU:
      try {
        const r = await testFeishuConnection();
        await log('success', '飞书连通性测试成功', r);
        return { ok: true, ...r };
      } catch (e) {
        await log('error', '飞书连通性测试失败', { error: String(e.message || e) });
        return { ok: false, error: String(e.message || e) };
      }

    case MSG.RUN_FULL:
      return runFullScrape({
        reason: msg.reason || 'manual',
        tabId: msg.tabId,
        dryRun: msg.dryRun
      });

    case MSG.WRITE_FEISHU:
      return writeOnly(msg.rows || [], { dryRun: msg.dryRun });

    default:
      return { ok: false, error: `unknown type: ${msg.type}` };
  }
}

/**
 * 完整流程：找 tab → 抓取 → 归一化 → 写飞书
 */
async function runFullScrape({ reason = 'manual', tabId, dryRun } = {}) {
  const config = await getConfig();
  const useDryRun = dryRun != null ? dryRun : config.dryRun;

  let tab;
  try {
    tab = tabId
      ? await chrome.tabs.get(tabId)
      : await findBestTikTokTab();
  } catch {
    tab = null;
  }

  if (!tab?.id) {
    const error =
      '未找到已打开的 TikTok 广告/卖家页面。请在紫鸟店铺窗口中打开广告数据列表后再试。';
    await log('error', error, { reason });
    const result = { ok: false, error, reason };
    await saveLastResult(result);
    return result;
  }

  // 确保 content script 可用；抓取前在页面上切到 dateMode（默认昨天，避免默认近 7 天）
  // 业务日按英区后台时区 Europe/London，勿用中国本地日历
  const scrapeOptions = {
    waitMs: 10000,
    dateMode: config.dateMode || 'yesterday',
    setPageDateRange: config.setPageDateRange !== false,
    waitAfterDateChangeMs: config.waitAfterDateChangeMs ?? 5000,
    bizTimeZone: config.bizTimeZone || 'Europe/London',
    minUkHourForToday: config.minUkHourForToday ?? 20
  };
  let scrape;
  try {
    scrape = await sendToTab(tab.id, { type: 'SCRAPE_PAGE', options: scrapeOptions });
  } catch (e) {
    // 尝试动态注入
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content/content.js']
      });
      await sleep(300);
      scrape = await sendToTab(tab.id, { type: 'SCRAPE_PAGE', options: scrapeOptions });
    } catch (e2) {
      const error = `无法与页面通信: ${e2.message || e.message || e}`;
      await log('error', error, { reason, url: tab.url });
      const result = { ok: false, error, reason, url: tab.url };
      await saveLastResult(result);
      return result;
    }
  }

  if (!scrape?.ok) {
    const error = scrape?.error || '抓取失败';
    await log('error', error, { reason, url: tab.url, source: scrape?.source });
    const result = {
      ok: false,
      error,
      reason,
      url: tab.url,
      scrape
    };
    await saveLastResult(result);
    return result;
  }

  // 与 scrapeOptions 一致：today 过早时按英国时强制 yesterday
  let bizMode = config.dateMode || 'yesterday';
  const bizTz = config.bizTimeZone || 'Europe/London';
  const minUkHour = config.minUkHourForToday ?? 20;
  if (String(bizMode).toLowerCase() === 'today') {
    try {
      const ukHour = Number(
        new Intl.DateTimeFormat('en-GB', {
          timeZone: bizTz,
          hour: 'numeric',
          hour12: false
        }).format(new Date())
      );
      if (Number.isFinite(ukHour) && ukHour < minUkHour) {
        await log('warn', `dateMode=today 但英国时 ${ukHour}:00 < ${minUkHour}:00，改抓昨天`, {
          reason
        });
        bizMode = 'yesterday';
      }
    } catch {
      /* ignore */
    }
  }
  const date = resolveBizDate(bizMode, config.customDate, bizTz);
  const storeName = mapStoreName(
    scrape.storeName,
    config.storeMappings,
    config.defaultStoreName
  );

  const ctx = {
    date,
    storeName,
    storeId: '',
    // 与 TikTok 广告后台一致：广告花费 / 销售额按美金
    currency: scrape.currency || 'USD',
    sourceUrl: scrape.url || tab.url,
    scrapedAt: scrape.scrapedAt || new Date().toISOString()
  };

  const rows = filterValidRows(
    (scrape.rawRows || []).map((r) => normalizeRow(r, ctx))
  );

  if (!rows.length) {
    const error = '抓取到数据但归一化后为空（可能是汇总行或字段未识别）';
    await log('warn', error, { reason, rawCount: scrape.rawRows?.length });
    const result = { ok: false, error, reason, scrape, rows: [] };
    await saveLastResult(result);
    return result;
  }

  let write;
  try {
    write = await writeRecords(rows, { dryRun: useDryRun });
    await log('success', useDryRun ? '干跑抓取成功' : '抓取并写入成功', {
      reason,
      count: rows.length,
      written: write.written,
      dryRun: write.dryRun,
      store: storeName,
      source: scrape.source
    });
  } catch (e) {
    const error = String(e.message || e);
    await log('error', `写入飞书失败: ${error}`, { reason, count: rows.length });
    const result = {
      ok: false,
      error,
      reason,
      rows,
      scrape,
      storeName,
      date
    };
    await saveLastResult(result);
    return result;
  }

  const result = {
    ok: true,
    reason,
    rows,
    write,
    storeName,
    date,
    source: scrape.source,
    url: scrape.url || tab.url,
    dryRun: useDryRun
  };
  await saveLastResult(result);
  return result;
}

async function writeOnly(rows, { dryRun } = {}) {
  try {
    const write = await writeRecords(rows, { dryRun });
    await log('success', dryRun ? '干跑预览写入跳过' : '手动写入成功', {
      written: write.written,
      count: rows.length
    });
    return { ok: true, write };
  } catch (e) {
    await log('error', `写入失败: ${e.message || e}`);
    return { ok: false, error: String(e.message || e) };
  }
}

async function findBestTikTokTab() {
  const tabs = await chrome.tabs.query({});
  const matched = tabs.filter((t) => t.url && TIKTOK_URL_RE.test(t.url));
  if (!matched.length) return null;
  // 优先当前窗口 active
  matched.sort((a, b) => {
    if (a.active && !b.active) return -1;
    if (!a.active && b.active) return 1;
    return (b.lastAccessed || 0) - (a.lastAccessed || 0);
  });
  // 优先 ads / seller / campaign 路径
  const scored = matched.map((t) => {
    let s = 0;
    const u = t.url.toLowerCase();
    if (u.includes('ads')) s += 3;
    if (u.includes('seller')) s += 2;
    if (u.includes('campaign') || u.includes('shop-ads') || u.includes('gmv')) s += 4;
    if (t.active) s += 1;
    return { t, s };
  });
  scored.sort((a, b) => b.s - a.s);
  return scored[0].t;
}

function sendToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(response);
    });
  });
}

async function syncAlarmFromConfig() {
  const config = await getConfig();
  await chrome.alarms.clear(ALARM_NAME);
  if (!config.schedule?.enabled) {
    await log('info', '定时任务已关闭');
    return;
  }
  // 默认 17:20（中国时）；勿用早上 7:30——那时英国日刚开始，花费是半截
  const hour = Number(config.schedule.hour);
  const minute = Number(config.schedule.minute);
  const h = Number.isFinite(hour) ? hour : 17;
  const m = Number.isFinite(minute) ? minute : 20;
  // when: 下一次该时刻；periodInMinutes: 每天
  const when = nextAlarmTime(h, m);
  await chrome.alarms.create(ALARM_NAME, {
    when,
    periodInMinutes: 24 * 60
  });
  await log('info', `定时任务已设置: 每天 ${pad(h)}:${pad(m)}`, {
    when: new Date(when).toISOString()
  });
}

function nextAlarmTime(hour, minute) {
  const now = new Date();
  const next = new Date();
  next.setHours(hour, minute, 0, 0);
  if (next.getTime() <= now.getTime()) {
    next.setDate(next.getDate() + 1);
  }
  return next.getTime();
}

function pad(n) {
  return String(n).padStart(2, '0');
}

async function notify(title, message) {
  try {
    if (!chrome.notifications?.create) return;
    await chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title,
      message: String(message).slice(0, 200)
    });
  } catch {
    /* 部分环境无 notifications 权限也可忽略 */
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
