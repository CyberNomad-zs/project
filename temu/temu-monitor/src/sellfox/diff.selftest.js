/**
 * 本地单测：复现 2026-07-30 HomeCove 误报 + 2026-08-05 假上架
 * 运行：node src/sellfox/diff.selftest.js
 */
import { diffOnSale, formatChangeLines } from './diff.js';
import { parseChildInfo, attachSkusToAlertEvents } from './products.js';

function assert(cond, msg) {
  if (!cond) throw new Error('FAIL: ' + msg);
  console.log('  OK', msg);
}

function basePrev() {
  // 15 个在售（确认基准）
  const onSaleMap = {};
  for (let i = 1; i <= 15; i++) {
    onSaleMap['skc' + i] = {
      skcId: 'skc' + i,
      parentId: 'p' + i,
      name: '商品' + i,
      selectStatus: '12',
    };
  }
  return {
    onSaleMap,
    pendingOnshelf: {},
    allCount: 300,
    statusCounts: { 12: 15, 13: 100 },
    ts: 1,
  };
}

function fullAllMap(onSaleIds, extra = 280) {
  const all = {};
  for (const id of onSaleIds) {
    all[id] = {
      skcId: id,
      parentId: 'p',
      name: id,
      selectStatus: '12',
    };
  }
  for (let i = 0; i < extra; i++) {
    const id = 'other' + i;
    all[id] = { skcId: id, parentId: 'o', name: id, selectStatus: '13' };
  }
  return all;
}

console.log('1) 漏数假下架（5 个在售从结果中消失，all 也变少）→ 必须 skip，不告警 delist');
{
  const prev = basePrev();
  const keep = Object.keys(prev.onSaleMap).slice(0, 10);
  const onSaleMap = {};
  for (const id of keep) onSaleMap[id] = prev.onSaleMap[id];
  const allMap = fullAllMap(keep, 250);
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 10, 13: 90 },
    pullUnique: 918,
    prevPullUnique: 954,
  });
  assert(r.skipUpdate === true, 'skipUpdate');
  assert(r.delistedCount === 0, 'no delist');
  assert(!r.events.some((e) => e.type === 'delist' && e.severity === 'alert'), 'no delist alert');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 15, 'baseline kept 15');
}

console.log('2) 真·下架：商品仍在 allMap，status 从 12→13');
{
  const prev = basePrev();
  const ids = Object.keys(prev.onSaleMap);
  const gone = ids.slice(0, 2);
  const keep = ids.slice(2);
  const onSaleMap = {};
  for (const id of keep) onSaleMap[id] = prev.onSaleMap[id];
  const allMap = fullAllMap(keep, 280);
  for (const id of gone) {
    allMap[id] = {
      skcId: id,
      parentId: prev.onSaleMap[id].parentId,
      name: prev.onSaleMap[id].name,
      selectStatus: '13',
    };
  }
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 13, 13: 102 },
    pullUnique: 954,
    prevPullUnique: 954,
  });
  assert(r.skipUpdate === false, 'not skip');
  assert(r.delistedCount === 2, 'delist 2');
  assert(r.events.some((e) => e.type === 'delist' && e.items.length === 2), 'delist event');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 13, 'snap 13');
}

console.log('3) 上架首轮：新 skc 进 12 → 只 pending，不进确认基准、不告警');
{
  const prev = basePrev();
  const onSaleMap = { ...prev.onSaleMap };
  onSaleMap.skcNew = {
    skcId: 'skcNew',
    parentId: 'pn',
    name: '新品',
    selectStatus: '12',
  };
  const allMap = fullAllMap(Object.keys(onSaleMap), 280);
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 16 },
    pullUnique: 955,
    prevPullUnique: 954,
  });
  assert(r.skipUpdate === false, 'not skip');
  assert(r.listedCount === 0, 'no onshelf alert round1');
  assert(r.pendingOnshelfCount === 1, 'pending 1');
  assert(r.listedRawCount === 1, 'raw new 1');
  assert(r.events.some((e) => e.type === 'onshelf_pending'), 'pending event');
  assert(!r.events.some((e) => e.type === 'onshelf' && e.severity === 'alert'), 'no onshelf alert');
  assert(r.nextSnap.pendingOnshelf.skcNew, 'pending in snap');
  assert(!r.nextSnap.onSaleMap.skcNew, 'NOT in confirmed baseline yet');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 15, 'confirmed still 15');
}

console.log('3b) 上架第二轮仍为 12 → 确认告警，写入基准，清空 pending');
{
  const prev = basePrev();
  // 首轮之后：确认基准仍 15，pending 有 skcNew
  prev.pendingOnshelf = {
    skcNew: { skcId: 'skcNew', parentId: 'pn', name: '新品', selectStatus: '12' },
  };
  const onSaleMap = {
    ...prev.onSaleMap,
    skcNew: { skcId: 'skcNew', parentId: 'pn', name: '新品', selectStatus: '12' },
  };
  const allMap = fullAllMap(Object.keys(onSaleMap), 280);
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 16 },
    pullUnique: 955,
    prevPullUnique: 955,
  });
  assert(r.listedCount === 1, 'onshelf confirmed 1');
  assert(r.events.some((e) => e.type === 'onshelf' && e.items.length === 1), 'onshelf alert');
  assert(!r.nextSnap.pendingOnshelf.skcNew, 'pending cleared');
  assert(r.nextSnap.onSaleMap.skcNew, 'now in confirmed baseline');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 16, 'confirmed 16');
}

