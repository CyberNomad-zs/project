import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from './config.js';
import { itemLines } from './alertFormat.js';

const STATE_FILE = resolve(ROOT, 'data', 'state.json');

export function loadState() {
  try {
    return JSON.parse(readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return { stores: {} };
  }
}

export function saveState(state) {
  mkdirSync(resolve(ROOT, 'data'), { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}

/**
 * 对比本次扫描与快照，产出告警事件（含商品明细行）
 * @param {object} prev
 * @param {object} curr scanStore 结果
 * @param {object} alertsCfg
 * @param {{ editBaseUrl?: string, skipOnSaleDrop?: boolean }} [opts]
 *   skipOnSaleDrop：下架点名已由赛狐负责时，可跳过「仅数字」在售下降，避免双报
 */
export function diffStore(prev, curr, alertsCfg, opts = {}) {
  const events = [];
  const editBase = opts.editBaseUrl || 'https://agentseller.temu.com';

  // 在售数量下降（数字）；完整下架点名优先走赛狐
  if (
    !opts.skipOnSaleDrop &&
    alertsCfg.onSaleDrop &&
    prev &&
    typeof prev.onSaleCount === 'number' &&
    typeof curr.onSaleCount === 'number' &&
    curr.onSaleCount < prev.onSaleCount
  ) {
    events.push({
      type: 'onSaleDrop',
      text: `在售商品数量下降：${prev.onSaleCount} → ${curr.onSaleCount}（减少 ${prev.onSaleCount - curr.onSaleCount} 件）`,
    });
  }

  if (alertsCfg.trafficAnomaly !== false) {
    const prevWatch = prev?.trafficWatchCount;
    const currWatch = curr.trafficWatchCount;
    if (
      typeof prevWatch === 'number' &&
      typeof currWatch === 'number' &&
      currWatch > prevWatch
    ) {
      const lines = [
        `「商品流量待关注」增加：${prevWatch} → ${currWatch}（+${currWatch - prevWatch}）`,
        ...itemLines(curr.watchItems, currWatch, editBase),
      ];
      events.push({ type: 'trafficWatch', text: lines.join('\n') });
    }

    // 近期下降：数字增加（插件 v 后）或 布尔从无到有
    const prevDec = prev?.trafficDeclineCount;
    const currDec = curr.trafficDeclineCount;
    if (
      typeof prevDec === 'number' &&
      typeof currDec === 'number' &&
      currDec > prevDec
    ) {
      const lines = [
        `「商品流量近期有下降」增加：${prevDec} → ${currDec}（本页可见徽标）`,
        ...itemLines(curr.declineItems, null, editBase),
      ];
      events.push({ type: 'trafficDecline', text: lines.join('\n') });
    } else if (
      prev &&
      curr.trafficDeclineExists &&
      !prev.trafficDeclineExists
    ) {
      // 必须有过基准：首轮 prev 为空只建快照，不报「从无到有」
      const lines = [
        '出现「商品流量近期有下降」商品，请及时处理。',
        ...itemLines(curr.declineItems, null, editBase),
      ];
      events.push({ type: 'trafficDecline', text: lines.join('\n') });
    }
  }

  return events;
}

/** 合并写入快照（null 轮 carry） */
export function mergeSnapshot(prev, result) {
  const carry = (cur, key) =>
    cur == null && prev && typeof prev[key] === 'number' ? prev[key] : cur;
  return {
    onSaleCount: carry(result.onSaleCount, 'onSaleCount'),
    trafficWatchCount: carry(result.trafficWatchCount, 'trafficWatchCount'),
    trafficDeclineCount: carry(result.trafficDeclineCount, 'trafficDeclineCount'),
    trafficDeclineExists: !!result.trafficDeclineExists,
    trafficAnomalyTotal:
      (carry(result.trafficWatchCount, 'trafficWatchCount') ?? 0) +
      (carry(result.trafficDeclineCount, 'trafficDeclineCount') ?? 0),
    watchItems: Array.isArray(result.watchItems) ? result.watchItems : prev?.watchItems || [],
    declineItems: Array.isArray(result.declineItems)
      ? result.declineItems
      : prev?.declineItems || [],
    updatedAt: new Date().toISOString(),
  };
}
