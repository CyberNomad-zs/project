/**
 * Temu Partner OpenAPI 客户端（签名 + 调用）
 * 签名算法对齐官方/社区 SDK（temu_api）：
 *   1. 公共参数 + 业务参数（不含 sign）
 *   2. key 字典序
 *   3. 拼接 key+value（对象/数组用紧凑 JSON）
 *   4. app_secret + 拼接串 + app_secret → MD5 大写
 */
import crypto from 'node:crypto';
import { log } from '../logger.js';

/** 参与签名的 value 序列化（对齐 Python str + 去空格/单引号转双引号） */
export function serializeForSign(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  // list/dict：紧凑 JSON，无空格，双引号
  return JSON.stringify(value);
}

export function buildSign(appSecret, params) {
  const keys = Object.keys(params).filter((k) => k !== 'sign').sort();
  let result = '';
  for (const k of keys) {
    const v = params[k];
    if (v === null || v === undefined) continue;
    result += k + serializeForSign(v);
  }
  result = result.replace(/ /g, '').replace(/'/g, '"');
  const raw = `${appSecret}${result}${appSecret}`;
  return crypto.createHash('md5').update(raw, 'utf8').digest('hex').toUpperCase();
}

function filterNone(obj) {
  if (Array.isArray(obj)) return obj.map(filterNone).filter((v) => v !== undefined);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (v === null || v === undefined) continue;
      out[k] = filterNone(v);
    }
    return out;
  }
  return obj;
}

/**
 * @param {{ appKey: string, appSecret: string, accessToken?: string, baseUrl: string, debug?: boolean }} opts
 */
export function createOpenApiClient(opts) {
  const appKey = String(opts.appKey || '').trim();
  const appSecret = String(opts.appSecret || '').trim();
  const baseUrl = String(opts.baseUrl || 'https://openapi-b-global.temu.com').replace(/\/$/, '');
  const debug = !!opts.debug;

  if (!appKey || !appSecret) {
    throw new Error('openapi 缺少 appKey / appSecret（请配置 openapi.config.json）');
  }

  /**
   * @param {string} type API 名，如 bg.local.goods.list.query
   * @param {object} [biz] 业务参数
   * @param {{ accessToken?: string }} [callOpts]
   */
  async function call(type, biz = {}, callOpts = {}) {
    const accessToken = String(callOpts.accessToken || opts.accessToken || '').trim();
    if (!accessToken) throw new Error(`调用 ${type} 需要 access_token`);

    const timestamp = Math.floor(Date.now() / 1000);
    const body = filterNone({
      type,
      app_key: appKey,
      access_token: accessToken,
      timestamp,
      data_type: 'JSON',
      ...biz,
    });
    body.sign = buildSign(appSecret, body);

    const url = `${baseUrl}/openapi/router`;
    if (debug) {
      const safe = { ...body, access_token: mask(body.access_token), sign: body.sign?.slice(0, 8) + '…' };
      log.info('OpenAPI request', type, safe);
    }

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json;charset=UTF-8' },
      body: JSON.stringify(body),
    });
    const text = await resp.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`OpenAPI 非 JSON 响应 HTTP ${resp.status}: ${text.slice(0, 200)}`);
    }
    if (debug) log.info('OpenAPI response', type, { success: data.success, errorCode: data.errorCode, errorMsg: data.errorMsg });

    if (data.success === false || (data.errorCode && data.errorCode !== 0 && data.errorCode !== 1000000)) {
      const err = new Error(`OpenAPI ${type} 失败: code=${data.errorCode} msg=${data.errorMsg || ''}`);
      err.code = data.errorCode;
      err.payload = data;
      throw err;
    }
    return data;
  }

  /** 查看当前 token 权限列表 */
  async function tokenInfo(accessToken) {
    return call('bg.open.accesstoken.info.get', {}, { accessToken });
  }

  /**
   * 用授权 code 换 access_token
   * 文档：首次调用时 token 参数可等于 code
   */
  async function createAccessToken({ code, token } = {}) {
    const t = String(token || code || '').trim();
    if (!t) throw new Error('createAccessToken 需要 code（授权回调里的 code）');
    // 部分实现要求业务字段 code；公共 access_token 首次=code
    return call('bg.open.accesstoken.create', { code: t }, { accessToken: t });
  }

  return { call, tokenInfo, createAccessToken, baseUrl, appKey };
}

function mask(s) {
  const t = String(s || '');
  if (t.length <= 8) return '****';
  return t.slice(0, 4) + '…' + t.slice(-4);
}
