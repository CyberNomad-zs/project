/**
 * 飞书 tenant_access_token 获取与缓存
 */

import { FEISHU } from '../lib/constants.js';
import { getConfig, getFeishuTokenCache, setFeishuTokenCache } from '../lib/storage.js';

/**
 * @param {boolean} [forceRefresh]
 * @returns {Promise<string>}
 */
export async function getTenantAccessToken(forceRefresh = false) {
  if (!forceRefresh) {
    const cache = await getFeishuTokenCache();
    if (cache?.token && cache.expireAt && Date.now() < cache.expireAt - 60_000) {
      return cache.token;
    }
  }

  const config = await getConfig();
  const { appId, appSecret } = config.feishu || {};
  if (!appId || !appSecret) {
    throw new Error('请先在插件设置中填写飞书 App ID 与 App Secret');
  }

  const res = await fetch(FEISHU.TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({
      app_id: appId,
      app_secret: appSecret
    })
  });

  const json = await res.json();
  if (json.code !== 0 || !json.tenant_access_token) {
    throw new Error(
      `飞书获取 token 失败: code=${json.code} msg=${json.msg || JSON.stringify(json)}`
    );
  }

  const expireAt = Date.now() + (json.expire || 7200) * 1000;
  await setFeishuTokenCache(json.tenant_access_token, expireAt);
  return json.tenant_access_token;
}
