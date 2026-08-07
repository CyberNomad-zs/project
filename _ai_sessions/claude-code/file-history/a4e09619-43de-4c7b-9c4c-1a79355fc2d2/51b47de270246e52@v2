/**
 * OpenAPI 配置加载
 * 优先级：openapi.config.json > config.json.openapi > 环境变量
 * 密钥文件 openapi.config.json 已加入 .gitignore，勿提交。
 */
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from '../config.js';

const REGIONS = {
  global: 'https://openapi-b-global.temu.com',
  us: 'https://openapi-b-us.temu.com',
  eu: 'https://openapi-b-eu.temu.com',
};

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * @returns {object|null} 未配置时返回 null
 */
export function loadOpenApiConfig() {
  const main = readJson(resolve(ROOT, 'config.json')) || {};
  const local = readJson(resolve(ROOT, 'openapi.config.json')) || {};
  const raw = { ...(main.openapi || {}), ...local };

  const appKey = String(raw.appKey || raw.app_key || process.env.TEMU_APP_KEY || '').trim();
  const appSecret = String(raw.appSecret || raw.app_secret || process.env.TEMU_APP_SECRET || '').trim();

  let baseUrl = String(raw.baseUrl || raw.base_url || '').trim();
  if (!baseUrl) {
    const region = String(raw.region || 'global').toLowerCase();
    baseUrl = REGIONS[region] || REGIONS.global;
  }
  baseUrl = baseUrl.replace(/\/$/, '');
  if (!/\/openapi\/router$/i.test(baseUrl) && !baseUrl.includes('openapi-b-')) {
    // 允许用户只填 host
  }
  // 若用户误填了完整 router URL，剥掉 path
  baseUrl = baseUrl.replace(/\/openapi\/router\/?$/i, '');

  const stores = Array.isArray(raw.stores)
    ? raw.stores.map((s) => ({
        name: String(s.name || s.storeName || s.mallId || '未命名店铺').trim(),
        accessToken: String(s.accessToken || s.access_token || '').trim(),
        mallId: s.mallId || s.mall_id || null,
        enabled: s.enabled !== false,
        baseUrl: s.baseUrl || s.base_url || null, // 单店可覆盖区域
      })).filter((s) => s.name)
    : [];

  // 飞书：优先 openapi 段，否则沿用主 config
  const feishuWebhooks = (Array.isArray(raw.feishuWebhooks)
    ? raw.feishuWebhooks
    : [raw.feishuWebhook, ...(main.feishuWebhooks || []), main.feishuWebhook])
    .map((s) => String(s || '').trim())
    .filter(Boolean);
  // 去重
  const hooks = [...new Set(feishuWebhooks)];

  const cfg = {
    enabled: raw.enabled !== false,
    appKey,
    appSecret,
    baseUrl,
    region: raw.region || 'global',
    stores,
    intervalMinutes: Number(raw.intervalMinutes || main.intervalMinutes) || 15,
    apiMode: raw.apiMode === 'listRetrieve' ? 'listRetrieve' : 'listQuery',
    pageSize: Number(raw.pageSize) || 100,
    forceAssumeActiveOnType1: raw.forceAssumeActiveOnType1 === true,
    editBaseUrl: raw.editBaseUrl || main.goodsListUrl?.replace(/\/goods\/list.*$/, '') || 'https://agentseller.temu.com',
    debug: raw.debug === true || process.env.OPENAPI_DEBUG === '1',
    alerts: {
      delist: raw.alerts?.delist !== false,
      lowTraffic: raw.alerts?.lowTraffic !== false,
      restrictedTraffic: raw.alerts?.restrictedTraffic !== false,
    },
    feishuWebhooks: hooks,
    feishuSecret: raw.feishuSecret || main.feishuSecret || '',
    stateFile: resolve(ROOT, raw.stateFile || 'data/openapi-state.json'),
  };

  return cfg;
}

export function openApiConfigReady(cfg) {
  if (!cfg) return { ok: false, reason: '无配置' };
  if (!cfg.appKey || !cfg.appSecret) return { ok: false, reason: '缺少 appKey/appSecret' };
  const enabledStores = (cfg.stores || []).filter((s) => s.enabled && s.accessToken);
  if (!enabledStores.length) return { ok: false, reason: '没有配置带 accessToken 的店铺' };
  return { ok: true, stores: enabledStores };
}

export function exampleConfigPath() {
  return resolve(ROOT, 'openapi.config.example.json');
}

export function configPath() {
  return resolve(ROOT, 'openapi.config.json');
}

export function hasLocalConfig() {
  return existsSync(configPath());
}
