// 精准探查：店铺下拉完整列表 / 快速筛选项 / 共有N条 / 点流量筛选后的计数变化。
import { loadConfig } from './src/config.js';
import { launchBrowser, gotoWithRetry, waitForGoodsList } from './src/browser.js';
import { closePopups } from './src/popups.js';
import { log } from './src/logger.js';
import { writeFileSync } from 'node:fs';

const OUT = 'C:\\Users\\Administrator\\AppData\\Local\\Temp\\claude\\E--project-temu\\39c2c9b3-8b05-4fa9-a38d-ee426277b3c7\\scratchpad\\probe2.txt';
const cfg = loadConfig();
const dump = [];
const P = (t) => { dump.push(String(t)); log.info(String(t).slice(0, 120)); };
const readTotal = (page) => page.evaluate(() => {
  const e = [...document.querySelectorAll('*')].find((x) => x.children.length === 0 && /共有\s*[\d,]+\s*条/.test(x.textContent || ''));
  return e ? e.textContent.trim() : '(无共有N条)';
});

const { context, page } = await launchBrowser(cfg, { headless: true });
try {
  await gotoWithRetry(page, cfg.goodsListUrl, cfg);
  await waitForGoodsList(page, { timeout: cfg.navTimeoutMs });
  await page.waitForTimeout(3000);
  await closePopups(page);
  await page.waitForTimeout(1500);

  P('初始总数: ' + await readTotal(page));

  // A. 来源店铺下拉完整选项（排除分页/全选噪声）
  const label = page.getByText('来源店铺', { exact: false }).first();
  if (await label.isVisible({ timeout: 2000 }).catch(() => false)) {
    const box = label.locator('xpath=following::*[@role="combobox" or contains(@class,"Select") or contains(@class,"select")][1]').first();
    await box.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(1800);
    const stores = await page.evaluate(() => {
      const bad = /^(全选|每页.*|共有.*|上一页|下一页|\d+|请选择|重置|确定)$/;
      const els = [...document.querySelectorAll('[role="option"],[class*="option" i],[class*="Option" i],li')];
      const vis = els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
      return [...new Set(vis.map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 60 && !bad.test(t)))];
    });
    P('=== [A] 来源店铺选项 ===\n' + JSON.stringify(stores, null, 1));
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(600);
  } else P('(未找到来源店铺 label)');

  // B. 快速筛选区文本（截图里「快速筛选」标签后的 chip）
  const chips = await page.evaluate(() => {
    const anchor = [...document.querySelectorAll('*')].find((e) => /^快速筛选/.test((e.textContent || '').trim()) && e.children.length < 3);
    const scope = anchor ? (anchor.closest('[class*="filter" i],[class*="quick" i]') || anchor.parentElement?.parentElement || anchor.parentElement) : null;
    if (!scope) return [];
    return [...new Set([...scope.querySelectorAll('*')].filter((e) => e.children.length === 0)
      .map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 24))];
  });
  P('=== [B] 快速筛选周边文本 ===\n' + JSON.stringify(chips, null, 1));

  // C. 点「商品流量待关注」→ 看总数变化 + url
  const wl = page.getByText('商品流量待关注', { exact: false }).first();
  if (await wl.isVisible({ timeout: 2000 }).catch(() => false)) {
    await wl.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(2800);
    P('点「商品流量待关注」后总数: ' + await readTotal(page));
    P('  url=' + page.url());
    // 复位
    await page.getByText(/^重置$/).first().click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(2000);
  } else P('(「商品流量待关注」不可点/未找到)');

  // D. 商品行结构：定位含 SKC ID 的行，输出其祖先里 textContent 长度适中的那层
  const rowHtml = await page.evaluate(() => {
    const skcEl = [...document.querySelectorAll('td,div,span')].find((e) => /SKC\s*ID/i.test(e.textContent || '') && (e.textContent || '').length < 60);
    if (!skcEl) return '(未找到SKC)';
    let row = skcEl;
    for (let i = 0; i < 10 && row.parentElement; i++) {
      const len = (row.textContent || '').length;
      if (len > 150 && len < 1200) break; // 一行商品的合理文本量
      row = row.parentElement;
    }
    return row.outerHTML.slice(0, 2000);
  });
  P('=== [D] 商品行HTML ===\n' + rowHtml);
} catch (e) {
  P('!! ERROR: ' + (e.message || e));
} finally {
  writeFileSync(OUT, dump.join('\n\n'), 'utf8');
  log.info('DUMP: ' + OUT);
  await context.close().catch(() => {});
}
