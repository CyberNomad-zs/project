/**
 * 在售 SKC → SKU 基线库（JSON 文件，零依赖「数据库」）
 *
 * 模型（按店）：
 *   bySkc[skcId] = { parentId, name, skus: { [skuId]: { skuId, specName, extCode, ... } }, ts }
 *
 * 判定：
 *   - 父体仍在售(12)：拉 getChildInfo 与 bySkc 比对 → 多=上架 SKU，少=下架 SKU
 *   - 父体离开 12：该 SKC 下原有 SKU 全部视为下架，并从库删除
 *   - 首轮 / 新建 SKC：只 seed 不告警
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

export function defaultSkuDbPath(stateFile) {
  // 与 sellfox-state.json 同目录：data/sellfox-sku-db.json
  const dir = dirname(resolve(stateFile || 'data/sellfox-state.json'));
  return resolve(dir, 'sellfox-sku-db.json');
}

export function loadSkuDb(path) {
  try {
    if (!existsSync(path)) return { version: 1, stores: {} };
    const j = JSON.parse(readFileSync(path, 'utf8'));
    if (!j || typeof j !== 'object') return { version: 1, stores: {} };
    if (!j.stores) j.stores = {};
    j.version = j.version || 1;
    return j;
  } catch {
    return { version: 1, stores: {} };
  }
}

export function saveSkuDb(path, db) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(db, null, 2), 'utf8');
}

function skuKey(s) {
  return String((s && (s.skuId || s.id)) || '').trim();
}

/** 数组 → map */
export function skusToMap(skus) {
  const m = {};
  for (const s of skus || []) {
    const id = skuKey(s);
    if (!id) continue;
    m[id] = {
      skuId: id,
      parentId: s.parentId != null ? String(s.parentId) : '',
      specName: String(s.specName || '').trim(),
      name: String(s.name || '').trim(),
      extCode: String(s.extCode || '').trim(),
      commoditySku: String(s.commoditySku || '').trim(),
      stockQuantity: s.stockQuantity != null && s.stockQuantity !== '' ? String(s.stockQuantity) : '',
      supplyPrice: s.supplyPrice != null ? String(s.supplyPrice) : '',
      supplyCurrency: String(s.supplyCurrency || '').trim(),
    };
  }
  return m;
}

/**
 * 比对单个 SKC 的新旧 SKU 集合
 * @returns {{ added: object[], removed: object[], nextMap: object }}
 */
export function diffSkuMaps(prevMap, currMap) {
  const prev = prevMap || {};
  const curr = currMap || {};
  const added = [];
  const removed = [];
  for (const id of Object.keys(curr)) {
    if (!(id in prev)) added.push(curr[id]);
  }
  for (const id of Object.keys(prev)) {
    if (!(id in curr)) removed.push(prev[id]);
  }
  return { added, removed, nextMap: curr };
}

/**
 * 一轮 SKU 库更新 + 事件
 *
 * @param {object|null} prevShopDb { bySkc }
 * @param {{
 *   onSaleMap: object,           // 确认在售 SKC 基准（本轮 nextSnap.onSaleMap）
 *   delistedItems?: object[],    // 父体下架 items（带 skcId/parentId/name）
 *   childByParentId: Record<string, object[]>, // parentId → 本轮 getChildInfo
 *   isFirstParentBaseline?: boolean, // 父体首轮：全量 seed SKU 不告警
 *   skip?: boolean,
 * }} input
 */
