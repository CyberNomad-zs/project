/**
 * 飞书多维表格写入
 * - 写入前拉取表字段，按别名映射真实列名
 * - 只写表里存在的字段，避免 FieldNameNotFound
 */

import {
  BITABLE_FIELD_ALIASES,
  BITABLE_FIELDS,
  BITABLE_REQUIRED_KEYS,
  FEISHU
} from '../lib/constants.js';
import { getConfig } from '../lib/storage.js';
import { getTenantAccessToken } from './auth.js';

/** @type {{ key: string, appToken: string, tableId: string, map: Record<string, {name:string,type:number}>, names: string[], at: number } | null} */
let fieldCache = null;
const FIELD_CACHE_TTL = 5 * 60 * 1000;

/**
 * 业务记录 → 飞书 fields（使用固定首选名；实际写入走 resolve）
 * @param {object} row
 * @param {Record<string, {name:string,type:number}>} [resolvedMap]
 */
export function toBitableFields(row, resolvedMap) {
  const dateMs = row.date ? new Date(`${row.date}T00:00:00`).getTime() : Date.now();
  const scrapedMs = row.scrapedAt ? new Date(row.scrapedAt).getTime() : Date.now();

  const planLabel =
    row.planStatus === 'on'
      ? '投放中'
      : row.planStatus === 'off'
        ? '已关闭'
        : row.planStatus
          ? row.planStatus === 'unknown'
            ? '未知'
            : String(row.planStatus)
          : '';

  const logical = {
    date: dateMs,
    store: row.store || '',
    storeId: row.storeId || '',
    campaign: row.campaign || '',
    spend: Number(row.spend) || 0,
    orders: Number(row.orders) || 0,
    roi: Number(row.roi) || 0,
    revenue: Number(row.revenue) || 0,
    scrapedAt: scrapedMs,
    sourceUrl: row.sourceUrl || '',
    status: row.status || 'success',
    planStatus: planLabel
  };

  // 无映射时用默认中文名（兼容旧逻辑）
  if (!resolvedMap) {
    const out = {};
    for (const [k, v] of Object.entries(logical)) {
      const name = BITABLE_FIELDS[k];
      if (name) out[name] = v;
    }
    return out;
  }

  const out = {};
  for (const [k, v] of Object.entries(logical)) {
    const meta = resolvedMap[k];
    if (!meta?.name) continue;
    out[meta.name] = coerceValue(v, meta.type);
  }
  return out;
}

/**
 * @param {unknown} value
 * @param {number} type 飞书字段 type
 */
function coerceValue(value, type) {
  // 1 text, 3 single select, 4 multi, 15 url → string
  // 2 number → number
  // 5 datetime → ms
  if (type === 2) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }
  if (type === 5) {
    if (typeof value === 'number') return value;
    const t = new Date(value).getTime();
    return Number.isFinite(t) ? t : Date.now();
  }
  if (type === 3) {
    // 单选：传选项名字符串
    return String(value ?? '');
  }
  return value == null ? '' : String(value);
}

/**
 * 拉取表字段并解析逻辑字段 → 真实字段名
 */
export async function resolveFieldMap(appToken, tableId, force = false) {
  if (
    !force &&
    fieldCache &&
    fieldCache.appToken === appToken &&
    fieldCache.tableId === tableId &&
    Date.now() - fieldCache.at < FIELD_CACHE_TTL
  ) {
    return fieldCache;
  }

  const token = await getTenantAccessToken();
  const url = `${FEISHU.BITABLE_FIELDS(appToken, tableId)}?page_size=100`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const json = await res.json().catch(() => ({}));
  if (json.code !== 0) {
    throw new Error(
      `读取飞书表字段失败: code=${json.code} msg=${json.msg}。请确认 App Token / Table ID 正确，且应用已加入该多维表格。`
    );
  }

  const items = json.data?.items || [];
  const names = items.map((f) => f.field_name).filter(Boolean);
  const byName = {};
  for (const f of items) {
    if (f.field_name) byName[f.field_name] = f;
  }

  /** @type {Record<string, {name:string,type:number}>} */
  const map = {};
  for (const [key, aliases] of Object.entries(BITABLE_FIELD_ALIASES)) {
    for (const alias of aliases) {
      if (byName[alias]) {
        map[key] = { name: alias, type: byName[alias].type };
        break;
      }
    }
    // 大小写不敏感兜底
    if (!map[key]) {
      const lowerHit = names.find((n) =>
        aliases.some((a) => a.toLowerCase() === String(n).toLowerCase())
      );
      if (lowerHit && byName[lowerHit]) {
        map[key] = { name: lowerHit, type: byName[lowerHit].type };
      }
    }
  }

  const missingRequired = BITABLE_REQUIRED_KEYS.filter((k) => !map[k]);
  if (missingRequired.length) {
    const need = missingRequired
      .map((k) => `${k}(${(BITABLE_FIELD_ALIASES[k] || []).join('/')})`)
      .join('、');
    throw new Error(
      `飞书表缺少必要字段: ${need}。当前表字段: [${names.join(', ')}]。请补齐列名或改回与文档一致。`
    );
  }

  fieldCache = {
    key: `${appToken}/${tableId}`,
    appToken,
    tableId,
    map,
    names,
    at: Date.now()
  };
  return fieldCache;
}

