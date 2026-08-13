/**
 * 赛狐 Temu 下架监测一轮
 *
 * 1) 父体 getParentPageList → selectStatus=12 集合 diff（SKC 上下架）
 * 2) 本地 SKU 库：在售 SKC 的 getChildInfo 清单；diff 多/少 = SKU 上/下架
 * 3) 飞书：SKC 卡片 +（若有）SKU 基线 diff 卡片
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname } from 'node:path';
import { createSellfoxClient } from './client.js';
import {
  fetchAllCrossParents,
  groupByShop,
  SELECT_STATUS,
  fetchChildrenByParentIds,
  attachSkusToAlertEvents,
} from './products.js';
import { diffOnSale, formatChangeLines, alertTemplate, alertTitle } from './diff.js';
import {
  defaultSkuDbPath,
  loadSkuDb,
  saveSkuDb,
  applySkuRound,
  formatSkuChangeLines,
  skuAlertTemplate,
  skuAlertTitle,
} from './skuStore.js';
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
 * 从确认在售 map 收集 parentId
 * @param {object} onSaleMap
 */
function parentIdsFromOnSale(onSaleMap) {
  const ids = [];
  for (const row of Object.values(onSaleMap || {})) {
    if (row && row.parentId) ids.push(String(row.parentId));
  }
  return [...new Set(ids)];
}

/**
 * 父体告警 items 挂上库里已有 SKU 或本轮 childMap
 */
