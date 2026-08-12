import { log } from './logger.js';

/**
 * 通用弹窗关闭策略。登录成功后 / 切换店铺时 / 页面加载后会弹出多种不固定的弹窗，
 * 需求明确「一律关闭，可能还会有其他类型的弹窗，都关闭」。已知类型包括：
 *   - 推广券 / 调价提效 / 店铺提效 / 新功能提示等营销弹窗
 *   - 「您有以下待办任务需要尽快处理」待办任务模态框（右上角 X）
 *   - 点击「消息」后弹出的「全部消息」通知面板 / 「商品不合规，影响售卖」通知（右上角 X）
 * 策略：多轮「文本按钮 + 关闭图标 + Esc」清扫，不依赖单一选择器。
 */

// 需要点击的按钮文本（精确/包含匹配）。仅放「关闭/忽略」类，绝不放「去处理/去填写」等会跳转的按钮。
const DISMISS_TEXTS = [
  '稍后再说', '我知道了', '知道了', '暂不领取', '暂不参与',
  '以后再说', '下次再说', '不再提示', '暂不处理', '取消', '关闭',
];

// 关闭图标的候选选择器（Temu / 常见 UI 库）
const CLOSE_ICON_SELECTORS = [
  '[aria-label="close"]',
  '[aria-label="关闭"]',
  '[aria-label="Close"]',
  '.ant-modal-close',
  '.ant-drawer-close',
  '.ant-notification-notice-close',
  '[class*="closeIcon"]',
  '[class*="close-icon"]',
  '[class*="Close_"]',
  '[class*="_close"]',
  '[class*="closeBtn" i]',
  '[class*="close-btn" i]',
  'button[class*="close" i]',
  'span[class*="close" i]',
  'i[class*="close" i]',
  'svg[class*="close" i]',
  '[class*="icon" i][class*="close" i]',
];

// 已知弹窗的标题/关键文本。命中后在其容器内优先点关闭图标（这类弹窗没有「关闭」文本按钮，
// 只有右上角 X，且往往带「去处理」等会跳转的按钮，绝不能误点）。
const KNOWN_DIALOG_KEYWORDS = [
  '待办任务需要尽快处理', // 待办任务模态框
  '全部消息',             // 消息通知面板
  '商品不合规',           // 违规通知
];

/**
 * 关闭当前页面上所有可见弹窗。多轮尝试直到无可关闭项或达到上限。
 * @param {import('playwright').Page} page
 */
export async function closePopups(page, { rounds = 4 } = {}) {
  let totalClosed = 0;
  for (let r = 0; r < rounds; r++) {
    let closedThisRound = 0;

    // 1) 文本按钮
    for (const t of DISMISS_TEXTS) {
      const btn = page.getByRole('button', { name: t, exact: false }).first();
      if (await safeClick(btn)) { closedThisRound++; continue; }
      const el = page.getByText(t, { exact: true }).first();
      if (await safeClick(el)) closedThisRound++;
    }

    // 2) 已知弹窗：按标题关键字定位其容器，点容器内的关闭图标（避免误点「去处理」等跳转按钮）
    for (const kw of KNOWN_DIALOG_KEYWORDS) {
      const anchor = page.getByText(kw, { exact: false }).first();
      if (!(await anchor.isVisible({ timeout: 300 }).catch(() => false))) continue;
      // 容器 class 关键词放宽：除 modal/dialog/drawer/popover 外，
      // 「全部消息 / 商品不合规」是自定义通知面板，class 多为 notice/notification/message/panel/popup/card
      const container = anchor.locator(
        'xpath=ancestor::*[contains(translate(@class,"MDNPCS","mdnpcs"),"modal") or contains(translate(@class,"MDNPCS","mdnpcs"),"dialog") or contains(translate(@class,"MDNPCS","mdnpcs"),"drawer") or contains(translate(@class,"MDNPCS","mdnpcs"),"popover") or contains(translate(@class,"MDNPCS","mdnpcs"),"notice") or contains(translate(@class,"MDNPCS","mdnpcs"),"notification") or contains(translate(@class,"MDNPCS","mdnpcs"),"message") or contains(translate(@class,"MDNPCS","mdnpcs"),"panel") or contains(translate(@class,"MDNPCS","mdnpcs"),"popup") or contains(translate(@class,"MDNPCS","mdnpcs"),"card")][1]'
      ).first();
      // 依次尝试：命中的语义容器 → 逐级放大的祖先（2/4/6 层），在其中找关闭图标
      const scopes = [];
      if (await container.count().catch(() => 0)) scopes.push(container);
      for (const depth of [2, 4, 6]) scopes.push(anchor.locator(`xpath=ancestor::*[${depth}]`).first());
      let done = false;
      for (const scope of scopes) {
        for (const sel of CLOSE_ICON_SELECTORS) {
          const icon = scope.locator(sel).first();
          if (await safeClick(icon)) { closedThisRound++; done = true; break; }
        }
        if (done) break;
      }
    }

    // 3) 关闭图标（全页兜底）
    for (const sel of CLOSE_ICON_SELECTORS) {
      const icons = page.locator(sel);
      const n = Math.min(await icons.count().catch(() => 0), 5);
      for (let i = 0; i < n; i++) {
        if (await safeClick(icons.nth(i))) closedThisRound++;
      }
    }

    // 4) 兜底 Esc（关闭 modal / drawer）
    await page.keyboard.press('Escape').catch(() => {});

    totalClosed += closedThisRound;
    if (closedThisRound === 0) break;
    await page.waitForTimeout(600);
  }
  if (totalClosed > 0) log.info(`关闭弹窗 ${totalClosed} 个`);
  return totalClosed;
}

async function safeClick(locator) {
  try {
    if (!(await locator.isVisible({ timeout: 400 }))) return false;
    await locator.click({ timeout: 1200, force: true });
    return true;
  } catch {
    return false;
  }
}