/**
 * @param {object[]} rows 归一化后的业务行
 * @param {{dryRun?: boolean}} [opts]
 */
export async function writeRecords(rows, opts = {}) {
  const config = await getConfig();
  const { appToken, tableId } = config.feishu || {};
  if (!appToken || !tableId) {
    throw new Error('请先配置飞书多维表格 app_token 与 table_id');
  }

  if (!rows?.length) {
    return { written: 0, batches: 0, dryRun: !!opts.dryRun };
  }

  if (opts.dryRun || config.dryRun) {
    return {
      written: 0,
      batches: 0,
      dryRun: true,
      preview: rows.slice(0, 50)
    };
  }

  const resolved = await resolveFieldMap(appToken, tableId);
  const records = rows.map((r) => ({
    fields: toBitableFields(r, resolved.map)
  }));

  let written = 0;
  let batches = 0;

  for (let i = 0; i < records.length; i += FEISHU.BATCH_SIZE) {
    const chunk = records.slice(i, i + FEISHU.BATCH_SIZE);
    try {
      await batchCreateWithRetry(appToken, tableId, chunk);
    } catch (e) {
      // 字段可能刚改过，清缓存重解析一次再试
      if (/1254045|FieldNameNotFound/i.test(String(e.message || e))) {
        fieldCache = null;
        const again = await resolveFieldMap(appToken, tableId, true);
        const retryChunk = rows.slice(i, i + FEISHU.BATCH_SIZE).map((r) => ({
          fields: toBitableFields(r, again.map)
        }));
        try {
          await batchCreateWithRetry(appToken, tableId, retryChunk);
        } catch (e2) {
          throw enhanceFieldError(e2, again.names, again.map);
        }
      } else {
        throw enhanceFieldError(e, resolved.names, resolved.map);
      }
    }
    written += chunk.length;
    batches += 1;
  }

  return {
    written,
    batches,
    dryRun: false,
    fieldMap: Object.fromEntries(
      Object.entries(resolved.map).map(([k, v]) => [k, v.name])
    )
  };
}

function enhanceFieldError(err, tableNames, map) {
  const msg = String(err.message || err);
  if (!/1254045|FieldNameNotFound/i.test(msg)) return err;
  const used = map ? Object.values(map).map((m) => m.name) : [];
  const hint = new Error(
    `${msg}。写入使用字段: [${used.join(', ')}]，表内字段: [${(tableNames || []).join(', ')}]。请检查插件设置的 Table ID 是否指向当前表，并重新加载插件 v1.0.3+。`
  );
  hint.status = err.status;
  hint.body = err.body;
  return hint;
}

async function batchCreateWithRetry(appToken, tableId, records) {
  let lastErr;
  for (let attempt = 0; attempt < FEISHU.MAX_RETRIES; attempt++) {
    try {
      return await batchCreate(appToken, tableId, records, attempt > 0);
    } catch (e) {
      lastErr = e;
      const msg = String(e.message || e);
      // 字段不存在：不要无意义重试多次
      if (/1254045|FieldNameNotFound/i.test(msg)) throw e;
      if (/99991663|99991661|token/i.test(msg) || e.status === 401) {
        await getTenantAccessToken(true);
      }
      const delay = Math.min(1000 * 2 ** attempt, 8000);
      await sleep(delay);
    }
  }
  throw lastErr;
}

async function batchCreate(appToken, tableId, records, forceToken = false) {
  const token = await getTenantAccessToken(forceToken);
  const url = FEISHU.BITABLE_BATCH_CREATE(appToken, tableId);
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json; charset=utf-8'
    },
    body: JSON.stringify({ records })
  });

  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.code !== 0) {
    const err = new Error(
      `飞书写入失败: HTTP ${res.status} code=${json.code} msg=${json.msg || JSON.stringify(json)}`
    );
    err.status = res.status;
    err.body = json;
    throw err;
  }
  return json;
}

/**
 * 测试飞书连通性：拿 token + 读字段 + 读 1 条记录
 */
export async function testFeishuConnection() {
  const config = await getConfig();
  const { appToken, tableId } = config.feishu || {};
  if (!appToken || !tableId) {
    throw new Error('缺少 app_token 或 table_id');
  }
  const token = await getTenantAccessToken(true);
  const resolved = await resolveFieldMap(appToken, tableId, true);
  const url = `${FEISHU.BITABLE_LIST(appToken, tableId)}?page_size=1`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const json = await res.json();
  if (json.code !== 0) {
    throw new Error(`连通性检查失败: code=${json.code} msg=${json.msg}`);
  }
  return {
    ok: true,
    total: json.data?.total ?? 0,
    fields: resolved.names,
    mapped: Object.fromEntries(
      Object.entries(resolved.map).map(([k, v]) => [k, v.name])
    )
  };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
