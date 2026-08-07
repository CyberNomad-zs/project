// 验证：真实 Chrome + 复用登录态，能否登录成功 + 商品网格出数据。
// VD_HEADLESS=1 → headless（避开有头软渲崩溃）；否则有头。
import { loadConfig } from './src/config.js';
import { launchBrowser, gotoWithRetry, waitForGoodsList } from './src/browser.js';
import { log } from './src/logger.js';

const OUT = 'C:\\Users\\Administrator\\AppData\\Local\\Temp\\claude\\E--project-temu\\39c2c9b3-8b05-4fa9-a38d-ee426277b3c7\\scratchpad\\verify-detect.png';
const headless = process.env.VD_HEADLESS === '1';

const cfg = loadConfig();
log.info('mode:', headless ? 'HEADLESS' : 'HEADED', ' channel=', cfg.channel, ' userDataDir=', cfg.userDataDir);

const { context, page } = await launchBrowser(cfg, { headless });
try {
  const navOk = await gotoWithRetry(page, cfg.goodsListUrl, cfg);
  const url = page.url();
  log.info('navOk=', navOk, ' url=', url);

  if (page.isClosed()) {
    log.error('❌ 页面已崩溃关闭（frame detached / 渲染进程崩溃）。');
  } else {
    const isAuth = /auth|login|signin|authentication/i.test(url);
    log.info(isAuth ? '❌ 未登录：被重定向到认证页' : '✔ 已登录：未跳认证页');

    const gridOk = await waitForGoodsList(page, { timeout: cfg.navTimeoutMs });
    log.info('waitForGoodsList=', gridOk);
    if (!page.isClosed()) await page.waitForTimeout(6000).catch(() => {});

    const tabs = await page.getByText(/全部\s*\d+|在售中\s*\d+/).allInnerTexts().catch(() => []);
    log.info('TABS:', JSON.stringify(tabs));
    const skcCount = await page.getByText(/SKC\s*ID/i).count().catch(() => 0);
    const loading = await page.getByText(/加载中/).first().isVisible().catch(() => false);
    log.info('商品行(SKC ID 数)=', skcCount, ' 页面「加载中」=', loading);

    await page.screenshot({ path: OUT }).catch((e) => log.warn('截图失败', e.message));
    log.info('截图:', OUT);

    log.info(!isAuth && skcCount > 0 && !loading
      ? '✅ 成功：已登录且商品网格出数据！'
      : '⚠️ 未达成：见上面各项判断。');
  }
} finally {
  if (!page.isClosed()) await page.waitForTimeout(1000).catch(() => {});
  await context.close().catch(() => {});
}
