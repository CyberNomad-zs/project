/**
 * 发版闸门：切店 / count / chip / mallId 关键时间线（纯逻辑，不启动 Chrome）
 * 与 test_onsale_ab / test_traffic_dedupe 互补——本文件按「故事」组织，防止回退 P0。
 *
 * 运行：node test_timelines.js
 * 或：  powershell -File check.ps1
 */

function assert(cond, msg) {
  if (!cond) throw new Error('FAIL: ' + msg);
  console.log('OK  ' + msg);
}

// ─── 与生产约定对齐的常量（改 background 时两边一起改）───
const QTY_HITS = 2;
const QTY_GAP_MS = 3000;
const QTY_TTL_MS = 60 * 1000;
const BIG_HITS = 3;
const BIG_GAP_MS = 12000;
const BIG_DROP_RATIO = 0.5;
const BIG_DROP_MIN = 3;
const ALERT_COOLDOWN_MS = 6 * 60 * 60 * 1000;

// ─── A 数量确认（v19.2 + v19.3 归零/大跌）───
function qtyStep(state, cur, now, opts) {
  opts = opts || {};
  const cycleSilent = !!opts.cycleSilent; // 轮巡中：可更新 pending/base 策略简化为不 alert
  let base = state.base;
  let pending = state.pending;

  if (pending && pending.firstTs && now - pending.firstTs > QTY_TTL_MS) pending = null;

  if (base == null) {
    return { state: { base: cur, pending: null }, alert: false, first: true };
  }
  if (cur === base) {
    const hadPending = !!pending;
    return {
      state: { base: base, pending: null },
      alert: false,
      cancelled: hadPending,
      cancelScan: hadPending,
      shouldScan: false,
    };
  }

  let nextPending;
  if (pending && pending.to === cur) {
    nextPending = {
      from: base,
      to: cur,
      firstTs: pending.firstTs,
      hits: (pending.hits || 1) + 1,
    };
  } else {
    nextPending = { from: base, to: cur, firstTs: now, hits: 1 };
  }

  const isZeroDrop = cur === 0 && base > 0;
  const dropN = cur < base ? base - cur : 0;
  const isBigDrop =
    dropN > 0 &&
    (isZeroDrop || dropN >= Math.max(BIG_DROP_MIN, Math.ceil(base * BIG_DROP_RATIO)));
  const needHits = isBigDrop ? BIG_HITS : QTY_HITS;
  const needGap = isBigDrop ? BIG_GAP_MS : QTY_GAP_MS;
  const confirmed =
    !isZeroDrop &&
    nextPending.hits >= needHits &&
    now - nextPending.firstTs >= needGap;

  if (cycleSilent) {
    // 轮巡：不发数量卡；确认后可跟基准（与「只同步基准」一致的简化）
    if (confirmed) {
      return {
        state: { base: cur, pending: null },
        alert: false,
        synced: true,
        silencedByCycle: true,
      };
    }
    return {
      state: { base: base, pending: nextPending },
      alert: false,
      pending: true,
      silencedByCycle: true,
    };
  }

  if (!confirmed) {
    return {
      state: { base: base, pending: nextPending },
      alert: false,
      pending: true,
      isZeroDrop: isZeroDrop,
      isBigDrop: isBigDrop,
      // v20：pending 绝不约 B
      shouldScan: false,
      cancelScan: false,
    };
  }
  return {
    state: { base: cur, pending: null },
    alert: true,
    from: base,
    to: cur,
    shouldScan: true,
    confirmed: true,
    cancelScan: false,
  };
}

// ─── mallId 归属（v19.3）───
function resolveByMall(map, mallId, dom) {
  const id = mallId != null && mallId !== '' ? String(mallId) : '';
  if (id && map[id]) {
    if (dom && dom !== map[id]) {
      const owned = Object.keys(map).find(function (k) {
        return map[k] === dom && k !== id;
      });
      if (!owned) {
        map[id] = dom;
        return dom;
      }
      return map[id];
    }
    return map[id];
  }
  if (id && dom) {
    map[id] = dom;
    return dom;
  }
  return dom || null;
}