export function applySkuRound(prevShopDb, input) {
  const prevBySkc = (prevShopDb && prevShopDb.bySkc) || {};
  const onSaleMap = input.onSaleMap || {};
  const childByParent = input.childByParentId || {};
  const delistedItems = input.delistedItems || [];
  const isFirst = !!input.isFirstParentBaseline;
  const skip = !!input.skip;
  const now = Date.now();
  const events = [];

  if (skip) {
    return {
      nextShopDb: prevShopDb || { bySkc: prevBySkc, ts: now },
      events: [],
      stats: { seeded: 0, refreshed: 0, skuDelist: 0, skuOnshelf: 0, skcGone: 0 },
    };
  }

  const nextBySkc = { ...prevBySkc };
  let seeded = 0;
  let refreshed = 0;
  let skuDelist = 0;
  let skuOnshelf = 0;
  let skcGone = 0;

  // —— 1) 父体下架：库中该 SKC 全部 SKU 报下架并删除 ——
  for (const it of delistedItems) {
    const skcId = String(it.skcId || '');
    if (!skcId) continue;
    const prev = nextBySkc[skcId];
    const prevSkus = prev && prev.skus ? Object.values(prev.skus) : [];
    if (prevSkus.length) {
      events.push({
        type: 'sku_delist',
        severity: 'alert',
        reason: 'skc_left_onsale',
        skcId,
        parentId: it.parentId || prev.parentId || '',
        name: it.name || prev.name || '',
        selectStatus: it.selectStatus || '',
        items: prevSkus,
      });
      skuDelist += prevSkus.length;
    }
    if (nextBySkc[skcId]) {
      delete nextBySkc[skcId];
      skcGone++;
    }
  }

  // —— 2) 当前确认在售：有子体数据则 diff / seed ——
  for (const skcId of Object.keys(onSaleMap)) {
    const row = onSaleMap[skcId] || {};
    const parentId = String(row.parentId || '');
    const children = parentId ? childByParent[parentId] : null;
    // 本轮没拉到该父体子体 → 保留库、不判 diff（避免空结果当全下架）
    if (!Array.isArray(children)) continue;

    const currMap = skusToMap(children);
    const prevEntry = nextBySkc[skcId];
    const prevMap = (prevEntry && prevEntry.skus) || null;
    const hadBaseline = prevMap && Object.keys(prevMap).length > 0;

    if (isFirst || !hadBaseline) {
      nextBySkc[skcId] = {
        parentId,
        name: row.name || prevEntry?.name || '',
        skus: currMap,
        ts: now,
      };
      seeded++;
      continue;
    }

    const { added, removed } = diffSkuMaps(prevMap, currMap);
    if (removed.length) {
      events.push({
        type: 'sku_delist',
        severity: 'alert',
        reason: 'sku_missing_while_skc_onsale',
        skcId,
        parentId,
        name: row.name || prevEntry.name || '',
        selectStatus: row.selectStatus || '12',
        items: removed,
      });
      skuDelist += removed.length;
    }
    if (added.length) {
      events.push({
        type: 'sku_onshelf',
        severity: 'alert',
        reason: 'sku_new_while_skc_onsale',
        skcId,
        parentId,
        name: row.name || prevEntry.name || '',
        selectStatus: row.selectStatus || '12',
        items: added,
      });
      skuOnshelf += added.length;
    }

    nextBySkc[skcId] = {
      parentId,
      name: row.name || prevEntry.name || '',
      skus: currMap,
      ts: now,
    };
    refreshed++;
  }

  // —— 3) 库中残留但不在确认在售、也不是本轮 delist 处理过的：父体漏数时不删（由 skip 保护）；
  //     若确认不在 onSale 且不在 delisted 列表 → 可能是 skip 外的幽灵，保守保留
  //     （父体 diff 已用 ghost carry；SKU 库跟确认 onSaleMap 对齐清理）
  if (!isFirst) {
    for (const skcId of Object.keys(nextBySkc)) {
      if (skcId in onSaleMap) continue;
      // 已在 delisted 处理中删除；若仍在则是「未告警父体下架」残留 → 随确认基准清理且不二次告警
      if (delistedItems.some((d) => String(d.skcId) === skcId)) continue;
      // 不在 onSale 的 SKC：从库移除，不告警（父体层应已报或 ghost carry）
      delete nextBySkc[skcId];
    }
  }

  return {
    nextShopDb: { bySkc: nextBySkc, ts: now },
    events,
    stats: { seeded, refreshed, skuDelist, skuOnshelf, skcGone },
  };
}

/**
 * 飞书：SKU 级上下架卡片行
 */
