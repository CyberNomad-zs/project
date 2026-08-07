import { log } from './logger.js';

/**
 * 店铺枚举 / 切换。真实后台用顶部「来源店铺」下拉筛选商品来源店铺
 * （不是右上角切换器）。beast-core UI 库，下拉展开后选项为浮层元素。
 *
 * 注意：实测该 agentseller 账号下仅 1 个店铺，「全球」聚合视图即其全部商品，
 * 因此单店铺时 run.js 直接监测聚合视图、不做切换（见 run.js）。以下函数为
 * 多店铺场景保留。
 */

/** 定位「来源店铺」下拉的可点触发区 */
function storeSelectBox(page) {
  const label = page.getByText('来源店铺', { exact: false }).first();
  return label.locator(
    'xpath=following::*[@role="combobox" or contains(@class,"Select") or contains(@class,"select")][1]'
  ).first();
}

/** 从展开的下拉浮层里读店铺名（排除分页/全选等噪声） */
async function readOptions(page) {
  return page.evaluate(() => {
    const bad = /^(全选|每页.*|共有.*|上一页|下一页|\d+|请选择|重置|确定|查询|取消)$/;
    const els = [...document.querySelectorAll('[role="option"],[class*="option" i],[class*="Option" i],li')];
    const vis = els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    return [...new Set(vis.map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 60 && !bad.test(t)))];
  });
}

/**
 * 枚举账号下全部店铺名。
 * @returns {Promise<string[]>}
 */
export async function listStores(page) {
  const label = page.getByText('来源店铺', { exact: false }).first();
  if (!(await label.isVisible({ timeout: 8000 }).catch(() => false))) {
    log.warn('未找到「来源店铺」筛选，按单店铺处理。');
    return [];
  }
  await storeSelectBox(page).click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(1500);
  const names = await readOptions(page);
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(500);
  log.info(`枚举到 ${names.length} 个店铺：`, names);
  return names;
}

/**
 * 通过「来源店铺」下拉选择指定店铺并点「查询」。
 * @returns {Promise<boolean>}
 */
export async function switchStore(page, storeName, cfg) {
  const label = page.getByText('来源店铺', { exact: false }).first();
  if (!(await label.isVisible({ timeout: 8000 }).catch(() => false))) return false;
  await storeSelectBox(page).click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(1200);
  const opt = page.getByText(storeName, { exact: false }).first();
  if (!(await opt.isVisible({ timeout: 2000 }).catch(() => false))) {
    log.warn(`来源店铺下拉中未找到「${storeName}」`);
    await page.keyboard.press('Escape').catch(() => {});
    return false;
  }
  await opt.click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(500);
  const query = page.getByText(/^查询$/).first();
  if (await query.isVisible({ timeout: 1500 }).catch(() => false)) {
    await query.click({ timeout: 2000 }).catch(() => {});
  }
  await page.waitForTimeout(2500);
  return true;
}
