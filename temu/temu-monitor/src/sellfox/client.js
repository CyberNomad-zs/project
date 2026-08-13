/**
 * 赛狐开放平台客户端（对齐 sellfox-bridge/bridge/clients/sellfox.py）
 * - GET /api/oauth/v2/token.json
 * - 业务 POST：query 带 access_token/client_id/timestamp/nonce/sign
 * - 签名：HMAC-SHA256(client_secret, 字典序 k=v 用 & 拼接)；body 不参与签名
 */
import crypto from 'node:crypto';
import { log } from '../logger.js';

export class SellfoxError extends Error {
  constructor(code, msg, requestId) {
    super(`sellfox code=${code} msg=${msg}${requestId ? ` requestId=${requestId}` : ''}`);
    this.code = code;
    this.msg = msg;
    this.requestId = requestId;
  }
}

/**
 * @param {{ baseUrl?: string, clientId: string, clientSecret: string, timeoutMs?: number, debug?: boolean }} opts
 */
export function createSellfoxClient(opts) {
  const baseUrl = String(opts.baseUrl || 'https://openapi.sellfox.com').replace(/\/$/, '');
  const clientId = String(opts.clientId || '').trim();
  const clientSecret = String(opts.clientSecret || '').trim();
  const timeoutMs = Number(opts.timeoutMs) || 60000;
  const debug = !!opts.debug;

  if (!clientId || !clientSecret) {
    throw new Error('sellfox 缺少 clientId / clientSecret');
  }

  let token = null;
  let tokenExpireAt = 0; // epoch seconds

  async function getToken() {
    const now = Date.now() / 1000;
    if (token && now < tokenExpireAt - 600) return token;
    const url = new URL(`${baseUrl}/api/oauth/v2/token.json`);
    url.searchParams.set('client_id', clientId);
    url.searchParams.set('client_secret', clientSecret);
    url.searchParams.set('grant_type', 'client_credentials');
    const resp = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(timeoutMs) });
    const body = await resp.json().catch(() => ({}));
    if (body.code !== 0) {
      throw new SellfoxError(body.code, body.msg || resp.statusText, body.requestId);
    }
    token = body.data.access_token;
    // 文档/实调：expires_in 多为毫秒
    const exp = Number(body.data.expires_in) || 86400000;
    tokenExpireAt = now + (exp > 1e6 ? exp / 1000 : exp);
    log.info('Sellfox token refreshed');
    return token;
  }

  function sign(urlPath, accessToken, timestamp, nonce) {
    const params = {
      access_token: accessToken,
      client_id: clientId,
      method: 'post',
      nonce: String(nonce),
      timestamp: String(timestamp),
      url: urlPath,
    };
    const data = Object.keys(params)
      .sort()
      .map((k) => `${k}=${params[k]}`)
      .join('&');
    return crypto.createHmac('sha256', clientSecret).update(data, 'utf8').digest('hex');
  }

  /**
   * @param {string} urlPath 如 /api/multiplatform/temu/product/getParentPageList.json
   * @param {object} body
   */
  async function post(urlPath, body = {}, retries = 5) {
    let lastErr = null;
    for (let attempt = 0; attempt < retries; attempt++) {
      const accessToken = await getToken();
      const ts = Date.now();
      const nonce = Math.floor(Math.random() * 99999) + 1;
      const q = new URLSearchParams({
        access_token: accessToken,
        client_id: clientId,
        timestamp: String(ts),
        nonce: String(nonce),
        sign: sign(urlPath, accessToken, ts, nonce),
      });
      const url = `${baseUrl}${urlPath}?${q}`;
      if (debug) log.info('Sellfox POST', urlPath, body);

      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(timeoutMs),
        });
        const text = await resp.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          lastErr = new Error(`非 JSON HTTP ${resp.status}: ${text.slice(0, 200)}`);
          await sleep(2 ** attempt * 400);
          continue;
        }
        if (data.code === 0) return data.data;
        // 40019 限流：退避重试
        if ((data.code === 40019 || /超过限制|rate|限流/i.test(String(data.msg || ''))) && attempt < retries - 1) {
          const wait = 1500 * (attempt + 1);
          log.warn(`Sellfox 限流 code=${data.code}，${wait}ms 后重试`);
          await sleep(wait);
          continue;
        }
        if (String(data.msg || '').toLowerCase().includes('token') && attempt < retries - 1) {
          token = null;
          continue;
        }
        throw new SellfoxError(data.code, data.msg, data.requestId);
      } catch (e) {
        if (e instanceof SellfoxError) throw e;
        lastErr = e;
        log.warn(`Sellfox ${urlPath} 网络异常(${attempt + 1}): ${e.message}`);
        await sleep(2 ** attempt * 400);
      }
    }
    throw new SellfoxError(-1, `重试仍失败: ${lastErr && lastErr.message}`);
  }

  /** Temu 跨境父体分页（startDate/endDate 间隔 ≤30 天） */
  async function temuCrossParentPage({
    pageNo = 1,
    pageSize = 100,
    shopIds,
    dateType = 'updateDate',
    startDate,
    endDate,
  } = {}) {
    const body = {
      pageNo: Number(pageNo),
      pageSize: Number(pageSize),
      dateType: dateType || 'updateDate',
      startDate: startDate || '2020-01-01',
      endDate: endDate || ymd(new Date()),
    };
    if (shopIds?.length) body.shopIdList = shopIds.map(String);
    return post('/api/multiplatform/temu/product/getParentPageList.json', body);
  }

  /**
   * Temu 跨境店在线产品子体（SKU）——按 parentId。
   * 实调 2026-08-12：返回数组，字段含 skuId/specName/extCode/stockQuantity 等；
   * 无 selectStatus（上下架仍看父体 getParentPageList）。
   * @param {string} parentId
   */
  async function temuCrossChildInfo(parentId) {
    return post('/api/multiplatform/temu/product/getChildInfo.json', {
      parentId: String(parentId),
    });
  }

  return { post, getToken, temuCrossParentPage, temuCrossChildInfo, baseUrl, clientId };
}

function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export { ymd };
