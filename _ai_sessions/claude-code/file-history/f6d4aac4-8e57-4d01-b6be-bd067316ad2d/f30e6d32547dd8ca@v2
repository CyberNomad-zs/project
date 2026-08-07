import { appendLog } from './storage.js';

/**
 * 统一日志：写 storage + console
 * @param {'info'|'warn'|'error'|'success'} level
 * @param {string} message
 * @param {object} [meta]
 */
export async function log(level, message, meta = {}) {
  const entry = { level, message, ...meta };
  console[level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log'](
    `[TK-Ad] ${message}`,
    meta
  );
  try {
    await appendLog(entry);
  } catch (e) {
    console.error('[TK-Ad] appendLog failed', e);
  }
  return entry;
}
