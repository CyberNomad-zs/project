// 飞书企业自建应用：tenant_access_token + 多维表格 upsert + 任务创建。
// 由 background importScripts 加载。凭证来自 config（本机 storage），不上传自建服务器。
// 未配置 app_id/secret 或 bitable 时全部 no-op，不阻断 webhook 卡片告警。

var FeishuApp = (function () {
  var log = (typeof TemuLogger !== 'undefined')
    ? TemuLogger.createLogger('feishuApp')
    : { info: function () {}, warn: function () {}, error: function () {} };

  var tokenCache = { token: '', expireAt: 0 };

  function cfgReady(cfg) {
    return !!(cfg && cfg.feishuAppId && cfg.feishuAppSecret
      && cfg.bitableAppToken && cfg.bitableTableId);
  }

  async function getTenantToken(cfg) {
    const now = Date.now();
    if (tokenCache.token && tokenCache.expireAt > now + 60 * 1000) return tokenCache.token;
    const resp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_id: cfg.feishuAppId, app_secret: cfg.feishuAppSecret }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!data || data.code !== 0 || !data.tenant_access_token) {
      throw new Error('token failed: ' + JSON.stringify(data));
    }
    tokenCache.token = data.tenant_access_token;
    // expire 通常 7200s；提前 5 分钟刷新
    const ttl = (typeof data.expire === 'number' ? data.expire : 7200) - 300;
    tokenCache.expireAt = now + Math.max(60, ttl) * 1000;
    return tokenCache.token;
  }

  async function api(cfg, method, path, body) {
    const token = await getTenantToken(cfg);
    const opts = {
      method: method,
      headers: {
        Authorization: 'Bearer ' + token,
        'Content-Type': 'application/json; charset=utf-8',
      },
    };
    if (body != null) opts.body = JSON.stringify(body);
    const resp = await fetch('https://open.feishu.cn/open-apis' + path, opts);
    const data = await resp.json().catch(() => ({}));
    if (!data || data.code !== 0) {
      throw new Error((data && data.msg) || ('HTTP ' + resp.status) + ' path=' + path);
    }
    return data;
  }

  // 字段名 → 多维表列名（可被 config.bitableFieldMap 覆盖）
  function fieldMap(cfg) {
    const def = {
      store: '店铺',
      name: '商品名',
      productId: 'productId',
      skc: 'SKC',
      skuCodes: 'SKU货号',
      kinds: '限流类型',
      severity: '严重等级',
      hotSale: '热销款',
      link: '编辑链接',
      pushedAt: '最近推送时间',
      reason: '判定原因',
    };
    return Object.assign({}, def, (cfg && cfg.bitableFieldMap) || {});
  }

  function recordFields(cfg, item, store) {
    const F = fieldMap(cfg);
    const severityLabel = item.severity === 'severe' ? '严重' : '一般';
    const kinds = Array.isArray(item.kinds) ? item.kinds : [];
    let kindsLabel = '待关注';
    if (kinds.indexOf('watch') >= 0 && kinds.indexOf('decline') >= 0) kindsLabel = '两者';
    else if (kinds.indexOf('decline') >= 0) kindsLabel = '近期下降';
    else if (kinds.indexOf('watch') >= 0) kindsLabel = '待关注';
    const fields = {};
    fields[F.store] = store || '';
    fields[F.name] = String(item.name || '').slice(0, 200);
    fields[F.productId] = String(item.productId || '');
    fields[F.skc] = String(item.skc || '');
    fields[F.skuCodes] = (item.skuCodes || []).join(', ');
    fields[F.kinds] = kindsLabel;
    fields[F.severity] = severityLabel;
    fields[F.hotSale] = !!item.hotSale;
    fields[F.link] = {
      link: 'https://agentseller.temu.com/goods/edit?from=productList&productId=' + item.productId,
      text: '编辑',
    };
    fields[F.pushedAt] = Date.now();
    if (item.reason) fields[F.reason] = String(item.reason);
    return fields;
  }

  // 按 店铺 + productId 查重；有则 update，无则 create
  async function upsertRecords(cfg, store, items) {
    if (!cfgReady(cfg) || !items || !items.length) {
      return { ok: false, skipped: true, msg: 'bitable not configured or empty' };
    }
    const F = fieldMap(cfg);
    const app = encodeURIComponent(cfg.bitableAppToken);
    const table = encodeURIComponent(cfg.bitableTableId);
    let created = 0;
    let updated = 0;
    const errors = [];
    // 严重优先
    const sorted = items.slice().sort((a, b) => {
      if (a.severity === b.severity) return 0;
      return a.severity === 'severe' ? -1 : 1;
    });
    for (const it of sorted) {
      if (!it || !it.productId) continue;
      try {
        const filter = 'AND(CurrentValue.[' + F.store + ']="' + String(store).replace(/"/g, '\\"')
          + '",CurrentValue.[' + F.productId + ']="' + String(it.productId).replace(/"/g, '\\"') + '")';
        const listed = await api(cfg, 'POST',
          '/bitable/v1/apps/' + app + '/tables/' + table + '/records/search',
          { filter: filter, page_size: 5 });
        const existing = listed && listed.data && Array.isArray(listed.data.items) ? listed.data.items : [];
        const fields = recordFields(cfg, it, store);
        if (existing.length && existing[0].record_id) {
          await api(cfg, 'PUT',
            '/bitable/v1/apps/' + app + '/tables/' + table + '/records/' + existing[0].record_id,
            { fields: fields });
          updated += 1;
        } else {
          await api(cfg, 'POST',
            '/bitable/v1/apps/' + app + '/tables/' + table + '/records',
            { fields: fields });
          created += 1;
        }
      } catch (e) {
        errors.push(String((e && e.message) || e));
        log.warn('bitable upsert fail productId=' + it.productId + ' err=' + ((e && e.message) || e));
      }
    }
    log.info('bitable upsert store=' + store + ' created=' + created + ' updated=' + updated
      + ' errors=' + errors.length);
    return { ok: errors.length === 0, created: created, updated: updated, errors: errors };
  }

  // 仅严重限流建任务，避免一般刷屏
  async function createSevereTasks(cfg, store, items) {
    if (!cfg || cfg.feishuTaskEnabled === false) {
      return { ok: false, skipped: true, msg: 'task disabled' };
    }
    if (!cfg.feishuAppId || !cfg.feishuAppSecret) {
      return { ok: false, skipped: true, msg: 'no app creds' };
    }
    const severe = (items || []).filter((it) => it && it.severity === 'severe' && it.productId);
    if (!severe.length) return { ok: true, created: 0 };
    let created = 0;
    const errors = [];
    for (const it of severe) {
      try {
        const link = 'https://agentseller.temu.com/goods/edit?from=productList&productId=' + it.productId;
        const summary = '[严重限流] ' + (store || '') + ' · ' + String(it.name || it.productId).slice(0, 40);
        const desc = [
          '店铺：' + (store || ''),
          '等级：严重' + (it.reason ? '（' + it.reason + '）' : ''),
          'SKC：' + (it.skc || '-'),
          '货号：' + ((it.skuCodes || []).join(', ') || '-'),
          '编辑：' + link,
        ].join('\n');
        // 任务 v2：最小创建（无成员时仍可建，出现在应用侧）
        const body = {
          summary: summary,
          description: desc,
          extra: link,
        };
        // 若配置了任务清单，挂上去
        if (cfg.feishuTasklistGuid) {
          body.tasklists = [{ tasklist_guid: cfg.feishuTasklistGuid }];
        }
        await api(cfg, 'POST', '/task/v2/tasks', { task: body, client_token: 'temu-' + store + '-' + it.productId + '-' + Date.now() });
        created += 1;
      } catch (e) {
        errors.push(String((e && e.message) || e));
        log.warn('task create fail productId=' + it.productId + ' err=' + ((e && e.message) || e));
      }
    }
    log.info('tasks created=' + created + ' errors=' + errors.length);
    return { ok: errors.length === 0, created: created, errors: errors };
  }

  // 推送后同步：表 + 严重任务。失败只 log，不抛。
  async function syncAfterAlert(cfg, store, items) {
    if (!items || !items.length) return { bitable: null, tasks: null };
    let bitable = null;
    let tasks = null;
    try {
      bitable = await upsertRecords(cfg, store, items);
    } catch (e) {
      log.error('sync bitable: ' + ((e && e.message) || e));
      bitable = { ok: false, msg: String((e && e.message) || e) };
    }
    try {
      tasks = await createSevereTasks(cfg, store, items.filter((i) => i.severity === 'severe'));
    } catch (e) {
      log.error('sync tasks: ' + ((e && e.message) || e));
      tasks = { ok: false, msg: String((e && e.message) || e) };
    }
    return { bitable: bitable, tasks: tasks };
  }

  return {
    cfgReady: cfgReady,
    upsertRecords: upsertRecords,
    createSevereTasks: createSevereTasks,
    syncAfterAlert: syncAfterAlert,
  };
})();