export function formatSkuChangeLines(storeName, skuEvents, { editBaseUrl } = {}) {
  const base = String(editBaseUrl || 'https://agentseller.temu.com').replace(/\/$/, '');
  const edit = (parentId) =>
    `${base}/goods/edit?from=productList&productId=${parentId || ''}`;

  const lines = [`**🏬 ${storeName}**（赛狐 SKU 基线 diff · getChildInfo）`];
  let nDel = 0;
  let nAdd = 0;

  for (const ev of skuEvents || []) {
    if (ev.severity !== 'alert') continue;
    const skc = ev.skcId || '-';
    const pid = ev.parentId || '';
    const nm = String(ev.name || '商品').replace(/[[\]]/g, '').slice(0, 36);
    const title =
      pid
        ? `• [${nm}](${edit(pid)})  SKC ${skc}`
        : `• ${nm}  SKC ${skc}`;

    if (ev.type === 'sku_delist' && ev.items?.length) {
      nDel += ev.items.length;
      const why =
        ev.reason === 'skc_left_onsale'
          ? '（随 SKC 离开在售）'
          : '（SKC 仍在售，子体清单减少）';
      lines.push(`📉 **SKU 下架** ${ev.items.length} 个${why}`);
      lines.push(title);
      for (const s of ev.items.slice(0, 12)) {
        const parts = [`SKU ${s.skuId || '-'}`];
        if (s.specName) parts.push(s.specName);
        if (s.extCode || s.commoditySku) parts.push(`货号 ${s.extCode || s.commoditySku}`);
        if (s.stockQuantity) parts.push(`库存 ${s.stockQuantity}`);
        lines.push(`  ◦ ${parts.join(' · ')}`);
      }
      if (ev.items.length > 12) lines.push(`  ◦ _…另有 ${ev.items.length - 12} 个_`);
    }
    if (ev.type === 'sku_onshelf' && ev.items?.length) {
      nAdd += ev.items.length;
      lines.push(`📈 **SKU 上架** ${ev.items.length} 个（SKC 仍在售，子体清单增加）`);
      lines.push(title);
      for (const s of ev.items.slice(0, 12)) {
        const parts = [`SKU ${s.skuId || '-'}`];
        if (s.specName) parts.push(s.specName);
        if (s.extCode || s.commoditySku) parts.push(`货号 ${s.extCode || s.commoditySku}`);
        if (s.stockQuantity) parts.push(`库存 ${s.stockQuantity}`);
        lines.push(`  ◦ ${parts.join(' · ')}`);
      }
      if (ev.items.length > 12) lines.push(`  ◦ _…另有 ${ev.items.length - 12} 个_`);
    }
  }

  if (!nDel && !nAdd) {
    lines.push('_本轮无 SKU 增减_');
  } else {
    const parts = [];
    if (nDel) parts.push(`−${nDel} SKU`);
    if (nAdd) parts.push(`+${nAdd} SKU`);
    lines.push(`📊 SKU 变动合计：${parts.join(' ')}`);
    lines.push('_说明：以赛狐 getChildInfo 清单 diff 为准；与后台规格页可能略有延迟_');
  }
  lines.push(
    '',
    `_检查时间：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}_`,
  );
  return lines;
}

export function skuAlertTemplate(events) {
  const types = new Set((events || []).filter((e) => e.severity === 'alert').map((e) => e.type));
  const hasD = types.has('sku_delist');
  const hasO = types.has('sku_onshelf');
  if (hasD && hasO) return 'orange';
  if (hasO) return 'green';
  return 'red';
}

export function skuAlertTitle(events) {
  const types = new Set((events || []).filter((e) => e.severity === 'alert').map((e) => e.type));
  const hasD = types.has('sku_delist');
  const hasO = types.has('sku_onshelf');
  if (hasD && hasO) return '🔔 Temu SKU 变动（赛狐基线）';
  if (hasO) return '🔔 Temu SKU 上架（赛狐基线）';
  return '🔔 Temu SKU 下架（赛狐基线）';
}