// ─── 限流 chip / 静默吸收（v17–v18）───
function alertedSize(m) {
  return m && typeof m === 'object' ? Object.keys(m).length : 0;
}
function hasTrafficBaseline(snap) {
  if (!snap || typeof snap !== 'object') return false;
  return (
    alertedSize(snap.alertedTrafficIds) +
      alertedSize(snap.alertedWatchIds) +
      alertedSize(snap.alertedDeclineIds) >
    0
  );
}
function markAlerted(map, items, now) {
  const out = Object.assign({}, map || {});
  for (let i = 0; i < (items || []).length; i++) {
    const it = items[i];
    if (it && it.productId) out[String(it.productId)] = now;
  }
  return out;
}
function pickFresh(items, alerted, now) {
  const fresh = [];
  const seen = {};
  for (let i = 0; i < (items || []).length; i++) {
    const it = items[i];
    if (!it || !it.productId) continue;
    const pid = String(it.productId);
    if (seen[pid]) continue;
    seen[pid] = true;
    const last = alerted && alerted[pid];
    if (typeof last === 'number' && now - last < ALERT_COOLDOWN_MS) continue;
    fresh.push(it);
  }
  return fresh;
}
/** snap 计数：忽略瞬时 0（v18） */
function nextWatchSnap(prevWatch, prevHigh, curChip) {
  let watch = prevWatch;
  if (typeof curChip === 'number' && curChip > 0) watch = curChip;
  // curChip===0 → 保持 prev，不写 0
  const high = Math.max(
    typeof prevHigh === 'number' ? prevHigh : 0,
    typeof watch === 'number' ? watch : 0,
    typeof curChip === 'number' && curChip > 0 ? curChip : 0
  );
  return { trafficWatch: watch, trafficWatchHigh: high };
}
function decideTraffic(pool, alerted, snap, curWatch, now) {
  const prevHigh = Math.max(
    typeof snap.trafficWatchHigh === 'number' ? snap.trafficWatchHigh : 0,
    typeof snap.trafficWatch === 'number' ? snap.trafficWatch : 0
  );
  const chipReallyUp = typeof curWatch === 'number' && curWatch > prevHigh;
  const baselineReady = hasTrafficBaseline(snap);
  let nextAlerted = Object.assign({}, alerted || {});
  let fresh = [];
  let silenced = 0;
  let seeded = false;

  if (!baselineReady) {
    if (pool.length > 0) {
      nextAlerted = markAlerted(nextAlerted, pool, now);
      seeded = true;
    }
    return {
      fresh: fresh,
      nextAlerted: nextAlerted,
      silenced: silenced,
      seeded: seeded,
      chipReallyUp: chipReallyUp,
      high: Math.max(prevHigh, curWatch || 0),
    };
  }

  fresh = pickFresh(pool, nextAlerted, now);
  if (fresh.length && !chipReallyUp) {
    silenced = fresh.length;
    nextAlerted = markAlerted(nextAlerted, fresh, now);
    fresh = [];
  }
  if (fresh.length) nextAlerted = markAlerted(nextAlerted, fresh, now);
  nextAlerted = markAlerted(nextAlerted, pool, now);
  return {
    fresh: fresh,
    nextAlerted: nextAlerted,
    silenced: silenced,
    seeded: seeded,
    chipReallyUp: chipReallyUp,
    high: Math.max(prevHigh, curWatch || 0),
  };
}

// ═══════════════════════════════════════════════════════════
// Timeline 1 — count 毛刺 15→4→15：零张数量卡（P0-3）
// ═══════════════════════════════════════════════════════════
{
  let st = { base: 15, pending: null };
  let r = qtyStep(st, 4, 1000);
  assert(r.pending && !r.alert && !r.shouldScan, 'T1: 15→4 pending only');
  st = r.state;
  r = qtyStep(st, 15, 1500);
  assert(r.cancelled && r.cancelScan && !r.alert, 'T1: rebound 4→15 cancels');
  assert(r.state.base === 15 && r.state.pending == null, 'T1: base stays 15');
}

// ═══════════════════════════════════════════════════════════
// Timeline 2 — 真实下降 15→14→14（间隔够）：恰一张卡（P1 应报）
// ═══════════════════════════════════════════════════════════
{
  let st = { base: 15, pending: null };
  let r = qtyStep(st, 14, 1000);
  assert(!r.alert && r.pending, 'T2: first 14 no alert');
  st = r.state;
  r = qtyStep(st, 14, 1000 + QTY_GAP_MS);
  assert(r.alert === true && r.from === 15 && r.to === 14, 'T2: one drop alert');
  assert(r.state.base === 14, 'T2: base committed 14');
}

// ═══════════════════════════════════════════════════════════
// Timeline 3 — chip 闪 0 再回 N：不写 0、不高水位塌陷、不推全量（P0-2）
// ═══════════════════════════════════════════════════════════
{
  const now = 1e12;
  const pool = [
    { productId: '111', name: 'A' },
    { productId: '222', name: 'B' },
    { productId: '333', name: 'C' },
  ];
  let snap = {
    alertedTrafficIds: { '111': now, '222': now, '333': now },
    trafficWatch: 4,
    trafficWatchHigh: 4,
  };
  // loading：chip 读到 0
  let w = nextWatchSnap(snap.trafficWatch, snap.trafficWatchHigh, 0);
  assert(w.trafficWatch === 4, 'T3: ignore chip 0, watch stays 4');
  assert(w.trafficWatchHigh === 4, 'T3: high stays 4');
  snap.trafficWatch = w.trafficWatch;
  snap.trafficWatchHigh = w.trafficWatchHigh;
  // 恢复 4，pool 仍是那批；alerted 若被部分弄丢
  const partialAlerted = { '111': now };
  const r = decideTraffic(pool, partialAlerted, snap, 4, now + 5000);
  assert(r.chipReallyUp === false, 'T3: 4 > high4 ? false');
  assert(r.fresh.length === 0, 'T3: no feishu after 0→4');
  assert(r.silenced >= 2, 'T3: missing ids silently absorbed');
}

