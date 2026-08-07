import { STORAGE_KEYS, DEFAULT_CONFIG, LOG_LIMIT } from './constants.js';

export async function getConfig() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.CONFIG);
  const raw = data[STORAGE_KEYS.CONFIG] || {};
  return deepMerge(structuredClone(DEFAULT_CONFIG), raw);
}

export async function saveConfig(partial) {
  const current = await getConfig();
  const next = deepMerge(current, partial);
  await chrome.storage.local.set({ [STORAGE_KEYS.CONFIG]: next });
  return next;
}

export async function getLogs() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.LOGS);
  return data[STORAGE_KEYS.LOGS] || [];
}

export async function appendLog(entry) {
  const logs = await getLogs();
  logs.unshift({
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    time: new Date().toISOString(),
    ...entry
  });
  if (logs.length > LOG_LIMIT) logs.length = LOG_LIMIT;
  await chrome.storage.local.set({ [STORAGE_KEYS.LOGS]: logs });
  return logs[0];
}

export async function clearLogs() {
  await chrome.storage.local.set({ [STORAGE_KEYS.LOGS]: [] });
}

export async function getLastResult() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.LAST_RESULT);
  return data[STORAGE_KEYS.LAST_RESULT] || null;
}

export async function saveLastResult(result) {
  await chrome.storage.local.set({ [STORAGE_KEYS.LAST_RESULT]: result });
}

export async function getFeishuTokenCache() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.FEISHU_TOKEN);
  return data[STORAGE_KEYS.FEISHU_TOKEN] || null;
}

export async function setFeishuTokenCache(token, expireAt) {
  await chrome.storage.local.set({
    [STORAGE_KEYS.FEISHU_TOKEN]: { token, expireAt }
  });
}

function deepMerge(base, patch) {
  if (!patch || typeof patch !== 'object') return base;
  const out = { ...base };
  for (const [k, v] of Object.entries(patch)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && typeof base[k] === 'object' && base[k] && !Array.isArray(base[k])) {
      out[k] = deepMerge(base[k], v);
    } else if (v !== undefined) {
      out[k] = v;
    }
  }
  return out;
}
