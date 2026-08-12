// 登录态 DOM 探查：一次性 dump 出适配选择器所需的真实结构。
import { loadConfig } from './src/config.js';
import { launchBrowser, gotoWithRetry, waitForGoodsList } from './src/browser.js';
import { closePopups } from './src/popups.js';
import { log } from './src/logger.js';
import { writeFileSync } from 'node:fs';

const OUT = 'C:\\Users\\Administrator\\AppData\\Local\\Temp\\claude\\E--project-temu\\39c2c9b3-8b05-4fa9-a38d-ee426277b3c7\\scratchpad\\probe-dom.txt';
const cfg = loadConfig();
const dump = [];
const P = (t) => { dump.push(t); log.info(String(t).slice(0, 100)); };

const { context, page } = await launchBrowser(cfg, { headless: true });
try {
  await gotoWithRetry(page, cfg.goodsListUrl, cfg);
  await waitForGoodsList(page, { timeout: cfg.navTimeoutMs });
  await page.waitForTimeout(3000);
  await closePopups(page);
  await page.waitForTimeout(1500);
  P('URL: ' + page.url());

  // 1) 状态 tab（全部/在售中/未发布/已下架/已删除）叶子元素文本
  const tabsText = await page.evaluate(() => {
    const els = [...document.querySelectorAll('*')].filter((e) =>
      e.children.length === 0 && /全部|在售中|未发布|已下架|已终止|已删除/.test((e.textContent || '').trim()));
    return [...new Set(els.map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 24))];
  });
  P('=== [1] 状态tab叶子文本 ===\n' + JSON.stringify(tabsText, null, 1));

  // 「在售中」附近容器的 outerHTML（看数字是否独立 span）
  const onSaleHtml = await page.evaluate(() => {
    const hit = [...document.querySelectorAll('*')].find((e) =>
      /在售中/.test(e.textContent || '') && e.children.length <= 4 &&
      ![...e.children].some((c) => /在售中/.test(c.textContent || '')));
    return hit ? (hit.parentElement || hit).outerHTML.slice(0, 1500) : '(未找到)';
  });
  P('=== [2] 在售中 容器HTML ===\n' + onSaleHtml);

  // 2) 来源店铺 下拉：点开后 dump 选项
  let storeOptions = [];
  const label = page.getByText('来源店铺', { exact: false }).first();
  if (await label.isVisible({ timeout: 2000 }).catch(() => false)) {
    const box = label.locator('xpath=following::*[@role="combobox" or contains(@class,"select") or contains(@class,"Select") or contains(@class,"arco-select")][1]').first();
    await box.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(1800);
    storeOptions = await page.evaluate(() => {
      const opts = [...document.querySelectorAll('[role="option"],[class*="option" i],[class*="arco-select-option"],li')]
        .map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 50);
      return [...new Set(opts)].slice(0, 80);
    });
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(500);
  } else {
    P('(未找到「来源店铺」label)');
  }
  P('=== [3] 来源店铺 下拉选项 ===\n' + JSON.stringify(storeOptions, null, 1));

  // 顶部地区 tab（全球/美国/欧区/商家中心）
  const regionTabs = await page.evaluate(() => {
    const els = [...document.querySelectorAll('*')].filter((e) =>
      e.children.length === 0 && /^(全球|美国|欧区|商家中心)$/.test((e.textContent || '').trim()));
    return [...new Set(els.map((e) => (e.textContent || '').trim()))];
  });
  P('=== [4] 地区tab ===\n' + JSON.stringify(regionTabs));

  // 3) 含"流量"的叶子文本（找待关注/下降标签的真实文案）
  const trafficTexts = await page.evaluate(() => {
    const els = [...document.querySelectorAll('*')].filter((e) =>
      e.children.length === 0 && /流量/.test(e.textContent || ''));
    return [...new Set(els.map((e) => (e.textContent || '').trim()))].filter((t) => t && t.length < 40).slice(0, 30);
  });
  P('=== [5] 含"流量"文本 ===\n' + JSON.stringify(trafficTexts, null, 1));

  // 按钮文本（找"批量处理流量下降商品"等）
  const btns = await page.evaluate(() => {
    const els = [...document.querySelectorAll('button,[role="button"],[class*="btn" i],[class*="Button" i]')]
      .map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 24);
    return [...new Set(els)].slice(0, 60);
  });
  P('=== [6] 按钮文本 ===\n' + JSON.stringify(btns, null, 1));

  // 4) 第一个商品行 HTML（看 SKC/标题/流量标签结构）
  const rowHtml = await page.evaluate(() => {
    const skcEl = [...document.querySelectorAll('*')].find((e) =>
      /SKC\s*ID/i.test(e.textContent || '') && e.children.length < 6);
    if (!skcEl) return '(未找到 SKC 元素)';
    let row = skcEl;
    for (let i = 0; i < 8 && row.parentElement; i++) {
      if ((row.textContent || '').length > 120) break;
      row = row.parentElement;
    }
    return row.outerHTML.slice(0, 2500);
  });
  P('=== [7] 商品行HTML(截断) ===\n' + rowHtml);

  await page.screenshot({ path: OUT.replace('.txt', '.png'), fullPage: false }).catch(() => {});
} catch (e) {
  P('!! ERROR: ' + (e.message || e));
} finally {
  writeFileSync(OUT, dump.join('\n\n'), 'utf8');
  log.info('DUMP 写入: ' + OUT);
  await context.close().catch(() => {});
}
