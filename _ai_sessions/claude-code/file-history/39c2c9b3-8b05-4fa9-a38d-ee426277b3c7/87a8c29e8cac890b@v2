import crypto from 'node:crypto';
import { log } from './logger.js';

/**
 * 飞书自定义机器人告警。
 * 支持可选签名校验（config.feishuSecret）。
 */

function sign(secret, timestamp) {
  const stringToSign = `${timestamp}\n${secret}`;
  const hmac = crypto.createHmac('sha256', stringToSign);
  hmac.update('');
  return hmac.digest('base64');
}

/**
 * 发送一条飞书卡片消息。
 * @param {object} cfg
 * @param {{title:string, template?:string, lines:string[]}} msg
 */
export async function sendFeishu(cfg, { title, template = 'red', lines }) {
  const hooks = cfg.feishuWebhooks && cfg.feishuWebhooks.length
    ? cfg.feishuWebhooks
    : (cfg.feishuWebhook ? [cfg.feishuWebhook] : []);
  if (!hooks.length) {
    log.warn('未配置 feishuWebhooks，跳过告警。内容：', title, lines);
    return false;
  }
  const timestamp = Math.floor(Date.now() / 1000);
  const body = {
    msg_type: 'interactive',
    card: {
      config: { wide_screen_mode: true },
      header: {
        title: { tag: 'plain_text', content: title },
        template,
      },
      elements: [
        {
          tag: 'div',
          text: { tag: 'lark_md', content: lines.join('\n') },
        },
      ],
    },
  };
  if (cfg.feishuSecret) {
    body.timestamp = String(timestamp);
    body.sign = sign(cfg.feishuSecret, timestamp);
  }

  // 依次发往每个群 webhook；任一成功即视为发送成功，互不影响
  let anyOk = false;
  for (const url of hooks) {
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await resp.json().catch(() => ({}));
      if (data.code && data.code !== 0) {
        log.error(`飞书返回错误(...${url.slice(-8)})：`, data);
        continue;
      }
      log.info(`飞书告警已发送(...${url.slice(-8)})：`, title);
      anyOk = true;
    } catch (e) {
      log.error(`飞书发送失败(...${url.slice(-8)})：`, e.message);
    }
  }
  return anyOk;
}