console.log('3c) 上架首轮 pending、次轮已不在 12 → 不告警（抖动），不进基准');
{
  const prev = basePrev();
  prev.pendingOnshelf = {
    skcFlap: { skcId: 'skcFlap', parentId: 'pf', name: '抖动', selectStatus: '12' },
  };
  const onSaleMap = { ...prev.onSaleMap };
  const allMap = fullAllMap(Object.keys(onSaleMap), 280);
  allMap.skcFlap = {
    skcId: 'skcFlap',
    parentId: 'pf',
    name: '抖动',
    selectStatus: '13',
  };
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 15, 13: 101 },
    pullUnique: 954,
    prevPullUnique: 954,
  });
  assert(r.listedCount === 0, 'no onshelf on flap');
  assert(r.delistedCount === 0, 'no delist on flap');
  assert(!r.nextSnap.pendingOnshelf.skcFlap, 'pending dropped');
  assert(!r.nextSnap.onSaleMap.skcFlap, 'not in baseline');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 15, 'confirmed still 15');
}

console.log('3d) 复现 08-05：同轮 −2 真下架 +4 新 12 → 只报下架 2，+4 进 pending');
{
  const prev = basePrev();
  const ids = Object.keys(prev.onSaleMap);
  const gone = ids.slice(0, 2);
  const keep = ids.slice(2);
  const onSaleMap = {};
  for (const id of keep) onSaleMap[id] = prev.onSaleMap[id];
  // 4 个新进 12
  for (let i = 1; i <= 4; i++) {
    const id = 'new' + i;
    onSaleMap[id] = { skcId: id, parentId: 'n' + i, name: '新' + i, selectStatus: '12' };
  }
  const allMap = fullAllMap(Object.keys(onSaleMap), 280);
  for (const id of gone) {
    allMap[id] = {
      skcId: id,
      parentId: prev.onSaleMap[id].parentId,
      name: prev.onSaleMap[id].name,
      selectStatus: '13',
    };
  }
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 17, 13: 102 },
    pullUnique: 958,
    prevPullUnique: 957,
  });
  assert(r.delistedCount === 2, 'delist 2');
  assert(r.listedCount === 0, 'no onshelf yet');
  assert(r.pendingOnshelfCount === 4, 'pending 4');
  assert(Object.keys(r.nextSnap.onSaleMap).length === 13, 'confirmed 15-2=13');
  assert(r.events.some((e) => e.type === 'delist' && e.from === 15 && e.to === 13), 'from/to 15→13');
}

console.log('4) 首轮不告警');
{
  const onSaleMap = { a: { skcId: 'a', selectStatus: '12', name: 'x' } };
  const r = diffOnSale(null, {
    onSaleMap,
    allMap: { a: onSaleMap.a },
    statusCounts: { 12: 1 },
  });
  assert(r.isFirst === true, 'first');
  assert(r.delistedCount === 0 && r.listedCount === 0, 'no alerts');
  assert(r.pendingOnshelfCount === 0, 'no pending on first');
}

console.log('5) 旧半降护栏仍在：15→3 且 unique 腰斩');
{
  const prev = basePrev();
  const keep = Object.keys(prev.onSaleMap).slice(0, 3);
  const onSaleMap = {};
  for (const id of keep) onSaleMap[id] = prev.onSaleMap[id];
  const allMap = fullAllMap(keep, 50);
  const r = diffOnSale(prev, {
    onSaleMap,
    allMap,
    statusCounts: { 12: 3 },
    pullUnique: 200,
    prevPullUnique: 954,
  });
  assert(r.skipUpdate === true, 'half-drop or unique skip');
  assert(r.delistedCount === 0, 'no delist on incomplete');
}

console.log('6) 文案：下架行不再写 15→17，合计单独一行');
{
  const lines = formatChangeLines('HomeCove', [
    {
      type: 'delist',
      severity: 'alert',
      from: 15,
      to: 13,
      items: [{ skcId: '1', name: 'A', selectStatus: '13', parentId: 'p1' }],
    },
    {
      type: 'onshelf',
      severity: 'alert',
      from: 15,
      to: 13,
      items: [{ skcId: '2', name: 'B', selectStatus: '12', parentId: 'p2' }],
    },
  ]);
  const text = lines.join('\n');
  assert(!/下架.*在售 15/.test(text), 'delist line has no 在售 from→to');
  assert(text.includes('赛狐确认在售：**15 → 13**'), 'summary line');
  assert(text.includes('连续两轮'), 'onshelf says 两轮确认');
}

console.log('7) 文案：SKU 子行 + getChildInfo 解析');
{
  const raw = [
    {
      parentId: 'p1',
      skuId: '9011356554',
      specName: '[8H-100 PACK]',
      extCode: '',
      stockQuantity: '219',
      name: '茶蜡100',
    },
    {
      parentId: 'p1',
      skuId: '51150109252',
      specName: '[8H-99 PACK]',
      stockQuantity: '262',
    },
  ];
  const skus = parseChildInfo(raw);
  assert(skus.length === 2, 'parse 2 skus');
  assert(skus[0].skuId === '9011356554', 'skuId');
  const events = [
    {
      type: 'delist',
      severity: 'alert',
      from: 13,
      to: 12,
      items: [
        {
          skcId: '7636599333',
          parentId: 'p1',
          name: '茶蜡',
          selectStatus: '10',
        },
      ],
    },
  ];
  attachSkusToAlertEvents(events, { p1: skus });
  events[0].items[0].skusAttempted = true;
  const lines = formatChangeLines('Twilight Cove', events);
  const text = lines.join('\n');
  assert(text.includes('SKU 9011356554'), 'sku id in card');
  assert(text.includes('[8H-100 PACK]') || text.includes('8H-100'), 'spec in card');
  assert(text.includes('库存 219'), 'stock in card');
  assert(text.includes('SKC 7636599333'), 'skc still shown');
  assert(text.includes('getChildInfo'), 'header mentions child api');
}

console.log('\nAll selftests passed.');
