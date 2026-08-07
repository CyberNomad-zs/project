// One-off：趁店铺有「商品流量待关注」商品时，抓筛选后的 pageQuery，
// 对比待关注商品与普通商品的流量字段，定死「待关注」对应哪个字段/取值。
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadConfig, ROOT } from './src/config.js';
import { launchBrowser, gotoWithRetry, waitForGoodsList } from './src/browser.js';

const cfg = loadConfig();
const outDir = resolve(ROOT, 'capture');
mkdirSync(outDir, { recursive: true });

const FLOW_KEYS = ['flowLimit', 'flowLimitStatus', 'flowAllowanceStatus', 'flowAllowanceSiteList', 'preLimitTime', 'potentialProduct', 'trafficStatus'];
const pageQueries = []; // {total, items:[{id,name,flow:{...}}]}

const { context, page } = await launchBrowser(cfg, { headless: true });

page.on('response', async (resp) => {
  try {
    const url = resp.url();
    if (!/visage-agent-seller\/product\/skc\/pageQuery/.test(url)) return;
    if (resp.request().method() !== 'POST') return;
    const body = await resp.text();
    const j = JSON.parse(body);
    const r = j && j.result; if (!r) return;
    const items = (Array.isArray(r.pageItems) ? r.pageItems : []).map((it) => {
      const flow = {};
      for (const k of FLOW_KEYS) if (k in (it || {})) flow[k] = it[k];
      // 也扫一遍所有含 flow/traffic/limit 的键，防止字段名猜错
      for (const k of Object.keys(it || {})) if (/flow|traffic|limit|potential/i.test(k)) flow[k] = it[k];
      return { productId: it.productId, name: (it.productName || '').slice(0, 20), flow };
    });
    pageQueries.push({ total: r.total, count: items.length, items });
    console.log(`captured pageQuery: total=${r.total} items=${items.length}`);
  } catch (e) { /* ignore */ }
});

console.log('导航 goods/list ...');
await gotoWithRetry(page, cfg.goodsListUrl, cfg);
await waitForGoodsList(page, { timeout: cfg.navTimeoutMs });
await page.waitForTimeout(6000); // 首屏未筛选的 pageQuery

// 点「商品流量待关注」快速筛选 chip → 触发筛选后的 pageQuery（只含待关注商品）
console.log('点击「商品流量待关注」筛选 ...');
const chip = page.getByText('商品流量待关注', { exact: false }).first();
if (await chip.isVisible({ timeout: 5000 }).catch(() => false)) {
  await chip.click({ timeout: 5000 }).catch((e) => console.log('click err', e.message));
  await page.waitForTimeout(8000); // 等筛选后的 pageQuery 回来
  // 再点一次以防第一次没触发
  await chip.click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(6000);
} else {
  console.log('未找到「商品流量待关注」chip');
}

writeFileSync(resolve(outDir, '_traffic.json'), JSON.stringify(pageQueries, null, 2), 'utf8');
console.log('\n共捕获 pageQuery 次数:', pageQueries.length);
for (const q of pageQueries) console.log(`  total=${q.total} count=${q.count}`);
console.log('明细已存 capture/_traffic.json');

await context.close();
process.exit(0);
