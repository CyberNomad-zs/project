/**
 * 赛狐 Temu 下架监测一轮
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname } from 'node:path';
import { createSellfoxClient } from './client.js';
import { fetchAllCrossParents, groupByShop, SELECT_STATUS } from './products.js';
import { diffOnSale, formatChangeLines, alertTemplate, alertTitle } from './diff.js';
import { shopNameMap } from './config.js';
import { sendFeishu } from '../feishu.js';
import { log } from '../logger.js';

function loadState(path) {
  try {
    if (!existsSync(path)) return { stores: {} };
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return { stores: {} };
  }
}

function saveState(path, state) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(state, null, 2), 'utf8');
}

/**
 * @param {object} cfg loadSellfoxConfig()
 * @param {{ dryRun?: boolean }} [opts]
 */
export async function runSellfoxOnce(cfg, opts = {}) {
  const shops = (cfg.stores || []).filter((s) => s.enabled !== false && s.shopId);
  if (!cfg.clientId || !cfg.clientSecret) throw new Error('缺少 clientId/clientSecret');
  if (!shops.length) throw new Error('没有店铺');

  const client = createSellfoxClient({
    baseUrl: cfg.baseUrl,
    clientId: cfg.clientId,
    clientSecret: cfg.clientSecret,
    debug: cfg.debug,
  });

  const shopIds = shops.map((s) => s.shopId);
  const names = shopNameMap(cfg);

  log.info(`Sellfox 拉取 Temu 跨境父体：shops=${shopIds.join(',')} dateType=${cfg.dateType} lookback=${cfg.lookbackDays}d`);
  const { items, meta } = await fetchAllCrossParents(client, {
    shopIds,
    pageSize: cfg.pageSize,
    maxPagesPerWindow: cfg.maxPagesPerWindow,
    dateType: cfg.dateType,
    lookbackDays: cfg.lookbackDays,
  });
  log.info(`拉取完成 unique=${meta.unique} windows=${meta.windows}`);

  const grouped = groupByShop(items, names);
  const state = loadState(cfg.stateFile);
  if (!state.stores) state.stores = {};
  const prevPullUnique =
    typeof state.meta?.pullUnique === 'number' ? state.meta.pullUnique : null;

  const summary = [];
  let anySkip = false;

  for (const shop of shops) {
    const sid = shop.shopId;
    const name = names[sid] || shop.name || sid;
    const g = grouped[sid] || {
      shopId: sid,
      shopName: name,
      onSaleMap: {},
      allMap: {},
      statusCounts: {},
    };
    const onSaleN = Object.keys(g.onSaleMap).length;
    const allN = Object.keys(g.allMap || {}).length;
    log.info(
      `${name}(${sid}) 在售(12)=${onSaleN} 全量=${allN} 状态分布=${JSON.stringify(g.statusCounts || {})}`,
    );

    const prev = state.stores[sid]?.snapshot || null;
    const {
      events,
      nextSnap,
      isFirst,
      skipUpdate,
      ghostCount,
      pendingOnshelfCount,
    } = diffOnSale(prev, {
      onSaleMap: g.onSaleMap,
      allMap: g.allMap || {},
      statusCounts: g.statusCounts,
      pullUnique: meta.unique,
      prevPullUnique,
    });

    for (const ev of events) {
      if (ev.severity === 'warn') log.warn(`${name} ${ev.message || ev.type}`);
      else if (ev.type === 'onshelf_pending') log.info(`${name} ${ev.message || ev.type}`);
    }

    if (isFirst) {
      log.info(`${name} 首轮：建立在售基准 ${onSaleN}（全量 ${allN}），不告警`);
    } else if (skipUpdate) {
      anySkip = true;
      log.warn(`${name} 跳过上下架更新（扫描疑似不全${ghostCount ? ` ghost=${ghostCount}` : ''}）`);
    }

    // 按配置过滤：delist / onshelf 可分别关闭（默认都开）
    const alertEvents = events.filter((e) => {
      if (e.severity !== 'alert') return false;
      if (e.type === 'delist') return cfg.alerts?.delist !== false;
      if (e.type === 'onshelf') return cfg.alerts?.onshelf !== false;
      return false;
    });

    if (alertEvents.length && !opts.dryRun) {
      const lines = formatChangeLines(name, alertEvents, { editBaseUrl: cfg.editBaseUrl });
      await sendFeishu(
        { feishuWebhooks: cfg.feishuWebhooks, feishuSecret: cfg.feishuSecret },
        {
          title: alertTitle(alertEvents),
          template: alertTemplate(alertEvents),
          lines,
        },
      );
      const nDelist = alertEvents
        .filter((e) => e.type === 'delist')
        .reduce((n, e) => n + (e.items?.length || 0), 0);
      const nShelf = alertEvents
        .filter((e) => e.type === 'onshelf')
        .reduce((n, e) => n + (e.items?.length || 0), 0);
      const parts = [];
      if (nDelist) parts.push(`下架 ${nDelist}`);
      if (nShelf) parts.push(`上架 ${nShelf}`);
      log.info(`${name} 已告警${parts.join('、')} 个`);
    } else if (alertEvents.length && opts.dryRun) {
      log.info(
        `${name} dryRun:`,
        formatChangeLines(name, alertEvents, { editBaseUrl: cfg.editBaseUrl }),
      );
    } else if (!isFirst && !skipUpdate) {
      const pendN = pendingOnshelfCount || 0;
      log.info(
        `${name} 本轮无上下架告警` +
          (pendN ? `（待确认上架 ${pendN}）` : '') +
          ` 确认在售=${nextSnap.onSaleCount}`,
      );
    }

    state.stores[sid] = {
      name,
      latest: {
        onSaleCount: nextSnap.onSaleCount,
        allCount: nextSnap.allCount,
        pendingOnshelfCount: Object.keys(nextSnap.pendingOnshelf || {}).length,
        statusCounts: g.statusCounts,
        ts: Date.now(),
      },
      snapshot: nextSnap,
    };
    summary.push({
      shopId: sid,
      store: name,
      onSale: nextSnap.onSaleCount,
      allCount: nextSnap.allCount,
      pendingOnshelf: Object.keys(nextSnap.pendingOnshelf || {}).length,
      statusCounts: g.statusCounts,
      events: events.map((e) => e.type),
      isFirst,
      skipUpdate,
      ghostCount,
    });
  }

  // 配置了但本轮 API 完全没返回的店也建空基准提示
  for (const shop of shops) {
    if (!summary.find((s) => s.shopId === shop.shopId)) {
      summary.push({ shopId: shop.shopId, store: shop.name, onSale: 0, note: '无数据' });
    }
  }

  // 只有本轮看起来完整时才刷新全局 unique，避免用残缺值当下一轮护栏基准
  if (!opts.dryRun) {
    if (!anySkip) {
      state.meta = {
        ...(state.meta || {}),
        pullUnique: meta.unique,
        pullTs: Date.now(),
        range: meta.range,
      };
    } else {
      log.warn(
        `本轮存在 skipUpdate，保留上轮 pullUnique=${prevPullUnique ?? '无'}（本轮 unique=${meta.unique} 不写入）`,
      );
    }
    saveState(cfg.stateFile, state);
  }
  return { meta, summary, onSaleStatus: SELECT_STATUS.ON_SALE };
}

