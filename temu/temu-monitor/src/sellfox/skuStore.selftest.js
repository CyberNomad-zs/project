/**
 * SKU 基线 diff 单测
 * node src/sellfox/skuStore.selftest.js
 */
import { applySkuRound, diffSkuMaps, skusToMap, formatSkuChangeLines } from './skuStore.js';

function assert(cond, msg) {
  if (!cond) throw new Error('FAIL: ' + msg);
  console.log('  OK', msg);
}

console.log('1) diffSkuMaps 多/少');
{
  const prev = skusToMap([
    { skuId: 'a', specName: '[1]' },
    { skuId: 'b', specName: '[2]' },
  ]);
  const curr = skusToMap([
    { skuId: 'b', specName: '[2]' },
    { skuId: 'c', specName: '[3]' },
  ]);
  const d = diffSkuMaps(prev, curr);
  assert(d.removed.length === 1 && d.removed[0].skuId === 'a', 'removed a');
  assert(d.added.length === 1 && d.added[0].skuId === 'c', 'added c');
}

console.log('2) 首轮 seed 不告警');
{
  const r = applySkuRound(null, {
    isFirstParentBaseline: true,
    onSaleMap: {
      skc1: { skcId: 'skc1', parentId: 'p1', name: '茶蜡', selectStatus: '12' },
    },
    childByParentId: {
      p1: [
        { skuId: 's1', specName: '[99]', parentId: 'p1' },
        { skuId: 's2', specName: '[100]', parentId: 'p1' },
      ],
    },
    delistedItems: [],
  });
  assert(r.events.length === 0, 'no events first');
  assert(r.stats.seeded === 1, 'seeded 1 skc');
  assert(Object.keys(r.nextShopDb.bySkc.skc1.skus).length === 2, '2 skus stored');
}

console.log('3) SKC 仍在售，少 1 SKU → sku_delist');
{
  const prev = {
    bySkc: {
      skc1: {
        parentId: 'p1',
        name: '茶蜡',
        skus: skusToMap([
          { skuId: 's1', specName: '[99]' },
          { skuId: 's2', specName: '[100]' },
        ]),
      },
    },
  };
  const r = applySkuRound(prev, {
    onSaleMap: {
      skc1: { skcId: 'skc1', parentId: 'p1', name: '茶蜡', selectStatus: '12' },
    },
    childByParentId: {
      p1: [{ skuId: 's1', specName: '[99]', parentId: 'p1' }],
    },
    delistedItems: [],
  });
  const del = r.events.filter((e) => e.type === 'sku_delist');
  assert(del.length === 1, 'one delist event');
  assert(del[0].items.length === 1 && del[0].items[0].skuId === 's2', 's2 gone');
  assert(r.stats.skuDelist === 1, 'stats');
}

console.log('4) SKC 离开在售 → 原 SKU 全下架并删库');
{
  const prev = {
    bySkc: {
      skc1: {
        parentId: 'p1',
        name: '茶蜡',
        skus: skusToMap([
          { skuId: 's1', specName: '[99]' },
          { skuId: 's2', specName: '[100]' },
        ]),
      },
    },
  };
  const r = applySkuRound(prev, {
    onSaleMap: {},
    childByParentId: {},
    delistedItems: [
      { skcId: 'skc1', parentId: 'p1', name: '茶蜡', selectStatus: '10' },
    ],
  });
  assert(r.events.some((e) => e.type === 'sku_delist' && e.reason === 'skc_left_onsale'), 'skc left');
  assert(r.stats.skuDelist === 2, '2 skus');
  assert(!r.nextShopDb.bySkc.skc1, 'removed from db');
}

console.log('5) 本轮未拉到 child → 不误报清空');
{
  const prev = {
    bySkc: {
      skc1: {
        parentId: 'p1',
        name: 'x',
        skus: skusToMap([{ skuId: 's1', specName: '[1]' }]),
      },
    },
  };
  const r = applySkuRound(prev, {
    onSaleMap: {
      skc1: { skcId: 'skc1', parentId: 'p1', name: 'x', selectStatus: '12' },
    },
    childByParentId: {}, // 没拉
    delistedItems: [],
  });
  assert(r.events.length === 0, 'no false empty');
  assert(r.nextShopDb.bySkc.skc1.skus.s1, 'kept baseline');
}

console.log('6) 文案含 SKU');
{
  const lines = formatSkuChangeLines('Twilight Cove', [
    {
      type: 'sku_delist',
      severity: 'alert',
      reason: 'sku_missing_while_skc_onsale',
      skcId: '7636599333',
      parentId: 'p1',
      name: '茶蜡',
      items: [{ skuId: '9011356554', specName: '[8H-100 PACK]', stockQuantity: '0' }],
    },
  ]);
  const t = lines.join('\n');
  assert(t.includes('SKU 9011356554'), 'sku in card');
  assert(t.includes('8H-100'), 'spec');
}

console.log('\nskuStore selftests passed.');
