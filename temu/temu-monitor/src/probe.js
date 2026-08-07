import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from './config.js';
import { loadConfig } from './config.js';
import { launchBrowser, gotoWithRetry } from './browser.js';
import { closePopups } from './popups.js';
import { log } from './logger.js';

/**
 * 重度探针：用截图 + 全量响应抓取，看清商品列表页真实状态，定位：
 *   1) 列表核心内容有没有渲染（截图直观看）
 *   2) 返回商品列表 / 在售数量 / 流量标记的真实接口是哪个（保存 JSON body）
 *   3) 列表数据 XHR 是否也被网关重置
 *   4) 店铺切换器的真实 DOM
 * 产物全部写入 data/probe-*，供离线分析。
 */

const DIR = resolve(ROOT, 'data');
const p = (f) => resolve(DIR, f);

const INTEREST = /goods|product|list|page|query|流量|traffic|onSale|在售|skc|sku|mall|shop|seller|item|status|count|summary|filter|tab/i;

async function main() {
  const cfg = loadConfig();
  const { context, page } = await launchBrowser(cfg, { headless: false });

  const respLog = [];
  let bodyIdx = 0;
  const bodyIndex = [];

  page.on('response', async (resp) => {
    try {
      const url = resp.url();
      const status = resp.status();
      const ct = resp.headers()['content-type'] || '';
      let size = -1;
      let saved = '';
      const isJson = ct.includes('json');
      const looksInteresting = INTEREST.test(url);
      if (isJson && (looksInteresting || /agentseller\.temu\.com\/(api|bg|visage|drogon|hawk|quick)/.test(url))) {
        const text = await resp.text().catch(() => '');
        size = text.length;
        // 只保存像"业务数据"的：含流量/在售/商品字段，或体积较大
        if (/流量|在售|goodsList|productList|itemList|skcId|skuId|totalNum|onSale|pageItems|dataList|salesVolume/i.test(text) || size > 3000) {
          const idx = String(++bodyIdx).padStart(2, '0');
          const name = `probe-body-${idx}.json`;
          writeFileSync(p(name), `// ${resp.request().method()} ${url}\n// status=${status} ct=${ct} size=${size}\n${text.slice(0, 400000)}`, 'utf8');
          bodyIndex.push(`${name}  ${resp.request().method()} ${url}  (status=${status}, size=${size})`);
          saved = name;
        }
      }
      respLog.push(`${status}  ${resp.request().method()}  ${url}  ct=${ct}  size=${size}  ${saved}`);
    } catch { /* ignore */ }
  });

  page.on('requestfailed', (req) => {
    respLog.push(`FAILED  ${req.method()}  ${req.url()}  err=${req.failure()?.errorText || ''}`);
  });

  const shots = [];
  async function shot(tag) {
    const name = `probe-${tag}.png`;
    await page.screenshot({ path: p(name), fullPage: false }).catch((e) => log.warn(`截图 ${tag} 失败：${e.message}`));
    shots.push(name);
    log.info(`📸 ${name}`);
  }

  // 1) 导航
  log.info('导航到商品列表页…');
  const navOk = await gotoWithRetry(page, cfg.goodsListUrl, cfg, { attempts: 6 });
  log.info(`导航结果 navOk=${navOk}，当前 URL=${page.url()}`);
  await page.waitForTimeout(3000);
  await shot('01-landing');

  // 2) 关弹窗
  await closePopups(page);
  await page.waitForTimeout(1500);
  await shot('02-after-popups');

  // 3) 若列表未出现，反复：点「商品列表」导航 / reload，直到看到在售中或全部标签
  for (let attempt = 1; attempt <= 4; attempt++) {
    const hasList = await page
      .getByText(/在售中\s*\d|全部\s*\d|待审核|已下架|商品流量/)
      .first()
      .isVisible({ timeout: 2000 })
      .catch(() => false);
    log.info(`第 ${attempt} 次检查列表：hasList=${hasList}`);
    if (hasList) break;

    // 尝试点左侧「商品列表」菜单项
    const navItem = page.getByText('商品列表', { exact: true }).first();
    if (await navItem.isVisible({ timeout: 1000 }).catch(() => false)) {
      log.info('点击左侧「商品列表」菜单…');
      await navItem.click({ timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(4000);
      await closePopups(page);
    } else {
      log.info('未见「商品列表」菜单项，reload 重试…');
      await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
      await page.waitForTimeout(4000);
      await closePopups(page);
    }
  }
  await shot('03-after-navclick');

  // 4) 滚动触发懒加载 + 等接口
  await page.mouse.wheel(0, 600).catch(() => {});
  await page.waitForTimeout(2500);
  await shot('04-final');
  writeFileSync(p('probe-final.html'), await page.content().catch(() => ''), 'utf8');

  // 5) frames 清点（确认有没有 iframe 藏内容）
  const frames = page.frames().map((f) => `${f.name() || '(no-name)'}  ${f.url()}`);
  writeFileSync(p('probe-frames.txt'), frames.join('\n'), 'utf8');
  log.info(`frames 数量=${frames.length}`);

  // 6) 店铺切换器：截图右上角区域 + 尝试点击一批候选后截图
  await shot('05-topbar');
  const SW = [
    '[class*="MallSelect"]', '[class*="mall-select"]', '[class*="Mall_"]', '[class*="mall_"]',
    '[class*="shopSelect"]', '[class*="StoreSelect"]', '[class*="mallName" i]', '[class*="shopName" i]',
    '[class*="account" i]', 'header [class*="select" i]', 'header [class*="dropdown" i]',
  ];
  let swHit = '';
  for (const sel of SW) {
    const el = page.locator(sel).first();
    if (await el.isVisible({ timeout: 300 }).catch(() => false)) {
      await el.click({ timeout: 1200 }).catch(() => {});
      await page.waitForTimeout(1000);
      swHit = sel;
      break;
    }
  }
  await shot('06-switcher-open');
  writeFileSync(p('probe-switcher.html'), await page.content().catch(() => ''), 'utf8');
  writeFileSync(p('probe-switcher-meta.txt'), `swHit=${swHit}\n候选:\n${SW.join('\n')}\n`, 'utf8');

  // 保存响应清单 + body 索引
  writeFileSync(p('probe-responses.txt'), respLog.join('\n'), 'utf8');
  writeFileSync(p('probe-body-index.txt'), bodyIndex.join('\n'), 'utf8');
  log.info(`响应 ${respLog.length} 条，保存 body ${bodyIdx} 个。截图：${shots.join(', ')}`);

  log.info('保持浏览器 25 秒，可手动点开店铺切换器观察。之后自动关闭。');
  await page.waitForTimeout(25000);
  await shot('07-manual');
  writeFileSync(p('probe-switcher-manual.html'), await page.content().catch(() => ''), 'utf8');
  await context.close().catch(() => {});
}

main().then(() => process.exit(0)).catch((e) => { log.error(e); process.exit(1); });
