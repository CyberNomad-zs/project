/**
 * 赛狐 Temu 在售集合 diff → 下架 / 上架
 * 在售定义：selectStatus === "12"（已加入站点）
 *
 * 2026-07-31 防误报（服务器实锤）：
 * 某轮 getParentPageList 漏拉（unique 954→918），HomeCove 在售被算成 10，
 * 飞书误报「下架 5」；下一轮拉全又「上架 5」。半降护栏(50%)挡不住 15→10。
 *
 * 规则：
 *  1) 本店 allMap 相对上轮 allCount 掉太多 → 整轮 skip（接口不全）
 *  2) 「下架」必须：已在**确认基准** onSaleMap 中，且本轮仍出现在 allMap、status ≠ 12
 *     完全从本轮结果消失的 SKC = 漏数，不告警、不从基准剔除
 *  3) 「上架」二次确认（2026-08-05）：
 *     - 本轮新出现的 12 → 只进 pendingOnshelf，**不进确认基准、不告警**
 *     - 上轮 pending 且本轮仍为 12 → 确认上架告警，写入基准
 *     - 上轮 pending 但本轮已不是 12 → 抖动丢弃（不告警上架、更不会假下架）
 *  4) 文案：from/to 只写一次合计；注明以赛狐为准，可能与后台「在售中」有延迟
 */
import { SELECT_STATUS } from './products.js';

/**
 * @param {object|null} prevSnap { onSaleMap, allCount, statusCounts, pendingOnshelf, ts }
 * @param {{ onSaleMap: object, allMap?: object, statusCounts?: object, pullUnique?: number, prevPullUnique?: number }} curr
 */
