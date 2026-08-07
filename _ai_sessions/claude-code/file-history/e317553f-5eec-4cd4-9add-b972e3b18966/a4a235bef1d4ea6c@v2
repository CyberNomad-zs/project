// One-off: capture all XHR/fetch traffic on goods/list under the current logged-in
// session, to evaluate whether the internal JSON API can be called directly.
// Reuses the exact browser launch recipe (channel:chrome + .userdata + direct connect).
// Run standalone AFTER stopping the daemon (Chrome single-instance lock on .userdata).
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadConfig, ROOT } from './src/config.js';
import { launchBrowser, gotoWithRetry, waitForGoodsList } from './src/browser.js';

const cfg = loadConfig();
const outDir = resolve(ROOT, 'capture');
mkdirSync(outDir, { recursive: true });

const KEYS = /在售|待发|已下架|已删除|流量|traffic|goods|sku|skc|mms|itemList|pageItem|onSale|saleStatus/i;
const records = [];

const { context, page } = await launchBrowser(cfg, { headless: true });

page.on('response', async (resp) => {
  try {
    const req = resp.request();
    const url = resp.url();
    const ct = (resp.headers()['content-type'] || '');
    if (req.resourceType() !== 'xhr' && req.resourceType() !== 'fetch') return;
    if (!/json|text/i.test(ct)) return;
    let body = '';
    try { body = await resp.text(); } catch { body = '<unreadable>'; }
    const hit = KEYS.test(url) || KEYS.test(body.slice(0, 20000));
    records.push({
      url,
      method: req.method(),
      status: resp.status(),
      contentType: ct,
      postData: (req.postData() || '').slice(0, 2000),
      bodyLen: body.length,
      hit,
      bodyPreview: body.slice(0, 4000),
    });
    if (hit) {
      const name = 'hit-' + String(records.length).padStart(3, '0') + '.json';
      writeFileSync(resolve(outDir, name), JSON.stringify({ url, method: req.method(), status: resp.status(), postData: req.postData(), body }, null, 2), 'utf8');
      console.log('HIT ->', req.method(), url.slice(0, 120), 'bodyLen=', body.length);
    }
  } catch { /* ignore */ }
});

console.log('导航到 goods/list ...');
const navOk = await gotoWithRetry(page, cfg.goodsListUrl, cfg);
console.log('navOk=', navOk, 'url=', page.url());
const listed = await waitForGoodsList(page, { timeout: cfg.navTimeoutMs });
console.log('waitForGoodsList=', listed);

// 让页面把首屏所有接口打完 + 尝试触发 tab/列表懒加载
await page.waitForTimeout(8000);
// 轻滚动，触发可能的懒加载接口
try { await page.mouse.wheel(0, 2000); await page.waitForTimeout(3000); } catch {}

const loggedIn = !/login|signin|account\/authentication/i.test(page.url());
console.log('loggedIn(约) =', loggedIn);

// 汇总索引
const index = records.map((r, i) => ({ i, hit: r.hit, method: r.method, status: r.status, bodyLen: r.bodyLen, url: r.url }));
writeFileSync(resolve(outDir, '_index.json'), JSON.stringify(index, null, 2), 'utf8');
writeFileSync(resolve(outDir, '_all.json'), JSON.stringify(records, null, 2), 'utf8');
console.log('\n共捕获 XHR/fetch:', records.length, ' 命中关键字:', records.filter(r => r.hit).length);
console.log('输出目录:', outDir);

await context.close();
process.exit(0);