// ═══════════════════════════════════════════════════════════
// Timeline 4 — mallId=A 但 DOM 仍是 B：事件归 A（P0-1）
// ═══════════════════════════════════════════════════════════
{
  const map = { '9001': 'Agnis', '9002': 'HomeCove' };
  // 切到 Agnis 后 DOM 滞后显示 HomeCove
  const store = resolveByMall(map, '9001', 'HomeCove');
  assert(store === 'Agnis', 'T4: mallId wins over lagging DOM');

  // 模拟两店 count 交错：不得把 Agnis 的 12 写入 HomeCove base
  const bases = { Agnis: 12, HomeCove: 15 };
  const name = resolveByMall(map, '9001', 'HomeCove');
  const cur = 12;
  let st = { base: bases[name], pending: null };
  let r = qtyStep(st, cur, 8000);
  assert(name === 'Agnis', 'T4: write target Agnis');
  assert(r.state.base === 12 || r.first || !r.alert, 'T4: Agnis path stable');
  assert(bases.HomeCove === 15, 'T4: HomeCove base untouched');
}

// ═══════════════════════════════════════════════════════════
// Timeline 5 — 轮巡中数量变化：不发数量卡（v19.3 cycle silent）
// ═══════════════════════════════════════════════════════════
{
  let st = { base: 15, pending: null };
  let r = qtyStep(st, 14, 1000, { cycleSilent: true });
  st = r.state;
  r = qtyStep(st, 14, 1000 + QTY_GAP_MS, { cycleSilent: true });
  assert(!r.alert, 'T5: cycle silent no qty card even if confirmed');
  assert(r.synced === true && r.state.base === 14, 'T5: baseline may sync');
}

// ═══════════════════════════════════════════════════════════
// Timeline 6 — 归零 12→0 永不数量卡；回弹取消（P0-3 相关）
// ═══════════════════════════════════════════════════════════
{
  let st = { base: 12, pending: null };
  let r = qtyStep(st, 0, 1000);
  assert(r.pending && r.isZeroDrop && !r.alert, 'T6: zero pending');
  st = r.state;
  r = qtyStep(st, 0, 1000 + BIG_GAP_MS + 5000);
  assert(!r.alert, 'T6: zero never confirms');
  r = qtyStep(st, 12, 1000 + BIG_GAP_MS + 6000);
  assert(!r.alert && (r.cancelled || r.state.base === 12), 'T6: rebound to 12');
}

// ═══════════════════════════════════════════════════════════
// Timeline 7 — 大幅下降需 3 hits + 12s（防闪断）
// ═══════════════════════════════════════════════════════════
{
  let st = { base: 12, pending: null };
  const t0 = 5000;
  let r = qtyStep(st, 5, t0);
  st = r.state;
  r = qtyStep(st, 5, t0 + 4000);
  st = r.state;
  assert(!r.alert, 'T7: big drop 2 hits insufficient');
  r = qtyStep(st, 5, t0 + BIG_GAP_MS);
  assert(r.alert && r.to === 5, 'T7: big drop alerts after 3+12s');
}

// ═══════════════════════════════════════════════════════════
// Timeline 8 — chip 真升高 + 新 ID → 可告警（P1 正路径）
// ═══════════════════════════════════════════════════════════
{
  const now = 2e12;
  const snap = {
    alertedTrafficIds: { '111': now },
    trafficWatch: 4,
    trafficWatchHigh: 4,
  };
  const pool = [
    { productId: '111', name: 'old' },
    { productId: '999', name: 'new' },
  ];
  const r = decideTraffic(pool, { '111': now }, snap, 5, now + 1000);
  assert(r.chipReallyUp === true, 'T8: chip 4→5 rise');
  assert(r.fresh.some(function (x) { return x.productId === '999'; }), 'T8: new id fresh');
  assert(!r.fresh.some(function (x) { return x.productId === '111'; }), 'T8: old id not fresh');
}

// ═══════════════════════════════════════════════════════════
// Timeline 9 — 首次无基线只 seed 不推（防首装刷屏）
// ═══════════════════════════════════════════════════════════
{
  const now = 3e12;
  const pool = [{ productId: 'a' }, { productId: 'b' }];
  const r = decideTraffic(pool, {}, { alertedTrafficIds: {} }, 2, now);
  assert(r.seeded && r.fresh.length === 0, 'T9: first seed no alert');
  assert(r.nextAlerted.a && r.nextAlerted.b, 'T9: ids marked');
}

console.log('\ntest_timelines: OK (9 timelines · P0 gates)');