export function diffOnSale(prevSnap, curr) {
  const prevMap = (prevSnap && prevSnap.onSaleMap) || null;
  const currMap = curr.onSaleMap || {};
  const allMap = curr.allMap || {};
  const currIds = Object.keys(currMap);
  const prevPending = (prevSnap && prevSnap.pendingOnshelf) || {};
  const events = [];
  let skipUpdate = false;

  const prevAllCount =
    typeof prevSnap?.allCount === 'number'
      ? prevSnap.allCount
      : null;
  const currAllCount = Object.keys(allMap).length;

  // —— 全店商品数骤降：赛狐分页/限流漏数（实锤 954→918 级）——
  if (prevAllCount != null && prevAllCount >= 30 && currAllCount > 0) {
    if (currAllCount < Math.floor(prevAllCount * 0.92)) {
      skipUpdate = true;
      events.push({
        type: 'scan_incomplete',
        severity: 'warn',
        message: `本店商品列表疑似不全：上轮 all=${prevAllCount} → 本轮 ${currAllCount}，跳过上下架`,
      });
    }
  }

  // —— 全局 unique 骤降（monitor 传入）——
  if (
    !skipUpdate &&
    typeof curr.prevPullUnique === 'number' &&
    typeof curr.pullUnique === 'number' &&
    curr.prevPullUnique >= 100 &&
    curr.pullUnique < Math.floor(curr.prevPullUnique * 0.95)
  ) {
    skipUpdate = true;
    events.push({
      type: 'scan_incomplete',
      severity: 'warn',
      message: `全量 unique 疑似不全：${curr.prevPullUnique} → ${curr.pullUnique}，跳过上下架`,
    });
  }

  // —— 在售腰斩（旧护栏，保留；按确认基准）——
  if (!skipUpdate && prevMap) {
    const prevN = Object.keys(prevMap).length;
    // 用「确认基准 ∩ 本轮仍在售」粗估，避免 pending 未入基准时误伤
    const stillCommitted = prevMap
      ? Object.keys(prevMap).filter((id) => id in currMap).length
      : 0;
    if (prevN >= 5 && stillCommitted < Math.floor(prevN * 0.5)) {
      skipUpdate = true;
      events.push({
        type: 'scan_incomplete',
        severity: 'warn',
        message: `在售疑似不全：基准 ${prevN} → 本轮仍在售 ${stillCommitted}，跳过上下架判定`,
      });
    }
  }

  let delisted = [];
  let listed = []; // 连续两轮确认后的上架
  let ghosts = []; // 确认基准内、本轮 allMap 都没有 → 漏数
  let nextPending = {};
  let listedRawCount = 0;

  if (prevMap && !skipUpdate) {
    const prevIds = Object.keys(prevMap);

    // —— 下架：只从确认基准判定 ——
    for (const id of prevIds) {
      if (id in currMap) continue; // 仍在售
      const row = allMap[id];
      if (row && String(row.selectStatus) !== SELECT_STATUS.ON_SALE) {
        delisted.push(id);
      } else if (!row) {
        ghosts.push(id);
      } else {
        ghosts.push(id);
      }
    }

    // 大量 ghost = 本轮漏拉，整轮作废
    if (
      ghosts.length >= 3 ||
      (prevIds.length >= 5 &&
        ghosts.length >= 2 &&
        ghosts.length >= Math.ceil(prevIds.length * 0.15))
    ) {
      skipUpdate = true;
      delisted = [];
      events.push({
        type: 'scan_incomplete',
        severity: 'warn',
        message: `在售商品本轮失踪 ${ghosts.length} 个（未在结果中出现，疑似接口漏数），跳过上下架；样例 SKC ${ghosts.slice(0, 5).join(',')}`,
      });
    } else if (ghosts.length) {
      events.push({
        type: 'scan_ghost',
        severity: 'warn',
        message: `在售商品本轮未出现 ${ghosts.length} 个（保留基准、不报下架）：${ghosts.slice(0, 8).join(',')}`,
        items: ghosts.map((id) => ({
          skcId: id,
          parentId: prevMap[id]?.parentId || '',
          name: prevMap[id]?.name || '',
        })),
      });
    }

    if (!skipUpdate) {
      // —— 上架二次确认 ——
      // 1) 上轮 pending 且本轮仍 12 → 确认
      for (const id of Object.keys(prevPending)) {
        if (id in currMap) {
          listed.push(id);
        }
        // else: 抖动，丢弃
      }

      // 2) 本轮 12 且不在确认基准、也不是刚确认的 → 新 pending
      //    （刚确认的 listed 本轮直接进基准，不再回 pending）
      const listedSet = new Set(listed);
      for (const id of currIds) {
        if (id in prevMap) continue; // 已在确认基准
        if (listedSet.has(id)) continue; // 本轮刚确认
        const row = currMap[id];
        if (!row) continue;
        listedRawCount++;
        nextPending[id] = {
          skcId: row.skcId || id,
          parentId: row.parentId || '',
          name: row.name || '',
          selectStatus: row.selectStatus || SELECT_STATUS.ON_SALE,
          firstSeenTs: prevPending[id]?.firstSeenTs || Date.now(),
        };
      }

      if (Object.keys(nextPending).length) {
        events.push({
          type: 'onshelf_pending',
          severity: 'info',
          message: `新进在售 ${Object.keys(nextPending).length} 个，待下轮确认后再告警：${Object.keys(nextPending).slice(0, 8).join(',')}`,
          items: Object.values(nextPending),
        });
      }
    }

    // 确认基准规模：上轮确认 − 下架 − ghost不扣(carry) + 本轮确认上架
    // from/to 用「本轮结束后的确认基准」表达，避免和 pending 混淆
    const fromN = prevIds.length;
    // to 先按公式，最终与 nextOnSaleMap 对齐（下面构建后回填）
    let toN = fromN - delisted.length + listed.length;
    // ghost 仍留在基准里，不减少 to

    if (!skipUpdate && delisted.length) {
      events.push({
        type: 'delist',
        severity: 'alert',
        items: delisted.map((id) => ({
          skcId: id,
          parentId: (allMap[id] || prevMap[id])?.parentId || '',
          name: (allMap[id] || prevMap[id])?.name || '',
          selectStatus: allMap[id]?.selectStatus || prevMap[id]?.selectStatus || '',
        })),
        from: fromN,
        to: toN,
      });
    }
    if (!skipUpdate && listed.length) {
      events.push({
        type: 'onshelf',
        severity: 'alert',
        items: listed.map((id) => {
          const row = currMap[id] || prevPending[id] || {};
          return {
            skcId: id,
            parentId: row.parentId || '',
            name: row.name || '',
            selectStatus: row.selectStatus || SELECT_STATUS.ON_SALE,
          };
        }),
        from: fromN,
        to: toN,
      });
    }
  }

  const isFirst = !prevMap;

  // —— 构建下一轮确认基准 onSaleMap ——
  //  skip → 整表沿用 prev + 保留 pending
  //  否则：
  //    保留：上轮确认且本轮仍 12
  //    保留：ghost（漏数 carry）
  //    加入：本轮确认上架 listed
  //    不加入：nextPending（待确认）
  let nextOnSaleMap;
  let nextPendingFinal = nextPending;
  if (skipUpdate && prevMap) {
    nextOnSaleMap = prevMap;
    nextPendingFinal = prevPending;
  } else if (!prevMap) {
    // 首轮：整表建确认基准，无 pending、不告警
    nextOnSaleMap = currMap;
    nextPendingFinal = {};
  } else {
    nextOnSaleMap = {};
    for (const id of Object.keys(prevMap)) {
      if (delisted.includes(id)) continue;
      if (id in currMap) {
        nextOnSaleMap[id] = currMap[id];
      } else if (ghosts.includes(id)) {
        nextOnSaleMap[id] = prevMap[id];
      }
    }
    for (const id of listed) {
      if (currMap[id]) nextOnSaleMap[id] = currMap[id];
    }
  }

  // 回填 from/to 为真实 next 规模（与事件内一致）
  if (prevMap && !skipUpdate) {
    const realTo = Object.keys(nextOnSaleMap).length;
    const realFrom = Object.keys(prevMap).length;
    for (const ev of events) {
      if (ev.severity === 'alert' && (ev.type === 'delist' || ev.type === 'onshelf')) {
        ev.from = realFrom;
        ev.to = realTo;
      }
    }
  }

  const nextSnap = {
    onSaleMap: nextOnSaleMap,
    pendingOnshelf: nextPendingFinal,
    statusCounts:
      skipUpdate && prevSnap?.statusCounts
        ? prevSnap.statusCounts
        : curr.statusCounts || {},
    onSaleCount: Object.keys(nextOnSaleMap).length,
    allCount:
      skipUpdate && prevAllCount != null
        ? prevAllCount
        : currAllCount || prevAllCount || 0,
    ts: Date.now(),
  };

  return {
    events,
    nextSnap,
    isFirst,
    skipUpdate,
    delistedCount: skipUpdate ? 0 : delisted.length,
    listedCount: skipUpdate ? 0 : listed.length,
    pendingOnshelfCount: Object.keys(nextPendingFinal).length,
    listedRawCount: skipUpdate ? 0 : listedRawCount,
    ghostCount: ghosts.length,
  };
}

