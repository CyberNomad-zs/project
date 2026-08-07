import { chromium } from 'playwright';

const USERDATA = 'E:/project/temu/temu-monitor/.userdata';
const DEEP = 'https://agentseller.temu.com/goods/list';
const ROOT = 'https://agentseller.temu.com/';

async function once(page, url, waitUntil = 'commit') {
  const t0 = Date.now();
  try {
    const resp = await page.goto(url, { waitUntil, timeout: 20000 });
    return `OK  status=${resp && resp.status()}  url=${page.url().slice(0, 50)}  ${Date.now() - t0}ms`;
  } catch (e) {
    return `FAIL ${(e.message || '').split('\n')[0].replace('page.goto: ', '')}  ${Date.now() - t0}ms`;
  }
}

const ctx = await chromium.launchPersistentContext(USERDATA, {
  headless: true,
  args: ['--disable-blink-features=AutomationControlled'],
});
const page = ctx.pages()[0] || await ctx.newPage();

console.log('[direct] goods/list ×6 (commit)');
for (let i = 1; i <= 6; i++) {
  console.log(`  deep #${i}: ${await once(page, DEEP)}`);
  await page.waitForTimeout(1500).catch(() => {});
}
console.log('\n[direct] domcontentloaded 完整加载一次');
console.log(`  deep(dcl): ${await once(page, DEEP, 'domcontentloaded')}`);
// 加载后看看关键文本是否出现（真登录态 & 页面渲染）
await page.waitForTimeout(4000).catch(() => {});
const hit = await page.getByText(/在售中|商品列表|全部\s*\d+/).first().isVisible({ timeout: 5000 }).catch(() => false);
console.log(`  关键文本(在售中/商品列表)可见: ${hit}`);
console.log('\n[direct] root ×2');
for (let i = 1; i <= 2; i++) console.log(`  root #${i}: ${await once(page, ROOT)}`);

await ctx.close().catch(() => {});
console.log('\nDONE');
