/**
 * OpenAPI 一轮监测：拉目录 → diff → 飞书 → 写快照
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname } from 'node:path';
import { createOpenApiClient } from './client.js';
import { fetchStoreCatalog } from './goods.js';
import { diffCatalog, formatAlertLines } from './diff.js';
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
 * @param {object} cfg loadOpenApiConfig() 结果
 * @param {{ dryRun?: boolean }} [opts]
 */
export async function runOpenApiOnce(cfg, opts = {}) {
  const enabledStores = (cfg.stores || []).filter((s) => s.enabled !== false && s.accessToken);
  if (!cfg.appKey || !cfg.appSecret) throw new Error('缺少 appKey/appSecret');
  if (!enabledStores.length) throw new Error('没有可监测的店铺（需 name + accessToken）');

  const state = loadState(cfg.stateFile);
  if (!state.stores) state.stores = {};

  const summary = [];

  for (const store of enabledStores) {
    const name = store.name;
    const baseUrl = (store.baseUrl || cfg.baseUrl).replace(/\/openapi\/router\/?$/i, '').replace(/\/$/, '');
    const client = createOpenApiClient({
      appKey: cfg.appKey,
      appSecret: cfg.appSecret,
      baseUrl,
      debug: cfg.debug,
    });

    log.info(`OpenAPI 监测店铺：${name}`);
    let catalog;
    try {
      catalog = await fetchStoreCatalog(client, store.accessToken, {
        apiMode: cfg.apiMode,
        pageSize: cfg.pageSize,
        forceAssumeActiveOnType1: cfg.forceAssumeActiveOnType1,
      });
    } catch (e) {
      if (e.partial) {
        log.warn(`${name} 标签筛选失败，已用 ACTIVE 字段回退：`, e.message);
        catalog = {
          activeMap: Object.fromEntries((e.partial.activeItems || []).map((x) => [x.goodsId, { name: x.name }])),
          lowTrafficMap: Object.fromEntries((e.partial.lowItems || []).map((x) => [x.goodsId, { name: x.name }])),
          restrictedMap: Object.fromEntries((e.partial.restrictedItems || []).map((x) => [x.goodsId, { name: x.name }])),
          counts: {
            active: e.partial.activeItems?.length || 0,
            lowTraffic: e.partial.lowItems?.length || 0,
            restricted: e.partial.restrictedItems?.length || 0,
          },
        };
      } else {
        log.error(`${name} 拉取失败：`, e.message);
        summary.push({ store: name, ok: false, error: e.message });
        continue;
      }
    }

    log.info(
      `${name} 目录：在售=${catalog.counts.active} 低流量=${catalog.counts.lowTraffic} 限流=${catalog.counts.restricted}`,
    );
    if (cfg.debug && catalog.rawSample?.length) {
      log.info(`${name} 样本：`, catalog.rawSample);
    }

    const prev = state.stores[name]?.snapshot || null;
    const { events, nextSnap, isFirst, skipDelistUpdate } = diffCatalog(prev, catalog, cfg.alerts);

    if (isFirst) {
      log.info(`${name} 首轮：建立基准，不告警（在售 ${catalog.counts.active}）`);
    } else if (skipDelistUpdate) {
      log.warn(`${name} 跳过下架更新（扫描疑似不全）`);
    }

    const alertEvents = events.filter((e) => e.severity === 'alert');
    if (alertEvents.length && !opts.dryRun) {
      const lines = formatAlertLines(name, alertEvents, { editBaseUrl: cfg.editBaseUrl });
      const title = '🔔 Temu OpenAPI 监测告警';
      await sendFeishu(
        { feishuWebhooks: cfg.feishuWebhooks, feishuSecret: cfg.feishuSecret },
        { title, template: 'red', lines },
      );
      log.info(`${name} 已告警 ${alertEvents.length} 类事件`);
    } else if (alertEvents.length && opts.dryRun) {
      log.info(`${name} dryRun 告警内容：`, formatAlertLines(name, alertEvents, { editBaseUrl: cfg.editBaseUrl }));
    } else if (!isFirst) {
      log.info(`${name} 本轮无异常`);
    }

    state.stores[name] = {
      latest: {
        ...catalog.counts,
        ts: Date.now(),
      },
      snapshot: nextSnap,
    };
    summary.push({
      store: name,
      ok: true,
      counts: catalog.counts,
      events: events.map((e) => e.type),
      isFirst,
    });
  }

  if (!opts.dryRun) saveState(cfg.stateFile, state);
  return summary;
}

/** 探测：token 权限 + 拉 1 页商品 */
export async function probeStore(cfg, storeName) {
  const store = (cfg.stores || []).find((s) => s.name === storeName) || (cfg.stores || [])[0];
  if (!store?.accessToken) throw new Error('未找到店铺 accessToken');
  const baseUrl = (store.baseUrl || cfg.baseUrl).replace(/\/openapi\/router\/?$/i, '').replace(/\/$/, '');
  const client = createOpenApiClient({
    appKey: cfg.appKey,
    appSecret: cfg.appSecret,
    baseUrl,
    debug: true,
  });

  let info = null;
  try {
    info = await client.tokenInfo(store.accessToken);
  } catch (e) {
    log.warn('tokenInfo 失败（可忽略）：', e.message);
  }

  let page = null;
  try {
    page = await client.call(
      'bg.local.goods.list.query',
      { pageNo: 1, pageSize: 5, goodsSearchType: 1, goodsStatusFilterType: 1 },
      { accessToken: store.accessToken },
    );
  } catch (e) {
    // 再试 retrieve
    try {
      page = await client.call(
        'temu.local.goods.list.retrieve',
        { goodsSearchType: 'ACTIVE', pageSize: 5 },
        { accessToken: store.accessToken },
      );
    } catch (e2) {
      return { store: store.name, info, listError: e.message, retrieveError: e2.message };
    }
  }

  const result = page?.result || {};
  const list = result.goodsList || [];
  return {
    store: store.name,
    mallId: info?.result?.mallId,
    apiScopeList: info?.result?.apiScopeList || info?.result?.api_scope_list,
    sampleCount: list.length,
    total: result.total,
    sample: list.slice(0, 3).map((g) => ({
      goodsId: g.goodsId,
      goodsName: g.goodsName,
      status4VO: g.status4VO,
      lowTrafficTag: g.lowTrafficTag,
      restrictedTrafficTag: g.restrictedTrafficTag,
      goodsStatus: g.goodsStatus,
    })),
  };
}
