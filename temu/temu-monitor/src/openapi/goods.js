/**
 * 商品列表 / 流量标签拉取
 * - bg.local.goods.list.query（pageNo 分页）
 * - temu.local.goods.list.retrieve（pageToken 分页）
 *
 * 标签（官方文档）：
 *   goodsSearchTags: 1=Low traffic, 4=Restricted traffic
 *   lowTrafficTag: 1=低流量, 2=否
 *   restrictedTrafficTag: 1=限流, 2=否
 */

const PAGE_SIZE_MAX = 100;

function goodsIdOf(g) {
  const id = g?.goodsId ?? g?.goods_id ?? g?.productId;
  return id == null || id === '' ? null : String(id);
}

function nameOf(g) {
  return String(g?.goodsName || g?.goods_name || g?.productName || '').trim();
}

/** 是否视为「在售/上架可售」——用于下架 diff 的当前集合 */
export function isActiveGoods(g) {
  // retrieve 接口可能直接返回 goodsStatus 字符串
  const gs = String(g?.goodsStatus || g?.goods_status || '').toUpperCase();
  if (gs === 'ACTIVE' || gs === 'ON_SALE' || gs === 'ONSALE') return true;
  if (gs === 'INACTIVE' || gs === 'OFF_SALE' || gs === 'OFFSALE' || gs === 'DELETED') return false;

  // list.query: status4VO 文档示例 1=on sale
  const s4 = Number(g?.status4VO ?? g?.status);
  if (Number.isFinite(s4)) {
    // 保守：仅 1 视为在售；其它数字留给观测日志，默认不当作在售
    if (s4 === 1) return true;
    if (s4 === 2 || s4 === 3 || s4 === 4 || s4 === 5 || s4 === 6) return false;
  }

  // 若调用方用 ACTIVE 筛选拉回，列表内默认都算在售
  if (g?.__assumedActive) return true;
  return false;
}

export function isLowTraffic(g) {
  const t = Number(g?.lowTrafficTag);
  if (t === 1) return true;
  if (t === 2) return false;
  return false;
}

export function isRestrictedTraffic(g) {
  const t = Number(g?.restrictedTrafficTag);
  if (t === 1) return true;
  if (t === 2) return false;
  return false;
}

export function normalizeGoods(g, { assumedActive = false } = {}) {
  const id = goodsIdOf(g);
  if (!id) return null;
  const row = assumedActive ? { ...g, __assumedActive: true } : g;
  return {
    goodsId: id,
    name: nameOf(g),
    active: isActiveGoods(row),
    lowTraffic: isLowTraffic(g),
    restrictedTraffic: isRestrictedTraffic(g),
    status4VO: g?.status4VO ?? null,
    subStatus4VO: g?.subStatus4VO ?? null,
    goodsShowSubStatus: g?.goodsShowSubStatus ?? null,
    goodsStatus: g?.goodsStatus ?? null,
    outGoodsSn: g?.outGoodsSn || '',
    thumbUrl: g?.thumbUrl || '',
  };
}

/**
 * 分页拉全量（list.query）
 * goodsSearchType: 1=Available/off the shelf, 4=unpublished, 5=draft, 6=deleted
 */
export async function fetchAllListQuery(client, accessToken, {
  goodsSearchType = 1,
  goodsStatusFilterType,
  goodsSearchTags,
  pageSize = PAGE_SIZE_MAX,
  assumedActive = false,
} = {}) {
  const size = Math.min(PAGE_SIZE_MAX, Math.max(1, Number(pageSize) || PAGE_SIZE_MAX));
  const all = [];
  let pageNo = 1;
  let total = null;
  for (;;) {
    const biz = {
      pageNo,
      pageSize: size,
      goodsSearchType,
    };
    if (goodsStatusFilterType != null) biz.goodsStatusFilterType = goodsStatusFilterType;
    if (Array.isArray(goodsSearchTags) && goodsSearchTags.length) biz.goodsSearchTags = goodsSearchTags;

    const data = await client.call('bg.local.goods.list.query', biz, { accessToken });
    const result = data.result || {};
    const list = result.goodsList || result.data || [];
    if (typeof result.total === 'number') total = result.total;
    for (const g of list) {
      const n = normalizeGoods(g, { assumedActive });
      if (n) all.push(n);
    }
    if (!list.length) break;
    if (total != null && all.length >= total) break;
    if (list.length < size) break;
    pageNo += 1;
    if (pageNo > 500) throw new Error('list.query 分页超过 500 页，中止防死循环');
  }
  return { items: all, total: total ?? all.length };
}

/**
 * 分页拉全量（list.retrieve）
 * goodsSearchType: ALL | ACTIVE | INACTIVE | INCOMPLETE | DRAFT | DELETED
 */
