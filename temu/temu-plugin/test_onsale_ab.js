/**
 * v19 A+B 在售 diff 纯逻辑自测（不启动 Chrome）
 * node test_onsale_ab.js
 */
function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'assert failed');
}

// —— 复制 background 中的核心判定（保持与实现一致）——
const TRUE_ZERO_HITS = 2;
const TRUE_ZERO_VS_COUNT_MS = 2 * 60 * 1000;

/**
 * computeDiff：清单 diff + v19.4 trueZero 二次确认
 * @param prevMap
 * @param prevPending
 * @param items
 * @param onSaleTabCount
 * @param opts {{ pendingTrueZero?, onSaleCount?, onSaleCountTs?, now? }}
 */
function computeDiff(prevMap, prevPending, items, onSaleTabCount, opts) {
  opts = opts || {};
  const now = typeof opts.now === 'number' ? opts.now : Date.now();
  const looksZero = typeof onSaleTabCount === 'number' && onSaleTabCount === 0 && items.length === 0;
  if (!Array.isArray(items)) return { aborted: true };
  if (!items.length && !looksZero) return { aborted: true, reason: 'empty' };

  const known = typeof onSaleTabCount === 'number' && onSaleTabCount >= 0 ? onSaleTabCount : null;
  if (known != null && known > 0 && items.length < known) return { aborted: true, reason: 'incomplete' };
  if (known != null && items.length > known) return { aborted: true, reason: 'overflow' };

  // v19.4 trueZero 护栏
  let pendingTZ = opts.pendingTrueZero || null;
  if (looksZero) {
    const cnt = typeof opts.onSaleCount === 'number' ? opts.onSaleCount : null;
    const cntTs = typeof opts.onSaleCountTs === 'number' ? opts.onSaleCountTs : 0;
    if (cnt != null && cnt > 0 && cntTs && (now - cntTs) < TRUE_ZERO_VS_COUNT_MS) {
      return { aborted: true, reason: 'trueZero-vs-count', pendingTrueZero: null };
    }
    const hits = (pendingTZ && pendingTZ.hits ? pendingTZ.hits : 0) + 1;
    const firstTs = (pendingTZ && pendingTZ.firstTs) || now;
    if (hits < TRUE_ZERO_HITS) {
      return {
        aborted: true,
        reason: 'trueZero-pending',
        pendingTrueZero: { hits: hits, firstTs: firstTs, lastTs: now },
      };
    }
    // 确认，放行 diff
    pendingTZ = null;
  } else if (pendingTZ) {
    pendingTZ = null; // 非零扫描取消
  }

  const newMap = {};
  for (const it of items) {
    if (it && it.productId) newMap[String(it.productId)] = { name: it.name || '', skc: it.skc || '', productId: String(it.productId) };
  }

  if (!prevMap) {
    return { first: true, onSaleIds: newMap, pending: {}, delisted: [], listed: [], pendingTrueZero: null };
  }

  const rawDelisted = Object.keys(prevMap).filter((pid) => !(pid in newMap));
  const confirmedListed = [];
  for (const pid of Object.keys(prevPending || {})) {
    if (pid in newMap) confirmedListed.push(pid);
  }
  const listedSet = new Set(confirmedListed);
  const nextPending = {};
  for (const pid of Object.keys(newMap)) {
    if (pid in prevMap) continue;
    if (listedSet.has(pid)) continue;
    nextPending[pid] = { productId: pid, name: newMap[pid].name, skc: newMap[pid].skc };
  }
  const nextOnSale = {};
  for (const pid of Object.keys(prevMap)) {
    if (pid in newMap) nextOnSale[pid] = newMap[pid];
  }
  for (const pid of confirmedListed) nextOnSale[pid] = newMap[pid];

  return {
    first: false,
    delisted: rawDelisted,
    listed: confirmedListed,
    pending: nextPending,
    onSaleIds: nextOnSale,
    pendingTrueZero: null,
  };
}

// 1) 首轮建基
{
  const r = computeDiff(null, {}, [{ productId: 'A', name: 'a' }], 1);
  assert(r.first && r.onSaleIds.A, 'first baseline');
}

