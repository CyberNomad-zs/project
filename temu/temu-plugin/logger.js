// logger.js - Shared structured logging for Temu Monitor
// Works in: service worker, content script, popup
// Service worker → writes directly to chrome.storage (ring buffer, 500 entries)
// Content/popup   → writes to console + sends to background for persistent storage
(function () {
  'use strict';
  var MAX_ENTRIES = 500;
  var STORAGE_KEY = 'logs';
  var IS_SW = typeof window === 'undefined';

  // ---------------- timestamp ----------------
  function pad(n) { return String(n).padStart ? String(n).padStart(2, '0') : ('0' + n).slice(-2); }
  function fmtTs() {
    var d = new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
      ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  // ---------------- storage ring buffer (SW only) ----------------
  var writeChain = Promise.resolve();
  function writeEntry(entry) {
    writeChain = writeChain.then(function () {
      return _writeOne(entry);
    }).catch(function () { /* ignore write errors */ });
  }
  function _writeOne(entry) {
    return chrome.storage.local.get(STORAGE_KEY).then(function (r) {
      var logs = r[STORAGE_KEY] || [];
      if (logs.length >= MAX_ENTRIES) {
        logs = logs.slice(logs.length - MAX_ENTRIES + 1);
      }
      logs.push(entry);
      var obj = {};
      obj[STORAGE_KEY] = logs;
      return chrome.storage.local.set(obj);
    });
  }

  // ---------------- fire-and-forget to background (non-SW only) ----------------
  function sendToBg(entry) {
    try {
      chrome.runtime.sendMessage({ type: 'log', entry: entry }, function () {
        if (chrome.runtime.lastError) { /* bg terminated, entry lost -- acceptable */ }
      });
    } catch (e) { /* ignore */ }
  }

  // ---------------- public factory ----------------
  function createLogger(name) {
    function log(level, msg) {
      var entry = { ts: fmtTs(), level: level, msg: String(msg) };
      // Console output -- all contexts
      var prefix = '[' + entry.ts + '] [' + level + ']';
      try {
        if (level === 'ERROR') console.error(prefix, msg);
        else if (level === 'WARN') console.warn(prefix, msg);
        else console.log(prefix, msg);
      } catch (e) {}
      // Persistent storage
      if (IS_SW) {
        writeEntry(entry);
      } else {
        sendToBg(entry);
      }
    }
    return {
      info:  function (msg) { log('INFO',  msg); },
      warn:  function (msg) { log('WARN',  msg); },
      error: function (msg) { log('ERROR', msg); }
    };
  }

  // Export to global scope (no ES modules)
  if (IS_SW) {
    self.TemuLogger = { createLogger: createLogger, _writeEntry: writeEntry };
  } else {
    window.TemuLogger = { createLogger: createLogger };
  }
})();
