/**
 * 赛狐监测配置
 * 文件：temu-monitor/sellfox.config.json（gitignore）
 * 可回落主 config.json.sellfox + 环境变量
 */
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from '../config.js';

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

export function configPath() {
  return resolve(ROOT, 'sellfox.config.json');
}

export function exampleConfigPath() {
  return resolve(ROOT, 'sellfox.config.example.json');
}

export function loadSellfoxConfig() {
  const main = readJson(resolve(ROOT, 'config.json')) || {};
  const local = readJson(configPath()) || {};
  const raw = { ...(main.sellfox || {}), ...local };

  const clientId = String(raw.clientId || raw.client_id || process.env.SELLFOX_CLIENT_ID || '').trim();
  const clientSecret = String(raw.clientSecret || raw.client_secret || process.env.SELLFOX_CLIENT_SECRET || '').trim();
  const baseUrl = String(raw.baseUrl || raw.base_url || 'https://openapi.sellfox.com').replace(/\/$/, '');

  const defaultShops = [
    { shopId: '396706', name: 'Agnis' },
    { shopId: '398202', name: 'HomeCove' },
    { shopId: '398203', name: 'Twilight Cove' },
  ];

  let stores = Array.isArray(raw.stores) ? raw.stores : null;
  if (!stores || !stores.length) {
    const ids = raw.shopIds || raw.shop_whitelist || [];
    stores = (ids.length ? ids : defaultShops.map((s) => s.shopId)).map((id) => {
      const sid = String(id);
      const known = defaultShops.find((s) => s.shopId === sid);
      return { shopId: sid, name: known?.name || sid, enabled: true };
    });
  } else {
    stores = stores.map((s) => ({
      shopId: String(s.shopId || s.shop_id || ''),
      name: String(s.name || s.shopName || s.shopId || ''),
      enabled: s.enabled !== false,
    })).filter((s) => s.shopId);
  }

  const hooks = [
    ...(Array.isArray(raw.feishuWebhooks) ? raw.feishuWebhooks : [raw.feishuWebhook]),
    ...(Array.isArray(main.feishuWebhooks) ? main.feishuWebhooks : [main.feishuWebhook]),
  ]
    .map((s) => String(s || '').trim())
    .filter(Boolean);
  const feishuWebhooks = [...new Set(hooks)];

  return {
    enabled: raw.enabled !== false,
    clientId,
    clientSecret,
    baseUrl,
    stores,
    intervalMinutes: Number(raw.intervalMinutes || main.intervalMinutes) || 15,
    pageSize: Number(raw.pageSize) || 100,
    maxPagesPerWindow: Number(raw.maxPagesPerWindow) || 50,
    dateType: raw.dateType || 'updateDate',
    lookbackDays: Number(raw.lookbackDays) || 30,
    editBaseUrl: raw.editBaseUrl || 'https://agentseller.temu.com',
    debug: raw.debug === true || process.env.SELLFOX_DEBUG === '1',
    alerts: {
      delist: raw.alerts?.delist !== false,
      // 上架：本轮 selectStatus=12 且上轮不在在售集合
      onshelf: raw.alerts?.onshelf !== false,
    },
    feishuWebhooks,
    feishuSecret: raw.feishuSecret || main.feishuSecret || '',
    stateFile: resolve(ROOT, raw.stateFile || 'data/sellfox-state.json'),
  };
}

export function sellfoxConfigReady(cfg) {
  if (!cfg) return { ok: false, reason: '无配置' };
  if (!cfg.clientId || !cfg.clientSecret) return { ok: false, reason: '缺少 clientId/clientSecret' };
  const shops = (cfg.stores || []).filter((s) => s.enabled !== false && s.shopId);
  if (!shops.length) return { ok: false, reason: '没有 enabled 的店铺 shopId' };
  return { ok: true, shops };
}

export function shopNameMap(cfg) {
  const m = {};
  for (const s of cfg.stores || []) {
    if (s.shopId) m[s.shopId] = s.name || s.shopId;
  }
  return m;
}

export function hasLocalConfig() {
  return existsSync(configPath());
}
