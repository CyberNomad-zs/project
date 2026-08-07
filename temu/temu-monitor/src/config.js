import { readFileSync, writeFileSync, existsSync, copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = resolve(__dirname, '..');

/**
 * 确保有 config.json：缺失时从 config.example.json 自动复制（同事首次解压常见）。
 * @returns {string} 实际使用的配置路径
 */
export function ensureConfigFile() {
  const dest = resolve(ROOT, 'config.json');
  if (existsSync(dest)) return dest;
  const ex = resolve(ROOT, 'config.example.json');
  if (existsSync(ex)) {
    copyFileSync(ex, dest);
    console.warn(
      `[WARN] 未找到 config.json，已从 config.example.json 自动生成。\n` +
        `       请编辑 ${dest}\n` +
        `       - feishuWebhooks：自己的飞书机器人\n` +
        `       - storeList：要盯的店名\n` +
        `       - fullRun 保持 false\n`,
    );
    return dest;
  }
  // 最后兜底写一份最小配置，避免直接崩
  const minimal = {
    feishuWebhooks: [],
    intervalMinutes: 15,
    stores: 'all',
    storeList: ['Agnis', 'HomeCove', 'Twilight Cove'],
    fullRun: false,
    headless: true,
    proxy: '',
    userDataDir: './.userdata',
    channel: 'chrome',
  };
  writeFileSync(dest, JSON.stringify(minimal, null, 2), 'utf8');
  console.warn(`[WARN] 已写入最小 config.json：${dest}（请补飞书 webhook 与 storeList）`);
  return dest;
}

/** 读取并规范化 config.json */
export function loadConfig() {
  const path = ensureConfigFile();
  const raw = JSON.parse(readFileSync(path, 'utf8'));
  return {
    // 告警目标群 webhook：支持单个字符串或数组（多个群同发）。兼容旧字段 feishuWebhook。
    feishuWebhooks: (Array.isArray(raw.feishuWebhooks)
      ? raw.feishuWebhooks
      : [raw.feishuWebhooks ?? raw.feishuWebhook ?? ''])
      .map((s) => String(s || '').trim()).filter(Boolean),
    feishuSecret: raw.feishuSecret || '',
    intervalMinutes: Number(raw.intervalMinutes) || 15,
    stores: raw.stores || 'all',
    // 多店会话切店清单（店名与卖家中心顶栏英文名一致）。默认三店。
    storeList: Array.isArray(raw.storeList)
      ? raw.storeList
      : ['Agnis', 'HomeCove', 'Twilight Cove'],
    // 默认 false：本机只跑浏览器流量，不碰赛狐（避免同事电脑无白名单报错）。
    // 上下架请用服务器 `npm run sellfox:start`，或显式 fullRun:true / FULL_RUN=1 联调。
    fullRun: raw.fullRun === true || process.env.FULL_RUN === '1' || process.env.FULL_RUN === 'true',
    alerts: {
      onSaleDrop: raw.alerts?.onSaleDrop !== false,
      trafficAnomaly: raw.alerts?.trafficAnomaly !== false,
      // 赛狐下架 / 上架点名（fullRun 时启用，默认都开）
      delist: raw.alerts?.delist !== false,
      onshelf: raw.alerts?.onshelf !== false,
      // 登录过期/连续监测失败时发飞书提醒，避免登录态失效后静默死掉没人知道
      loginExpiry: raw.alerts?.loginExpiry !== false,
    },
    // 连续失败达到该轮次才发登录过期告警（默认 2 轮 ≈ 30 分钟，滤掉偶发抖动）
    loginAlertAfterRounds: Number(raw.loginAlertAfterRounds) || 2,
    // 仍未恢复时每隔多少轮再提醒一次（默认 16 轮 ≈ 4 小时，避免刷屏）
    loginRealertRounds: Number(raw.loginRealertRounds) || 16,
    headless: raw.headless === true,
    // 代理：config.proxy 若为字符串（含空串）则以它为准——空串 = 强制直连，
    // 不再回落系统 HTTPS_PROXY（实测本机 7897 代理会频繁 ERR_CONNECTION_CLOSED，直连反而稳）。
    // 仅当 config.json 完全没有 proxy 字段时才跟随系统环境变量。
    proxy: typeof raw.proxy === 'string' ? raw.proxy : (process.env.HTTPS_PROXY || process.env.HTTP_PROXY || ''),
    loginUrl: raw.loginUrl || 'https://agentseller.temu.com/goods/list',
    goodsListUrl: raw.goodsListUrl || 'https://agentseller.temu.com/goods/list',
    userDataDir: resolve(ROOT, raw.userDataDir || './.userdata'),
    // 浏览器 channel：默认 'chrome' = 用系统真实 Chrome（指纹与真人一致，最不易被风控识别）。
    // 设为 '' 或 'chromium' 则回落 Playwright 内置 Chromium。
    channel: raw.channel === '' ? '' : (raw.channel || 'chrome'),
    // 可选：显式指定 chrome.exe 路径，优先级高于 channel。
    executablePath: raw.executablePath || '',
    perStoreTimeoutMs: Number(raw.perStoreTimeoutMs) || 60000,
    navTimeoutMs: Number(raw.navTimeoutMs) || 60000,
  };
}