export function editLink(editBaseUrl, parentIdOrProductId) {
  const base = String(editBaseUrl || 'https://agentseller.temu.com').replace(/\/$/, '');
  // 后台编辑页参数多为 productId；赛狐 parentId 实测常等于商品父 ID，可点
  return `${base}/goods/edit?from=productList&productId=${parentIdOrProductId}`;
}

/** 单条 SKU 展示行（缩进挂在 SKC 下） */
export function formatSkuSubLine(sku) {
  if (!sku) return '';
  const parts = [];
  if (sku.skuId) parts.push(`SKU ${sku.skuId}`);
  if (sku.specName) parts.push(String(sku.specName).replace(/\s+/g, ' '));
  const code = sku.extCode || sku.commoditySku;
  if (code) parts.push(`货号 ${code}`);
  if (sku.stockQuantity !== '' && sku.stockQuantity != null) {
    parts.push(`库存 ${sku.stockQuantity}`);
  }
  if (sku.name) {
    const nm = String(sku.name).replace(/[[\]]/g, '').slice(0, 24);
    if (nm) parts.push(nm);
  }
  if (!parts.length) return '';
  return `  ◦ ${parts.join(' · ')}`;
}

/**
 * SKC 主行 + 可选 SKU 子行
 * @param {object} it
 * @param {string} [editBaseUrl]
 * @returns {string[]}
 */
