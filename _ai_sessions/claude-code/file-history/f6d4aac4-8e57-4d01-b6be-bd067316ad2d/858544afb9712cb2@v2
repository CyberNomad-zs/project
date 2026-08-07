import { MSG } from '../lib/constants.js';

const $ = (id) => document.getElementById(id);

init();

async function init() {
  const { config } = await send({ type: MSG.GET_CONFIG });
  fillForm(config || {});

  $('btnSave').addEventListener('click', onSave);
  $('btnTest').addEventListener('click', onTest);
  $('btnClearLogs').addEventListener('click', onClearLogs);
}

function fillForm(c) {
  $('appId').value = c.feishu?.appId || '';
  $('appSecret').value = c.feishu?.appSecret || '';
  $('appToken').value = c.feishu?.appToken || '';
  $('tableId').value = c.feishu?.tableId || '';
  $('defaultStoreName').value = c.defaultStoreName || '';
  $('writeMode').value = c.writeMode || 'append';
  $('storeMappings').value = (c.storeMappings || [])
    .map((m) => `${m.alias} => ${m.name}`)
    .join('\n');
  $('scheduleEnabled').checked = !!c.schedule?.enabled;
  $('scheduleHour').value = c.schedule?.hour ?? 7;
  $('scheduleMinute').value = c.schedule?.minute ?? 30;
  $('dateMode').value = c.dateMode || 'yesterday';
  $('customDate').value = c.customDate || '';
  $('dryRun').checked = c.dryRun !== false;
}

function readForm() {
  const mappings = $('storeMappings')
    .value.split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(/=>|->|=/).map((s) => s.trim());
      if (parts.length >= 2) return { alias: parts[0], name: parts[1] };
      return { alias: parts[0], name: parts[0] };
    });

  return {
    feishu: {
      appId: $('appId').value.trim(),
      appSecret: $('appSecret').value.trim(),
      appToken: $('appToken').value.trim(),
      tableId: $('tableId').value.trim()
    },
    defaultStoreName: $('defaultStoreName').value.trim(),
    writeMode: $('writeMode').value,
    storeMappings: mappings,
    schedule: {
      enabled: $('scheduleEnabled').checked,
      hour: Number($('scheduleHour').value) || 7,
      minute: Number($('scheduleMinute').value) || 0
    },
    dateMode: $('dateMode').value,
    customDate: $('customDate').value,
    dryRun: $('dryRun').checked
  };
}

async function onSave() {
  const config = readForm();
  const r = await send({ type: MSG.SAVE_CONFIG, config });
  if (r.ok) toast('已保存');
  else toast(r.error || '保存失败');
}

async function onTest() {
  // 先保存再测
  await onSave();
  const r = await send({ type: MSG.TEST_FEISHU });
  if (r.ok) toast(`连接成功，表内约 ${r.total ?? 0} 条记录`);
  else toast(r.error || '连接失败');
}

async function onClearLogs() {
  await send({ type: MSG.CLEAR_LOGS });
  toast('日志已清空');
}

function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}

function send(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(response || {});
    });
  });
}
