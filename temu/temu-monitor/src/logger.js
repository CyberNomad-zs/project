import { appendFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { ROOT } from './config.js';

// 双写：data/monitor.log（历史路径，兼容旧脚本）+ logs/monitor-YYYYMMDD.log（按日、好找）
const DATA_DIR = resolve(ROOT, 'data');
const LOGS_DIR = resolve(ROOT, 'logs');
try { mkdirSync(DATA_DIR, { recursive: true }); } catch {}
try { mkdirSync(LOGS_DIR, { recursive: true }); } catch {}

const LEGACY_LOG = resolve(DATA_DIR, 'monitor.log');

function dayStamp() {
  // 本地日历日（不用 UTC），避免按日文件跨日错位
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function dailyLogPath() {
  return resolve(LOGS_DIR, `monitor-${dayStamp()}.log`);
}

let announced = false;

function ts() {
  // ISO 存盘统一；控制台也用同一格式，排障时好对齐
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function write(level, args) {
  const line = `[${ts()}] [${level}] ${args.map(fmt).join(' ')}`;
  if (level === 'ERROR') console.error(line);
  else console.log(line);
  // 文件写失败不能再递归 log.error，吞掉即可
  try { appendFileSync(LEGACY_LOG, line + '\n'); } catch {}
  try { appendFileSync(dailyLogPath(), line + '\n'); } catch {}
}

function fmt(a) {
  if (typeof a === 'string') return a;
  if (a instanceof Error) return a.stack || a.message || String(a);
  try { return JSON.stringify(a); } catch { return String(a); }
}

export const log = {
  info: (...a) => write('INFO', a),
  warn: (...a) => write('WARN', a),
  error: (...a) => write('ERROR', a),
  /**
   * 进程启动时喊一声落盘路径，避免同事以为「没写日志」。
   * 幂等：同进程只打一次。
   */
  announcePaths() {
    if (announced) return;
    announced = true;
    write('INFO', [
      `日志落盘：${dailyLogPath()} （同时写入 ${LEGACY_LOG}）`,
    ]);
  },
};
