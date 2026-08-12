/**
 * 开放平台快照 diff：下架 / 新进低流量 / 新进限流
 * 规则对齐插件：
 *  - 首轮只有基准不告警
 *  - 空扫 / 明显残缺不更新在售基准（防误报）
 */

/**
 * @param {object} prev snapshot
 * @param {object} curr { activeMap, lowTrafficMap, restrictedMap, counts }
 * @param {object} alerts { delist, lowTraffic, restrictedTraffic }
 */
export function diffCatalog(prev, curr, alerts = {}) {
  const events = [];
  const prevActive = (prev && prev.activeMap) || null;
  const prevLow = (prev && prev.lowTrafficMap) || null;
  const prevRes = (prev && prev.restrictedMap) || null;

  const currActive = curr.activeMap || {};
  const currLow = curr.lowTrafficMap || {};
  const currRes = curr.restrictedMap || {};

  const activeIds = Object.keys(currActive);
  // 防残缺：若已有基准且本轮在售数 < 基准的 50% 且基准≥10，视为扫不全，跳过下架 diff 且不更新 active 基准
  let skipDelistUpdate = false;
  if (prevActive) {
    const prevN = Object.keys(prevActive).length;
    const currN = activeIds.length;
    if (prevN >= 10 && currN < Math.floor(prevN * 0.5)) {
      skipDelistUpdate = true;
      events.push({
        type: 'scan_incomplete',
        severity: 'warn',
        message: `在售扫描疑似不全：基准 ${prevN} → 本轮 ${currN}，跳过下架判定`,
      });
    }
  }

  // —— 下架：上轮在售、本轮不在
  if (alerts.delist !== false && prevActive && !skipDelistUpdate) {
    const delisted = Object.keys(prevActive).filter((id) => !(id in currActive));
    if (delisted.length) {
      events.push({
        type: 'delist',
        severity: 'alert',
        items: delisted.map((id) => ({
          goodsId: id,
          name: prevActive[id]?.name || '',
        })),
        from: Object.keys(prevActive).length,
        to: activeIds.length,
      });
    }
  }

  // —— 新进低流量
  if (alerts.lowTraffic !== false && prevLow) {
    const added = Object.keys(currLow).filter((id) => !(id in prevLow));
    if (added.length) {
      events.push({
        type: 'low_traffic',
        severity: 'alert',
        items: added.map((id) => ({
          goodsId: id,
          name: currLow[id]?.name || currActive[id]?.name || '',
        })),
        from: Object.keys(prevLow).length,
        to: Object.keys(currLow).length,
      });
    }
  }

  // —— 新进限流
  if (alerts.restrictedTraffic !== false && prevRes) {
    const added = Object.keys(currRes).filter((id) => !(id in prevRes));
    if (added.length) {
      events.push({
        type: 'restricted_traffic',
        severity: 'alert',
        items: added.map((id) => ({
          goodsId: id,
          name: currRes[id]?.name || currActive[id]?.name || '',
        })),
        from: Object.keys(prevRes).length,
        to: Object.keys(currRes).length,
      });
    }
  }

  const isFirst = !prevActive;
  const nextSnap = {
    activeMap: skipDelistUpdate && prevActive ? prevActive : currActive,
    lowTrafficMap: currLow,
    restrictedMap: currRes,
    counts: curr.counts || {
      active: activeIds.length,
      lowTraffic: Object.keys(currLow).length,
      restricted: Object.keys(currRes).length,
    },
    ts: Date.now(),
  };

  return { events, nextSnap, isFirst, skipDelistUpdate };
}

export function editLink(editBaseUrl, goodsId) {
  const base = String(editBaseUrl || 'https://agentseller.temu.com').replace(/\/$/, '');
  // 与插件一致：SPU/productId 编辑页；OpenAPI goodsId 需实测是否同一 ID
  return `${base}/goods/edit?from=productList&productId=${goodsId}`;
}

export function formatAlertLines(storeName, events, { editBaseUrl } = {}) {
  const lines = [`**🏬 ${storeName}**（OpenAPI）`];
  for (const ev of events) {
    if (ev.severity !== 'alert') continue;
    if (ev.type === 'delist') {
      lines.push(`📉 在售商品下架 ${ev.items.length} 个（在售 ${ev.from} → ${ev.to}）：`);
      for (const it of ev.items.slice(0, 30)) {
        const nm = String(it.name || '商品').replace(/[[\]]/g, '').slice(0, 30);
        lines.push(`• [${nm}](${editLink(editBaseUrl, it.goodsId)})  ID ${it.goodsId}`);
      }
      if (ev.items.length > 30) lines.push(`_…另有 ${ev.items.length - 30} 个未列出_`);
    } else if (ev.type === 'low_traffic') {
      lines.push(`⚠️ 低流量商品新增 ${ev.items.length} 个（${ev.from} → ${ev.to}）：`);
      for (const it of ev.items.slice(0, 30)) {
        const nm = String(it.name || '商品').replace(/[[\]]/g, '').slice(0, 30);
        lines.push(`• [${nm}](${editLink(editBaseUrl, it.goodsId)})  ID ${it.goodsId}`);
      }
    } else if (ev.type === 'restricted_traffic') {
      lines.push(`🔴 限流商品新增 ${ev.items.length} 个（${ev.from} → ${ev.to}）：`);
      for (const it of ev.items.slice(0, 30)) {
        const nm = String(it.name || '商品').replace(/[[\]]/g, '').slice(0, 30);
        lines.push(`• [${nm}](${editLink(editBaseUrl, it.goodsId)})  ID ${it.goodsId}`);
      }
    }
  }
  lines.push('', `_检查时间：${new Date().toLocaleString('zh-CN')}_`);
  return lines;
}
