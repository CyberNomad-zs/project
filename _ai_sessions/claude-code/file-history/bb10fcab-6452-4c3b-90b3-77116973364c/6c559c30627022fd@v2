# 给 temu-plugin 添加日志功能

## Context

temu-plugin（Chrome 扩展）目前没有任何结构化日志系统——只有 `content.js` 里 3 处 `console.log`，`background.js`/`popup.js`/`inject.js` 完全没有日志。需要加上带持久化存储的结构化日志，支持在弹窗中查看和导出。

## 涉及文件

| 文件 | 操作 |
|------|------|
| `logger.js` | **新建** — 共享日志模块 |
| `manifest.json` | 修改 content_scripts 加载顺序 |
| `background.js` | import logger + 处理日志消息 + ~30 处日志调用 + 重命名冲突变量 |
| `content.js` | 替换 LOG 辅助函数 + ~15 处日志调用 |
| `popup.html` | 加载 logger.js + 日志查看器 UI |
| `popup.js` | 日志读取/渲染/导出逻辑 |
| `inject.js` | **不改**（MAIN world 无 chrome.* API） |
| `options.js/html` | **不改** |

## 设计要点

### logger.js — 共享日志模块

- 纯 JS 脚本（无 ES module），通过 `window.TemuLogger` / `self.TemuLogger` 暴露
- 上下文检测：`typeof window === 'undefined'` 判断是否为 Service Worker
- **SW 上下文**：直接写 `chrome.storage.local`（key: `logs`），用 Promise 链串行化防竞态
- **非 SW 上下文**（content/popup）：`console.log/warn/error` + `chrome.runtime.sendMessage({type:'log', entry})` 发给 SW 持久化
- 环形缓冲区：最多 500 条，超出裁旧留新
- 日志格式：`{ ts: "2026-07-20 14:30:45", level: "INFO", msg: "..." }`
- 控制台输出：`[2026-07-20 14:30:45] [INFO] message`
- API：`TemuLogger.createLogger(name)` → `{ info(msg), warn(msg), error(msg) }`
- SW 额外暴露 `_writeEntry(entry)` 给消息处理器直接写存储（避免重复 console 输出）

### 加载方式

- **background.js**：顶部 `importScripts('logger.js')`（MV3 SW 支持）
- **manifest.json**：content_scripts 的 js 数组改为 `["logger.js", "content.js"]`
- **popup.html**：在 `popup.js` 之前加 `<script src="logger.js"></script>`

### background.js 改动

1. 顶部加 `importScripts('logger.js'); var log = TemuLogger.createLogger('bg');`
2. 消息监听器新增 `type === 'log'` 分支（第一个判断），调用 `TemuLogger._writeEntry(msg.entry)`
3. `cycleStores` 函数内的局部变量 `const log = []` 重命名为 `const cycleLog = []`，所有引用同步更新（避免与全局 `log` 冲突）
4. 消息监听器 IIFE 外层包 try/catch
5. 约 30 处关键操作加日志：alarm 设置/触发、API 解析结果、diffAndAlert 触发/完成、Feishu 发送成功/失败、cycleStores 生命周期、pollNow、各类手动操作等

### content.js 改动

1. 删除旧的 `const LOG = (...a) => { ... }`，替换为 `var LOG = TemuLogger.createLogger('content');`
2. 旧有的 3 处 LOG 调用改用新 API
3. 新增约 15 处日志：inject.js 注入、DOM 操作、切店、扫描、错误等
4. 流量轮询的日志只在 dedupe gate（`key !== lastKey`）内触发，避免 2s 刷屏

### popup 改动

- **popup.html**：底部增加日志查看器区域（默认折叠），含切换按钮 + 导出按钮 + 日志计数 + 滚动列表
- **popup.js**：
  - 顶部 `var LOG = TemuLogger.createLogger('popup');`
  - `fetchAndRenderLogs()` — 从 storage 读 logs，最新在上，按级别着色
  - `toggleLogs()` — 展开/折叠，展开时 3s 自动刷新
  - `exportLogs()` — 序列化为文本，Blob 下载
  - 复用现有 `esc()` 函数做 HTML 转义

## 实现顺序

1. 创建 `logger.js`
2. 修改 `manifest.json`（content_scripts 加 logger.js）
3. 修改 `background.js`（import + handler + 重命名 + 日志调用）
4. 修改 `content.js`（替换 LOG + 日志调用）
5. 修改 `popup.html`（UI + 脚本标签）
6. 修改 `popup.js`（逻辑）

## 验证

1. 重新加载扩展后，打开 Temu 商品列表页
2. F12 打开 DevTools → Console，确认能看到 `[timestamp] [INFO]` 格式的日志
3. 在 `chrome://serviceworker-internals/` 查看 SW 控制台，确认 SW 日志正常
4. 点击扩展图标打开弹窗 → 点击「📋 日志」→ 确认能看到持久化的日志列表
5. 点击「导出」→ 确认下载的 .log 文件内容正确
6. 手动触发「测试飞书」→ 确认日志中出现飞书发送结果
