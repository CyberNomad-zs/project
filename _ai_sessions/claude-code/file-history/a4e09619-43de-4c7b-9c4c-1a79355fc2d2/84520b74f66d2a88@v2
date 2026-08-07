/**
 * OpenAPI 监测 CLI
 *
 *   node src/openapi/cli.js init          # 生成 openapi.config.json 模板
 *   node src/openapi/cli.js token <code>  # 用授权 code 换 access_token
 *   node src/openapi/cli.js probe [店名]  # 探测权限 + 拉 1 页
 *   node src/openapi/cli.js once          # 跑一轮
 *   node src/openapi/cli.js start         # 常驻轮询
 *   node src/openapi/cli.js dry           # 一轮但不发飞书、不写状态
 */
import { writeFileSync, existsSync, copyFileSync } from 'node:fs';
import { loadOpenApiConfig, openApiConfigReady, exampleConfigPath, configPath, hasLocalConfig } from './config.js';
import { createOpenApiClient } from './client.js';
import { runOpenApiOnce, probeStore } from './monitor.js';
import { log } from '../logger.js';

const cmd = process.argv[2] || 'once';

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function printHelp() {
  console.log(`
Temu OpenAPI 下架 / 限流监测

命令:
  init              从 example 生成 openapi.config.json（已存在则跳过）
  token <code>      授权 code 换 access_token（打印结果，需自行写入配置）
  probe [店名]      探测 token 权限 + 拉一页商品
  once              监测一轮（diff + 飞书 + 写快照）
  dry               监测一轮但不发飞书、不写快照
  start             按 intervalMinutes 常驻
  help              帮助

配置文件: temu-monitor/openapi.config.json（勿提交密钥）
模板:     temu-monitor/openapi.config.example.json
`);
}

async function cmdInit() {
  const dest = configPath();
  if (existsSync(dest)) {
    log.warn('已存在 openapi.config.json，未覆盖。');
    return;
  }
  const ex = exampleConfigPath();
  if (existsSync(ex)) {
    copyFileSync(ex, dest);
  } else {
    writeFileSync(dest, JSON.stringify({
      appKey: '',
      appSecret: '',
      region: 'global',
      stores: [{ name: 'HomeCove', accessToken: '', enabled: true }],
    }, null, 2));
  }
  log.info('已生成', dest);
  log.info('请填写 appKey/appSecret，并完成卖家授权后写入各店 accessToken。');
}

async function cmdToken(code) {
  const cfg = loadOpenApiConfig();
  if (!cfg.appKey || !cfg.appSecret) {
    log.error('请先在 openapi.config.json 填写 appKey / appSecret');
    process.exitCode = 1;
    return;
  }
  if (!code) {
    log.error('用法: node src/openapi/cli.js token <授权code>');
    process.exitCode = 1;
    return;
  }
  const client = createOpenApiClient({
    appKey: cfg.appKey,
    appSecret: cfg.appSecret,
    baseUrl: cfg.baseUrl,
    debug: true,
  });
  try {
    const data = await client.createAccessToken({ code });
    console.log(JSON.stringify(data, null, 2));
    const r = data.result || {};
    log.info('请将 accessToken / mallId 写入 openapi.config.json 对应店铺：');
    log.info('  accessToken =', r.accessToken || r.access_token);
    log.info('  mallId      =', r.mallId || r.mall_id);
    const scopes = r.apiScopeList || r.api_scope_list || [];
    const need = ['bg.local.goods.list.query', 'temu.local.goods.list.retrieve'];
    const hit = need.filter((x) => scopes.includes(x));
    log.info('商品列表相关权限命中：', hit.length ? hit.join(', ') : '无（可能无法做下架/限流监测）');
  } catch (e) {
    log.error('换 token 失败：', e.message);
    if (e.payload) console.error(JSON.stringify(e.payload, null, 2));
    process.exitCode = 1;
  }
}

async function cmdProbe(storeName) {
  const cfg = loadOpenApiConfig();
  const ready = openApiConfigReady(cfg);
  if (!ready.ok) {
    log.error(ready.reason);
    process.exitCode = 1;
    return;
  }
  try {
    const r = await probeStore(cfg, storeName);
    console.log(JSON.stringify(r, null, 2));
    if (r.listError && r.retrieveError) {
      log.error('两种列表接口均失败。常见原因：token 无 Local 商品权限，或店铺业态不匹配。');
      process.exitCode = 1;
    } else {
      log.info('探测成功。若 sample 里有 lowTrafficTag/restrictedTrafficTag，限流监测可用。');
    }
  } catch (e) {
    log.error(e.message);
    process.exitCode = 1;
  }
}

async function cmdOnce(dry) {
  const cfg = loadOpenApiConfig();
  const ready = openApiConfigReady(cfg);
  if (!ready.ok) {
    log.error(ready.reason);
    log.info('先运行: node src/openapi/cli.js init 并完成授权');
    process.exitCode = 1;
    return;
  }
  const summary = await runOpenApiOnce(cfg, { dryRun: !!dry });
  console.log(JSON.stringify(summary, null, 2));
}

async function cmdStart() {
  const cfg = loadOpenApiConfig();
  const ready = openApiConfigReady(cfg);
  if (!ready.ok) {
    log.error(ready.reason);
    process.exitCode = 1;
    return;
  }
  log.info(`OpenAPI 常驻监测启动，间隔 ${cfg.intervalMinutes} 分钟。Ctrl+C 退出。`);
  for (;;) {
    const t0 = Date.now();
    try {
      await runOpenApiOnce(cfg);
    } catch (e) {
      log.error('本轮失败：', e.message);
    }
    const waitMs = Math.max(60_000, cfg.intervalMinutes * 60_000 - (Date.now() - t0));
    log.info(`${Math.round(waitMs / 1000)} 秒后下一轮`);
    await sleep(waitMs);
  }
}

async function main() {
  switch (cmd) {
    case 'help':
    case '-h':
    case '--help':
      printHelp();
      break;
    case 'init':
      await cmdInit();
      break;
    case 'token':
      await cmdToken(process.argv[3]);
      break;
    case 'probe':
      await cmdProbe(process.argv[3]);
      break;
    case 'once':
      await cmdOnce(false);
      break;
    case 'dry':
      await cmdOnce(true);
      break;
    case 'start':
      await cmdStart();
      break;
    default:
      log.error('未知命令：', cmd);
      printHelp();
      process.exitCode = 1;
  }
}

main().catch((e) => {
  log.error(e);
  process.exitCode = 1;
});