/** 只读探测：拉一窗并打印分布 */
export async function probeSellfox(cfg) {
  const client = createSellfoxClient({
    baseUrl: cfg.baseUrl,
    clientId: cfg.clientId,
    clientSecret: cfg.clientSecret,
    debug: cfg.debug,
  });
  const shops = (cfg.stores || []).filter((s) => s.enabled !== false && s.shopId);
  const shopIds = shops.map((s) => s.shopId);
  const { items, meta } = await fetchAllCrossParents(client, {
    shopIds,
    pageSize: cfg.pageSize,
    maxPagesPerWindow: cfg.maxPagesPerWindow,
    dateType: cfg.dateType,
    lookbackDays: Math.min(cfg.lookbackDays || 30, 30),
  });
  const grouped = groupByShop(items, shopNameMap(cfg));
  const byStatus = {};
  for (const it of items) {
    const st = it.selectStatus || '<empty>';
    byStatus[st] = (byStatus[st] || 0) + 1;
  }
  return {
    meta,
    byStatus,
    byShop: Object.fromEntries(
      Object.entries(grouped).map(([id, g]) => [
        id,
        {
          name: g.shopName,
          onSale12: Object.keys(g.onSaleMap).length,
          statusCounts: g.statusCounts,
        },
      ]),
    ),
    sampleOnSale: items
      .filter((i) => i.selectStatus === SELECT_STATUS.ON_SALE)
      .slice(0, 5)
      .map((i) => ({
        shop: i.shopName,
        skcId: i.skcId,
        parentId: i.parentId,
        name: i.productName.slice(0, 40),
        selectStatus: i.selectStatus,
      })),
  };
}
