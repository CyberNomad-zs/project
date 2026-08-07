import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from './config.js';
import { launchBrowser, isLoggedIn } from './browser.js';
import { closePopups } from './popups.js';
import { log } from './logger.js';

/**
 * 校准脚本：有头登录态下，抓取商品列表页 & 店铺切换相关的
 *   - 所有 XHR/fetch 接口 URL（帮助确定商品列表 API）
 *   - 顶部 header / 店铺切换器的 HTML（帮助确定选择器）
 * 结果写入 data/calibrate-*.txt，供人工核对后微调选择器。
 */
export async function calibrate(cfg) {
  // headless 下网关重置期更稳（有头模式重置阵发期易 frame detached 崩溃）；
  // 截图/响应体捕获在无头下同样有效。可用 CALIB_HEADED=1 强制有头做人工观察。
  const headed = process.env.CALIB_HEADED === '1';
  const { context, page } = await launchBrowser(cfg, { headless: !headed });
  const apiUrls = new Set();
  page.on('request', (req) => {
    const t = req.resourceType();
    if (t === 'xhr' || t === 'fetch') apiUrls.add(`${req.method()} ${req.url()}`);
  });

  // 关键新增：把疑似商品数据接口的 JSON 响应体落盘，供离线反推字段名
  const bodiesDir = resolve(ROOT, 'data', 'calibrate-bodies');
  mkdirSync(bodiesDir, { recursive: true });
  const bodyIndex = [];
  let bodySeq = 0;
  page.on('response', async (resp) => {
    try {
      const url = resp.url();
      const ct = resp.headers()['content-type'] || '';
      if (!ct.includes('json')) return;
      // 抓「全部」业务 JSON（不再按 URL 关键词预筛，免得漏掉列表接口），仅跳过明显噪声
      if (/menu|\/auth\/|feedback|_stm|pmm|robin|exam|redDot|leo-config|report\/uin|env\?|jump\/token/i.test(url)) return;
      const text = await resp.text();
      if (!text || text.length < 40) return; // 太短多半是计数/开关类，跳过
      const seq = String(++bodySeq).padStart(2, '0');
      const file = `body-${seq}.json`;
      const hit = /在售|流量|onSale|skcId|goodsList|productList|traffic/i.test(text);
      writeFileSync(
        resolve(bodiesDir, file),
        `// ${resp.request().method()} ${url}\n// status=${resp.status()} hitKeywords=${hit}\n${text}`,
        'utf8'
      );
      bodyIndex.push(`${file}  hit=${hit}  ${resp.request().method()} ${url}`);
    } catch { /* ignore */ }
  });

  if (!(await isLoggedIn(page, cfg))) {
    log.error('未登录，请先 npm run login');
    await context.close();
    return;
  }
  await closePopups(page);
  log.info('已进入商品列表页，采集接口与 DOM 中…（约 25 秒）');
  await page.waitForTimeout(5000);

  // 页面外壳常只渲染菜单，需显式点「商品列表」菜单项进入真正的表格视图
  const menu = page.getByText(/^商品列表$/).first();
  if (await menu.isVisible({ timeout: 2000 }).catch(() => false)) {
    await menu.click({ timeout: 3000 }).catch(() => {});
    log.info('已点击「商品列表」菜单项，等待表格渲染…');
    await page.waitForTimeout(6000);
  }
  await closePopups(page);

  // 点一下「在售中」标签，触发列表接口
  const tab = page.getByText(/在售中\s*\d*/).first();
  if (await tab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await tab.click({ timeout: 3000 }).catch(() => {});
    log.info('已点击「在售中」标签。');
  } else {
    log.warn('未见「在售中」标签，可能表格仍未渲染。');
  }
  await page.waitForTimeout(3000);
  // 关键：网格「加载中」多因通知面板遮挡/抢焦点，先再清一轮弹窗
  await closePopups(page);
  // 落盘当前整页 HTML（面板仍在时），便于离线核对通知面板 X 的真实选择器
  writeFileSync(resolve(ROOT, 'data', 'calib-after-close.html'), await page.content().catch(() => ''), 'utf8');
  // 等网格数据真正出现（在售中 / 商品行）
  await page.getByText(/在售中\s*\d+/).first().waitFor({ state: 'visible', timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: resolve(ROOT, 'data', 'calib-shot-01-list.png') }).catch(() => {});
  // 轻微滚动，触发懒加载/分页接口
  await page.mouse.wheel(0, 1200).catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: resolve(ROOT, 'data', 'calib-shot-02-scrolled.png'), fullPage: true }).catch(() => {});

  // 保存接口清单
  const apiList = [...apiUrls].filter((u) => /goods|product|list|query|mms|mall|shop|search/i.test(u));
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-apis.txt'),
    [...apiUrls].sort().join('\n'),
    'utf8'
  );
  log.info(`接口清单已保存（${apiUrls.size} 条），疑似相关：`);
  for (const u of apiList.slice(0, 40)) log.info('  ', u);

  // 保存响应体索引
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-bodies', '_index.txt'),
    bodyIndex.join('\n') || '(未捕获到任何疑似商品接口响应体)',
    'utf8'
  );
  log.info(`已落盘 ${bodyIndex.length} 个疑似商品接口响应体到 data/calibrate-bodies/`);
  for (const b of bodyIndex.filter((x) => /hit=true/.test(x))) log.info('  ★', b);

  // 保存顶部 header HTML（含店铺切换器）
  const headerHtml = await page
    .locator('header, [class*="header" i], [class*="Header" i]')
    .first()
    .innerHTML()
    .catch(() => '');
  writeFileSync(resolve(ROOT, 'data', 'calibrate-header.html'), headerHtml, 'utf8');

  // 保存整页可见文本片段（辅助核对标签/芯片文案）
  const bodyText = await page.locator('body').innerText().catch(() => '');
  writeFileSync(resolve(ROOT, 'data', 'calibrate-bodytext.txt'), bodyText, 'utf8');

  // 保存「切换前」整页 HTML，供离线核对
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-page-before.html'),
    await page.content().catch(() => ''),
    'utf8'
  );

  // 自动尝试打开店铺切换器：逐个试候选触发区，打开后把整页 HTML 存盘，
  // 供离线分析下拉结构（stores.js 的 SWITCHER_TRIGGERS / STORE_ITEM_SELECTORS 据此微调）。
  const SWITCHER_CANDIDATES = [
    '[class*="MallSelect"]',
    '[class*="mall-select"]',
    '[class*="shopSelect"]',
    '[class*="StoreSelect"]',
    '[class*="mallName" i]',
    '[class*="shopName" i]',
    'header [class*="select" i]',
  ];
  let openedBy = '';
  for (const sel of SWITCHER_CANDIDATES) {
    const el = page.locator(sel).first();
    if (await el.isVisible({ timeout: 400 }).catch(() => false)) {
      await el.click({ timeout: 1500 }).catch(() => {});
      await page.waitForTimeout(1200);
      openedBy = sel;
      break;
    }
  }
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-page-switcher-open.html'),
    await page.content().catch(() => ''),
    'utf8'
  );
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-switcher-meta.txt'),
    `openedBy=${openedBy || '(未命中任何候选，见下方手动观察)'}\n候选清单:\n${SWITCHER_CANDIDATES.join('\n')}\n`,
    'utf8'
  );
  if (openedBy) log.info(`已自动点开疑似店铺切换器（命中 ${openedBy}），整页 HTML 已存盘。`);
  else log.warn('未自动命中店铺切换器候选，请在接下来 20 秒内手动点开，我已存下切换前整页 HTML 供比对。');

  log.info('校准文件已写入 data/：calibrate-apis.txt / calibrate-header.html / calibrate-bodytext.txt / calibrate-page-before.html / calibrate-page-switcher-open.html / calibrate-switcher-meta.txt');
  log.info('浏览器保持打开，请手动点开右上角店铺切换器再观察一次。20 秒后自动关闭。');
  await page.waitForTimeout(20000);
  // 手动打开后再存一次，兜底自动点击没命中的情况
  writeFileSync(
    resolve(ROOT, 'data', 'calibrate-page-switcher-manual.html'),
    await page.content().catch(() => ''),
    'utf8'
  );
  await context.close().catch(() => {});
}