export async function fetchAllListRetrieve(client, accessToken, {
  goodsSearchType = 'ACTIVE',
  goodsSearchTags,
  pageSize = PAGE_SIZE_MAX,
} = {}) {
  const size = Math.min(PAGE_SIZE_MAX, Math.max(1, Number(pageSize) || PAGE_SIZE_MAX));
  const all = [];
  let pageToken = undefined;
  let total = null;
  let guard = 0;
  const assumedActive = String(goodsSearchType).toUpperCase() === 'ACTIVE';
  for (;;) {
    const biz = {
      goodsSearchType,
      pageSize: size,
    };
    if (pageToken) biz.pageToken = pageToken;
    if (Array.isArray(goodsSearchTags) && goodsSearchTags.length) biz.goodsSearchTags = goodsSearchTags;

    const data = await client.call('temu.local.goods.list.retrieve', biz, { accessToken });
    const result = data.result || {};
    const list = result.goodsList || result.data || [];
    if (typeof result.total === 'number') total = result.total;
    for (const g of list) {
      const n = normalizeGoods(g, { assumedActive });
      if (n) all.push(n);
    }
    const next = result.pagination?.nextToken || result.nextToken || null;
    if (!list.length || !next) break;
    pageToken = next;
    guard += 1;
    if (guard > 500) throw new Error('list.retrieve 分页超过 500 页，中止防死循环');
  }
  return { items: all, total: total ?? all.length };
}

/**
 * 拉一店完整监测快照所需数据：
 *  - 在售集合（ACTIVE）
 *  - 低流量集合（tag=1）
 *  - 限流集合（tag=4）
 */
export async function fetchStoreCatalog(client, accessToken, cfg = {}) {
  const mode = cfg.apiMode === 'listRetrieve' ? 'listRetrieve' : 'listQuery';
  const pageSize = cfg.pageSize || PAGE_SIZE_MAX;

  let activeItems;
  if (mode === 'listRetrieve') {
    ({ items: activeItems } = await fetchAllListRetrieve(client, accessToken, {
      goodsSearchType: 'ACTIVE',
      pageSize,
    }));
  } else {
    // list.query：用 type=1 拉「可售/下架」合集，再按 isActiveGoods 过滤
    // 若 status 字段识别不准，可在 openapi.config 设 forceAssumeActiveOnType1: true
    const force = cfg.forceAssumeActiveOnType1 === true;
    const { items } = await fetchAllListQuery(client, accessToken, {
      goodsSearchType: 1,
      goodsStatusFilterType: 1,
      pageSize,
      assumedActive: force,
    });
    activeItems = force ? items : items.filter((x) => x.active);
    // 若过滤后为空但原列表非空，降级：整表当作候选在售并打日志（避免误判全下架）
    if (!activeItems.length && items.length) {
      activeItems = items.map((x) => ({ ...x, active: true }));
    }
  }

  // 流量标签：优先用 goodsSearchTags 直接筛（更准、更省）
  let lowItems = [];
  let restrictedItems = [];
  try {
    if (mode === 'listRetrieve') {
      ({ items: lowItems } = await fetchAllListRetrieve(client, accessToken, {
        goodsSearchType: 'ALL',
        goodsSearchTags: [1],
        pageSize,
      }));
      ({ items: restrictedItems } = await fetchAllListRetrieve(client, accessToken, {
        goodsSearchType: 'ALL',
        goodsSearchTags: [4],
        pageSize,
      }));
    } else {
      ({ items: lowItems } = await fetchAllListQuery(client, accessToken, {
        goodsSearchType: 1,
        goodsSearchTags: [1],
        pageSize,
        assumedActive: true,
      }));
      ({ items: restrictedItems } = await fetchAllListQuery(client, accessToken, {
        goodsSearchType: 1,
        goodsSearchTags: [4],
        pageSize,
        assumedActive: true,
      }));
    }
  } catch (e) {
    // 标签筛选失败时回退：用 ACTIVE 列表上的 tag 字段
    lowItems = activeItems.filter((x) => x.lowTraffic);
    restrictedItems = activeItems.filter((x) => x.restrictedTraffic);
    e._fallback = true;
    throw Object.assign(e, { partial: { activeItems, lowItems, restrictedItems } });
  }

  // 若 tag 筛选返回空，再用字段扫 ACTIVE（兼容「筛选无效但字段有值」）
  if (!lowItems.length) lowItems = activeItems.filter((x) => x.lowTraffic);
  if (!restrictedItems.length) restrictedItems = activeItems.filter((x) => x.restrictedTraffic);

  const toMap = (arr) => {
    const m = {};
    for (const it of arr) {
      if (!it?.goodsId) continue;
      m[it.goodsId] = {
        name: it.name || '',
        lowTraffic: !!it.lowTraffic,
        restrictedTraffic: !!it.restrictedTraffic,
      };
    }
    return m;
  };

  return {
    activeMap: toMap(activeItems),
    lowTrafficMap: toMap(lowItems.map((x) => ({ ...x, lowTraffic: true }))),
    restrictedMap: toMap(restrictedItems.map((x) => ({ ...x, restrictedTraffic: true }))),
    counts: {
      active: activeItems.length,
      lowTraffic: lowItems.length,
      restricted: restrictedItems.length,
    },
    rawSample: activeItems.slice(0, 3),
  };
}