export function itemBulletLines(it, editBaseUrl) {
  const nm = String(it.name || '商品').replace(/[[\]]/g, '').slice(0, 36);
  const pid = it.parentId || it.skcId;
  const st = it.selectStatus ? ` status=${it.selectStatus}` : '';
  const lines = [
    `• [${nm}](${editLink(editBaseUrl, pid)})  SKC ${it.skcId || '-'}${st}`,
  ];
  const skus = Array.isArray(it.skus) ? it.skus : [];
  if (!skus.length) {
    // 已尝试补拉但无明细时给一句说明（parentId 缺失则不提）
    if (it.skusAttempted) {
      lines.push('  ◦ _未查到 SKU 明细（getChildInfo 空或失败）_');
    }
    return lines;
  }
  const maxSku = 8;
  for (const s of skus.slice(0, maxSku)) {
    const sub = formatSkuSubLine(s);
    if (sub) lines.push(sub);
  }
  if (skus.length > maxSku) {
    lines.push(`  ◦ _…另有 ${skus.length - maxSku} 个 SKU_`);
  }
  return lines;
}

function itemBullet(it, editBaseUrl) {
  return itemBulletLines(it, editBaseUrl)[0];
}

/**
 * 把 delist / onshelf 告警拼成飞书 lark_md 行
 * @param {string} storeName
 * @param {Array} events
 * @param {{ editBaseUrl?: string }} [opts]
 */
export function formatChangeLines(storeName, events, { editBaseUrl } = {}) {
  const lines = [`**🏬 ${storeName}**（赛狐 OpenAPI · selectStatus=12 · SKU 明细 getChildInfo）`];
  let any = false;
  let fromTo = null;
  let nDelist = 0;
  let nShelf = 0;

  for (const ev of events) {
    if (ev.severity !== 'alert') continue;
    if (ev.type === 'delist' && ev.items?.length) {
      any = true;
      nDelist += ev.items.length;
      if (fromTo == null && ev.from != null && ev.to != null) {
        fromTo = { from: ev.from, to: ev.to };
      }
      lines.push(`📉 在售商品**下架** ${ev.items.length} 个（离开 selectStatus=12）：`);
      for (const it of ev.items.slice(0, 40)) {
        lines.push(...itemBulletLines(it, editBaseUrl));
      }
      if (ev.items.length > 40) lines.push(`_…另有 ${ev.items.length - 40} 个未列出_`);
    }
    if (ev.type === 'onshelf' && ev.items?.length) {
      any = true;
      nShelf += ev.items.length;
      if (fromTo == null && ev.from != null && ev.to != null) {
        fromTo = { from: ev.from, to: ev.to };
      }
      lines.push(
        `📈 在售商品**上架** ${ev.items.length} 个（连续两轮 selectStatus=12，已确认）：`,
      );
      for (const it of ev.items.slice(0, 40)) {
        lines.push(...itemBulletLines(it, editBaseUrl));
      }
      if (ev.items.length > 40) lines.push(`_…另有 ${ev.items.length - 40} 个未列出_`);
    }
  }
  if (!any) {
    lines.push('_本轮无上下架_');
  } else if (fromTo) {
    const parts = [];
    if (nDelist) parts.push(`−${nDelist}`);
    if (nShelf) parts.push(`+${nShelf}`);
    const detail = parts.length ? parts.join(' ') : '';
    lines.push(
      `📊 赛狐确认在售：**${fromTo.from} → ${fromTo.to}**` +
        (detail ? `（${detail}` : '（') +
        `；以赛狐为准，可能与卖家后台「在售中」略有延迟）`,
    );
  }
  lines.push(
    '',
    `_检查时间：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}_`,
  );
  return lines;
}

/** @deprecated 用 formatChangeLines；保留别名避免外部引用断裂 */
export function formatDelistLines(storeName, events, opts) {
  return formatChangeLines(storeName, events, opts);
}

/**
 * 飞书卡片颜色：仅下架 red；仅上架 green；混合 orange
 * @param {Array} events
 */
export function alertTemplate(events) {
  const types = new Set(
    (events || []).filter((e) => e.severity === 'alert').map((e) => e.type),
  );
  const hasD = types.has('delist');
  const hasO = types.has('onshelf');
  if (hasD && hasO) return 'orange';
  if (hasO) return 'green';
  return 'red';
}

export function alertTitle(events) {
  const types = new Set(
    (events || []).filter((e) => e.severity === 'alert').map((e) => e.type),
  );
  const hasD = types.has('delist');
  const hasO = types.has('onshelf');
  if (hasD && hasO) return '🔔 Temu 在售变动（赛狐）';
  if (hasO) return '🔔 Temu 上架监测（赛狐）';
  return '🔔 Temu 下架监测（赛狐）';
}