// 2) 下架点名
{
  const prev = { A: { name: '茶蜡', skc: '1' }, B: { name: 'x', skc: '2' } };
  const r = computeDiff(prev, {}, [{ productId: 'B', name: 'x' }], 1);
  assert(!r.first && r.delisted.length === 1 && r.delisted[0] === 'A', 'delist A');
  assert(!r.pending.A && r.onSaleIds.B, 'B remains');
}

// 3) 真清零：需连续 2 次（v19.4）
{
  const prev = { A: { name: '茶蜡', skc: '7636599333' } };
  const r1 = computeDiff(prev, {}, [], 0, { now: 1000 });
  assert(r1.aborted && r1.reason === 'trueZero-pending', 'true zero hit1 pending');
  assert(r1.pendingTrueZero && r1.pendingTrueZero.hits === 1, 'pending hits=1');
  const r2 = computeDiff(prev, {}, [], 0, { pendingTrueZero: r1.pendingTrueZero, now: 7000 });
  assert(!r2.aborted && r2.delisted.length === 1 && r2.delisted[0] === 'A', 'true zero hit2 delist');
  assert(Object.keys(r2.onSaleIds).length === 0, 'empty baseline after zero');
}

// 3b) 单次 trueZero 不点名（Agnis 日志回归）
{
  const prev = {};
  for (let i = 0; i < 12; i++) prev['p' + i] = { name: 'x' + i };
  const r = computeDiff(prev, {}, [], 0, { now: 1000 });
  assert(r.aborted && r.reason === 'trueZero-pending', 'single trueZero no delist');
  assert(r.delisted === undefined, 'no delisted on pending');
}

// 3c) 近 2min 内 countStatus>0 → 拒绝 trueZero
{
  const prev = { A: { name: 'a' } };
  const r = computeDiff(prev, {}, [], 0, {
    now: 10000,
    onSaleCount: 12,
    onSaleCountTs: 10000 - 30 * 1000, // 30s ago
  });
  assert(r.aborted && r.reason === 'trueZero-vs-count', 'reject trueZero vs recent count');
}

// 3d) trueZero pending 后非零扫描取消
{
  const prev = { A: { name: 'a' }, B: { name: 'b' } };
  const r1 = computeDiff(prev, {}, [], 0, { now: 1000 });
  assert(r1.reason === 'trueZero-pending', 'pending first');
  const r2 = computeDiff(prev, {}, [{ productId: 'A' }, { productId: 'B' }], 2, {
    pendingTrueZero: r1.pendingTrueZero,
    now: 5000,
  });
  assert(!r2.aborted && r2.delisted.length === 0, 'non-zero cancels trueZero, no delist');
  assert(r2.pendingTrueZero == null, 'pending cleared');
}

// 4) 空扫描但非权威 0 → 放弃
{
  const prev = { A: { name: 'a' } };
  const r = computeDiff(prev, {}, [], null);
  assert(r.aborted, 'empty abort');
}

// 5) 上架二次确认
{
  const prev = { A: { name: 'a' } };
  const r1 = computeDiff(prev, {}, [{ productId: 'A', name: 'a' }, { productId: 'C', name: 'new' }], 2);
  assert(r1.listed.length === 0 && r1.pending.C, 'C pending first seen');
  assert(!r1.onSaleIds.C, 'C not in committed yet');
  const r2 = computeDiff(r1.onSaleIds, r1.pending, [{ productId: 'A', name: 'a' }, { productId: 'C', name: 'new' }], 2);
  assert(r2.listed.length === 1 && r2.listed[0] === 'C', 'C confirmed second round');
  assert(r2.onSaleIds.C, 'C in baseline');
  assert(!r2.pending.C, 'C left pending');
}

// 6) 上架抖动：pending 后消失
{
  const prev = { A: { name: 'a' } };
  const r1 = computeDiff(prev, {}, [{ productId: 'A' }, { productId: 'C' }], 2);
  const r2 = computeDiff(r1.onSaleIds, r1.pending, [{ productId: 'A' }], 1);
  assert(r2.listed.length === 0 && !r2.pending.C, 'jitter dropped');
}

// 7) 扫不全
{
  const prev = { A: {}, B: {} };
  const r = computeDiff(prev, {}, [{ productId: 'A' }], 2);
  assert(r.aborted && r.reason === 'incomplete', 'incomplete');
}