function attachSkusFromMaps(alertEvents, childByParent, shopDb) {
  const bySkc = (shopDb && shopDb.bySkc) || {};
  for (const ev of alertEvents || []) {
    for (const it of ev.items || []) {
      if (!it) continue;
      const pid = String(it.parentId || '');
      const skc = String(it.skcId || '');
      let skus = pid && childByParent[pid] ? childByParent[pid] : null;
      if ((!skus || !skus.length) && skc && bySkc[skc] && bySkc[skc].skus) {
        skus = Object.values(bySkc[skc].skus);
      }
      if (skus && skus.length) {
        it.skus = skus;
        it.skusAttempted = true;
      } else if (pid) {
        it.skusAttempted = true;
        it.skus = it.skus || [];
      }
    }
  }
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
  const skuDbPath = cfg.skuDbFile || defaultSkuDbPath(cfg.stateFile);
  const skuDb = loadSkuDb(skuDbPath);
  if (!skuDb.stores) skuDb.stores = {};

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
  // 跨店合并 parentId 子体请求，整轮结束再按店 diff（减少重复 parent）
  // 但各店 onSale 集合不同，仍按店拉各自 onSale parent（体量小 ~40）

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

    // —— 拉在售 SKC 的子体（SKU 库刷新）；skip 时不动库 ——
    let childByParent = {};
    if (!skipUpdate) {
      const pids = parentIdsFromOnSale(nextSnap.onSaleMap);
      if (pids.length) {
        log.info(`${name} 刷新在售 SKU 基线：${pids.length} 个 parentId`);
        childByParent = await fetchChildrenByParentIds(client, pids, {
          delayMs: 500,
          onError: (pid, err) => {
            log.warn(
              `${name} getChildInfo 失败 parentId=${pid}: ${err && (err.msg || err.message) || err}`,
            );
          },
        });
        const okN = Object.values(childByParent).filter((a) => Array.isArray(a) && a.length).length;
        log.info(`${name} getChildInfo 成功有明细 ${okN}/${pids.length}`);
      }
    }

    // —— SKU 库 diff ——
    const delistEv = events.find((e) => e.type === 'delist' && e.severity === 'alert');
    const delistedItems = delistEv?.items || [];
    const prevShopSku = skuDb.stores[sid] || { bySkc: {} };
    const {
      nextShopDb,
      events: skuEvents,
      stats: skuStats,
    } = applySkuRound(prevShopSku, {
      onSaleMap: nextSnap.onSaleMap,
      delistedItems,
      childByParentId: childByParent,
      isFirstParentBaseline: isFirst,
      skip: skipUpdate,
    });

    log.info(
      `${name} SKU库: seed=${skuStats.seeded} refresh=${skuStats.refreshed}` +
        ` sku↓=${skuStats.skuDelist} sku↑=${skuStats.skuOnshelf} skc移除=${skuStats.skcGone}`,
    );

    // 父体告警过滤
    const alertEvents = events.filter((e) => {
      if (e.severity !== 'alert') return false;
      if (e.type === 'delist') return cfg.alerts?.delist !== false;
      if (e.type === 'onshelf') return cfg.alerts?.onshelf !== false;
      return false;
    });

    // SKC 卡片挂 SKU（本轮 child 或库内旧清单）
    if (alertEvents.length) {
      attachSkusFromMaps(alertEvents, childByParent, prevShopSku);
      // 上架 SKC：优先用本轮新拉的 child
      attachSkusToAlertEvents(alertEvents, childByParent);
      for (const ev of alertEvents) {
        for (const it of ev.items || []) {
          if (it) it.skusAttempted = true;
        }
      }
    }

    // SKU 级告警过滤
    // skc_left_onsale：整 SKC 下架已由父体卡片覆盖（并挂旧 SKU 列表），不再发第二张 SKU 卡
    const skuAlertEvents = (skuEvents || []).filter((e) => {
      if (e.severity !== 'alert') return false;
      if (e.reason === 'skc_left_onsale') return false;
      if (e.type === 'sku_delist') return cfg.alerts?.skuDelist !== false && cfg.alerts?.delist !== false;
      if (e.type === 'sku_onshelf') return cfg.alerts?.skuOnshelf !== false && cfg.alerts?.onshelf !== false;
      return false;
    });

    // —— 飞书：SKC ——
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
      log.info(`${name} 已告警 SKC ${parts.join('、')}`);
    } else if (alertEvents.length && opts.dryRun) {
      log.info(
        `${name} dryRun SKC:`,
        formatChangeLines(name, alertEvents, { editBaseUrl: cfg.editBaseUrl }),
      );
    }

    // —— 飞书：SKU 基线 diff ——
    // 若某 SKU 下架已因「整 SKC 离开在售」报过，父体 delist 卡片已带旧 SKU 列表；
    // 仍发 SKU 卡便于点名「具体哪个 SKU」；可接受双卡。若只要一张可后续加 dedupe。
    if (skuAlertEvents.length && !opts.dryRun) {
      const lines = formatSkuChangeLines(name, skuAlertEvents, { editBaseUrl: cfg.editBaseUrl });
      await sendFeishu(
        { feishuWebhooks: cfg.feishuWebhooks, feishuSecret: cfg.feishuSecret },
        {
          title: skuAlertTitle(skuAlertEvents),
          template: skuAlertTemplate(skuAlertEvents),
          lines,
        },
      );
      log.info(
        `${name} 已告警 SKU ↓${skuStats.skuDelist} ↑${skuStats.skuOnshelf}`,
      );
    } else if (skuAlertEvents.length && opts.dryRun) {
      log.info(
        `${name} dryRun SKU:`,
        formatSkuChangeLines(name, skuAlertEvents, { editBaseUrl: cfg.editBaseUrl }),
      );
    }

    if (!isFirst && !skipUpdate && !alertEvents.length && !skuAlertEvents.length) {
      const pendN = pendingOnshelfCount || 0;
      log.info(
        `${name} 本轮无上下架告警` +
          (pendN ? `（待确认上架 ${pendN}）` : '') +
          ` 确认在售=${nextSnap.onSaleCount}`,
      );
    }

    // 持久化
    state.stores[sid] = {
      name,
      latest: {
        onSaleCount: nextSnap.onSaleCount,
        allCount: nextSnap.allCount,
        pendingOnshelfCount: Object.keys(nextSnap.pendingOnshelf || {}).length,
        statusCounts: g.statusCounts,
        skuSkcCount: Object.keys(nextShopDb.bySkc || {}).length,
        skuTotal: Object.values(nextShopDb.bySkc || {}).reduce(
          (n, e) => n + Object.keys((e && e.skus) || {}).length,
          0,
        ),
        ts: Date.now(),
      },
      snapshot: nextSnap,
    };
    if (!opts.dryRun && !skipUpdate) {
      skuDb.stores[sid] = nextShopDb;
    }

    summary.push({
      shopId: sid,
      store: name,
      onSale: nextSnap.onSaleCount,
      allCount: nextSnap.allCount,
      pendingOnshelf: Object.keys(nextSnap.pendingOnshelf || {}).length,
      statusCounts: g.statusCounts,
      events: events.map((e) => e.type),
      skuEvents: (skuEvents || []).map((e) => e.type),
      skuStats,
      isFirst,
      skipUpdate,
      ghostCount,
    });
  }

  for (const shop of shops) {
    if (!summary.find((s) => s.shopId === shop.shopId)) {
      summary.push({ shopId: shop.shopId, store: shop.name, onSale: 0, note: '无数据' });
    }
  }

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
    saveSkuDb(skuDbPath, skuDb);
    log.info(`SKU 库已写入 ${skuDbPath}`);
  }
  return { meta, summary, onSaleStatus: SELECT_STATUS.ON_SALE, skuDbPath };
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