// 8) 数量 A 逻辑（旧：立即判定）
function qtyDecision(prev, cur) {
  if (prev == null) return { first: true, shouldScan: false };
  if (prev === cur) return { dropped: 0, rose: 0, shouldScan: false };
  const dropped = cur < prev ? prev - cur : 0;
  const rose = cur > prev ? cur - prev : 0;
  return { dropped, rose, shouldScan: dropped > 0 || rose > 0, from: prev, to: cur };
}
assert(qtyDecision(null, 13).first, 'qty first');
assert(qtyDecision(1, 0).dropped === 1 && qtyDecision(1, 0).shouldScan, '1→0');
assert(qtyDecision(13, 14).rose === 1, 'rise');
assert(!qtyDecision(5, 5).shouldScan, 'same');

// 9) v19.2/v20 数量防抖：纯状态机（与 background.diffOnSaleCount 对齐）
// v20：pending 时 shouldScan=false；仅 confirmed 才约 B；rebound → cancelScan
const QTY_HITS = 2;
const QTY_GAP_MS = 3000;
const QTY_TTL_MS = 60 * 1000;

function qtyConfirmStep(state, cur, now) {
  // state: { base, pending: null|{from,to,firstTs,hits} }
  let { base, pending } = state;
  if (pending && pending.firstTs && now - pending.firstTs > QTY_TTL_MS) pending = null;

  if (base == null) {
    return {
      state: { base: cur, pending: null },
      alert: false,
      shouldScan: false,
      confirmed: false,
      cancelScan: false,
      first: true,
    };
  }
  if (cur === base) {
    const hadPending = !!pending;
    return {
      state: { base, pending: null },
      alert: false,
      shouldScan: false,
      confirmed: false,
      cancelled: hadPending,
      cancelScan: hadPending,
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

  const confirmed = nextPending.hits >= QTY_HITS && (now - nextPending.firstTs) >= QTY_GAP_MS;
  if (!confirmed) {
    return {
      state: { base, pending: nextPending },
      alert: false,
      // v20：pending 绝不约 B
      shouldScan: false,
      confirmed: false,
      pending: true,
      cancelScan: false,
    };
  }
  return {
    state: { base: cur, pending: null },
    alert: true,
    shouldScan: true,
    confirmed: true,
    cancelScan: false,
    from: base,
    to: cur,
  };
}

// schedule 模拟：仅 confirmed&&shouldScan 武装；cancelScan 拆除
function applySchedule(armed, r) {
  if (r.cancelScan) return false;
  if (r.confirmed && r.shouldScan) return true;
  return armed;
}

// 9a) 切店毛刺 15→4→15：不告警、不约 B、rebound 取消
{
  let st = { base: 15, pending: null };
  let armed = false;
  let r = qtyConfirmStep(st, 4, 1000);
  assert(r.pending && !r.alert && !r.shouldScan, '15→4 pending no scan');
  armed = applySchedule(armed, r);
  assert(!armed, 'pending does not arm B');
  st = r.state;
  r = qtyConfirmStep(st, 15, 1001);
  assert(r.cancelled && r.cancelScan && !r.alert && st.base === 15, '4→15 rebound cancelScan');
  armed = applySchedule(armed, r);
  assert(!armed, 'rebound keeps B disarmed');
  assert(r.state.pending == null && r.state.base === 15, 'base stays 15');
}

// 9b) 真实下降：两次且 ≥3s 才告警，且确认后才 shouldScan
{
  let st = { base: 15, pending: null };
  let armed = false;
  let r = qtyConfirmStep(st, 14, 1000);
  assert(r.pending && !r.alert && !r.shouldScan, 'first hit no alert no scan');
  armed = applySchedule(armed, r);
  assert(!armed, 'first hit not armed');
  st = r.state;
  // 同值但间隔不够
  r = qtyConfirmStep(st, 14, 2000);
  assert(r.pending && !r.alert && !r.shouldScan && r.state.pending.hits === 2, 'second hit gap short no scan');
  armed = applySchedule(armed, r);
  assert(!armed, 'gap short not armed');
  st = r.state;
  // 间隔够
  r = qtyConfirmStep(st, 14, 1000 + QTY_GAP_MS);
  assert(r.alert && r.confirmed && r.shouldScan && r.from === 15 && r.to === 14, 'confirmed drop scans');
  armed = applySchedule(armed, r);
  assert(armed, 'confirmed arms B');
  assert(r.state.base === 14 && r.state.pending == null, 'base updated');
}

// 9c) 候选改道：4→3 重新计 hits
{
  let st = { base: 15, pending: null };
  let r = qtyConfirmStep(st, 4, 1000);
  st = r.state;
  r = qtyConfirmStep(st, 3, 2500);
  assert(r.pending && r.state.pending.to === 3 && r.state.pending.hits === 1, 'retarget');
  assert(!r.alert, 'no alert on retarget');
}

// 9d) pending 超时
{
  let st = { base: 15, pending: { from: 15, to: 4, firstTs: 1000, hits: 1 } };
  let r = qtyConfirmStep(st, 4, 1000 + QTY_TTL_MS + 1);
  // 超时后当作新候选 hits=1
  assert(r.pending && r.state.pending.hits === 1 && !r.alert, 'ttl restart');
}

// 10) v19.3：归零永不确认；大幅下降加严
const BIG_HITS = 3;
const BIG_GAP = 12000;
function qtyConfirmStepV193(state, cur, now) {
  let { base, pending } = state;
  if (base == null) return { state: { base: cur, pending: null }, alert: false, first: true };
  if (cur === base) return { state: { base, pending: null }, alert: false, cancelled: !!pending };
  let nextPending;
  if (pending && pending.to === cur) {
    nextPending = { from: base, to: cur, firstTs: pending.firstTs, hits: (pending.hits || 1) + 1 };
  } else {
    nextPending = { from: base, to: cur, firstTs: now, hits: 1 };
  }
  const isZeroDrop = cur === 0 && base > 0;
  const dropN = cur < base ? base - cur : 0;
  const isBigDrop = dropN > 0 && (isZeroDrop || dropN >= Math.max(3, Math.ceil(base * 0.5)));
  const needHits = isBigDrop ? BIG_HITS : QTY_HITS;
  const needGap = isBigDrop ? BIG_GAP : QTY_GAP_MS;
  const confirmed = !isZeroDrop && nextPending.hits >= needHits && (now - nextPending.firstTs) >= needGap;
  if (!confirmed) {
    return { state: { base, pending: nextPending }, alert: false, pending: true, isZeroDrop, isBigDrop };
  }
  return { state: { base: cur, pending: null }, alert: true, from: base, to: cur };
}

// 10a) 12→0 永不告警（即使多次命中）
{
  let st = { base: 12, pending: null };
  let r = qtyConfirmStepV193(st, 0, 1000);
  assert(r.pending && r.isZeroDrop && !r.alert, '12→0 pending zero');
  st = r.state;
  r = qtyConfirmStepV193(st, 0, 1000 + BIG_GAP + 1000);
  // hits may be 2 but zero never confirms
  assert(!r.alert, '12→0 never alerts');
  // rebound
  r = qtyConfirmStepV193(st, 12, 1000 + BIG_GAP + 2000);
  assert(r.cancelled || (!r.alert && r.state.base === 12), '0→12 rebound');
}

// 10b) 大幅下降 12→5 需 3 hits + 12s
{
  let st = { base: 12, pending: null };
  let t = 1000;
  let r = qtyConfirmStepV193(st, 5, t); st = r.state;
  r = qtyConfirmStepV193(st, 5, t + 4000); st = r.state;
  assert(!r.alert, 'big drop 2 hits no alert');
  r = qtyConfirmStepV193(st, 5, t + BIG_GAP); // hits=3, gap ok
  assert(r.alert && r.to === 5, 'big drop confirmed after 3+12s');
}

// 10c) mallId 解析优先
function resolveByMall(map, mallId, dom) {
  if (mallId && map[mallId]) {
    if (dom && dom !== map[mallId]) {
      const owned = Object.keys(map).find((k) => map[k] === dom && k !== mallId);
      if (!owned) { map[mallId] = dom; return dom; }
      return map[mallId]; // prefer mallId when conflict with another store
    }
    return map[mallId];
  }
  if (mallId && dom) { map[mallId] = dom; return dom; }
  return dom || null;
}
{
  const map = { '111': 'Agnis', '222': 'HomeCove' };
  // 切店 DOM 还是 HomeCove，但响应 mallId=111 → 必须记 Agnis
  assert(resolveByMall(map, '111', 'HomeCove') === 'Agnis', 'prefer mallId over lagging DOM');
  // 未知 mall + DOM
  assert(resolveByMall({}, '333', 'Twilight Cove') === 'Twilight Cove', 'learn new');
}


// 11) v19.5 collapse（defense-in-depth，主路径靠 trust）
function isOnSaleScanCollapsed(scanN, trustedCount, trustedTs, now) {
  const RATIO = 0.5, MIN_DROP = 3, MAX_AGE = 10 * 60 * 1000;
  if (typeof scanN !== 'number' || scanN < 0) return false;
  if (typeof trustedCount !== 'number' || trustedCount <= 0) return false;
  if (typeof trustedTs === 'number' && trustedTs > 0 && (now - trustedTs) > MAX_AGE) return false;
  if (scanN >= trustedCount) return false;
  const drop = trustedCount - scanN;
  if (drop < MIN_DROP) return false;
  if (scanN <= Math.floor(trustedCount * RATIO)) return true;
  if (drop >= Math.max(MIN_DROP, Math.ceil(trustedCount * RATIO))) return true;
  return false;
}
assert(isOnSaleScanCollapsed(4, 15, 1000, 2000), '15→4 collapsed');
assert(!isOnSaleScanCollapsed(14, 15, 1000, 2000), '15→14 not collapsed');
assert(!isOnSaleScanCollapsed(15, 15, 1000, 2000), 'same not collapsed');
assert(!isOnSaleScanCollapsed(4, 15, 1000, 1000 + 11 * 60 * 1000), 'stale trusted ignored');
// baseline ids: would delist 11 of 15
{
  const prevN = 15, scanned = 4, wouldDelist = 11;
  assert(wouldDelist >= 3 && isOnSaleScanCollapsed(scanned, prevN, 0, 1000), 'baseline collapse');
}

// 12) v20 trust 门闩：非 full-onsale 一律 abort，不动基准
function gateTrust(scanMeta) {
  scanMeta = scanMeta || {};
  if (scanMeta.watchFilterOn) return { aborted: true, reason: 'watch-filter-on' };
  if (scanMeta.trust !== 'full-onsale') {
    return { aborted: true, reason: 'untrusted-view', trustReason: scanMeta.trustReason || scanMeta.trust || 'missing-trust' };
  }
  return { aborted: false };
}
assert(gateTrust({ trust: 'full-onsale', watchFilterOn: false }).aborted === false, 'full trusted');
assert(gateTrust({ trust: 'untrusted', trustReason: 'filter-uncleared' }).reason === 'untrusted-view', 'untrusted abort');
assert(gateTrust({}).reason === 'untrusted-view', 'missing trust abort');
assert(gateTrust({ trust: 'full-onsale', watchFilterOn: true }).reason === 'watch-filter-on', 'filter overrides trust');
// 筛后 4===4 若 content 仍标 untrusted → 不写基准（模拟 HomeCove）
{
  const prevIds = {};
  for (let i = 1; i <= 15; i++) prevIds['p' + i] = { productId: 'p' + i };
  const g = gateTrust({ trust: 'untrusted', trustReason: 'filter-on-at-scan', watchFilterOn: true });
  assert(g.aborted, 'filtered 4===4 must abort');
  // 若误放行 computeDiff 会 delist 11；gate 挡住则 prev 保持
  assert(Object.keys(prevIds).length === 15, 'baseline untouched');
}

// 13) v20 HomeCove 全链路：pending 不约 B + rebound cancel + 即使 B 跑了 untrusted 不改基准
{
  let st = { base: 15, pending: null };
  let armed = false;
  let r = qtyConfirmStep(st, 4, 1000);
  armed = applySchedule(armed, r);
  assert(!armed && !r.shouldScan, 'HomeCove pending no B');
  st = r.state;
  r = qtyConfirmStep(st, 15, 1500);
  armed = applySchedule(armed, r);
  assert(r.cancelScan && !armed, 'HomeCove rebound cancels B');
  const fakeScan = gateTrust({ trust: 'untrusted', watchFilterOn: false, trustReason: 'filter-uncleared' });
  assert(fakeScan.aborted, 'HomeCove dirty scan aborted');
}

// 14) v22：限流在售子集 vs 全量恢复
function looksLikeWatchFilterSubset(onSale, latest, snap) {
  if (typeof onSale !== 'number' || onSale < 0) return false;
  const high = (typeof snap.onSaleHighWater === 'number' && snap.onSaleHighWater > 0)
    ? snap.onSaleHighWater
    : (typeof snap.onSaleCount === 'number' && snap.onSaleCount > 0 ? snap.onSaleCount : null);
  if (high == null || high < 4) return false;
  if (!(onSale < high && onSale <= Math.floor(high * 0.5))) return false;
  const twCandidates = [
    latest && latest.trafficWatch,
    snap.trafficWatch,
    snap.trafficWatchHigh,
  ].filter((n) => typeof n === 'number' && n >= 0);
  const tw = twCandidates.length ? Math.max.apply(null, twCandidates) : null;
  if (tw != null && tw > 0 && onSale <= tw + 1) return true;
  if (tw == null && onSale <= Math.floor(high * 0.35)) return true;
  return false;
}
function looksLikeSubsetRecovery(prev, next, snap) {
  if (typeof prev !== 'number' || typeof next !== 'number') return false;
  if (!(next > prev)) return false;
  const high = (typeof snap.onSaleHighWater === 'number' && snap.onSaleHighWater > 0)
    ? snap.onSaleHighWater : null;
  if (high != null && high >= 4) {
    if (prev < high * 0.5 && next >= Math.ceil(high * 0.8)) return true;
    if (prev <= Math.floor(high * 0.35) && next >= prev * 2) return true;
  }
  if (prev > 0 && prev <= 5 && next >= prev * 3 && (next - prev) >= 6) return true;
  return false;
}
// Twilight 截图：高水位 12、chip=3、筛后在售 2 → 子集
assert(looksLikeWatchFilterSubset(2, { trafficWatch: 3 }, { onSaleHighWater: 12, onSaleCount: 12 }),
  'Twilight 2 vs high12 chip3 is subset');
// HomeCove：3 vs 15
assert(looksLikeWatchFilterSubset(3, { trafficWatch: 3 }, { onSaleHighWater: 15 }),
  'HomeCove 3 vs high15 is subset');
// 真实下降 15→10 不是子集（仍高于 50%）
assert(!looksLikeWatchFilterSubset(10, { trafficWatch: 3 }, { onSaleHighWater: 15 }),
  '15→10 not subset');
// 真下降到 5 且 chip=3：5 > chip+1 → 若无腰斩判定… 5 <= 7.5 且 5 <= 4? no → not subset by chip
// 5 <= floor(15*0.5)=7 且 5 > 3+1=4 → chip 规则不命中；tw 路径要 onSale<=tw+1
assert(!looksLikeWatchFilterSubset(5, { trafficWatch: 3 }, { onSaleHighWater: 15 }),
  '15→5 with chip3 not treated as subset (may be real drop)');
// 恢复 2→12 / 3→15 静默
assert(looksLikeSubsetRecovery(2, 12, { onSaleHighWater: 12 }), '2→12 recover with high');
assert(looksLikeSubsetRecovery(3, 15, { onSaleHighWater: 15 }), '3→15 recover with high');
// 无高水位时：污染首基 2 后恢复 12
assert(looksLikeSubsetRecovery(2, 12, {}), '2→12 recover without high');
// 真实上架 12→13 不是 recover
assert(!looksLikeSubsetRecovery(12, 13, { onSaleHighWater: 12 }), '12→13 real rise');
// silent 不降基
function silentNext(prev, got) {
  if (prev != null && got < prev) return prev;
  return got;
}
assert(silentNext(12, 2) === 12, 'silent keep high on drop');
assert(silentNext(12, 13) === 13, 'silent allow rise');

console.log('test_onsale_ab: OK (14 groups, incl v20 A/B + v22 subset/recover)');

