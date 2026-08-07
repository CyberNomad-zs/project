# 清泉跨境 · Web 任务台（Phase0 演示）

## 启动

先保证 API 在 `http://127.0.0.1:8000` 运行，并已 seed。

```powershell
cd "E:\project\清泉跨境系统（企业级）\web"
npm install
npm run dev
```

浏览器打开终端提示的地址（默认 http://127.0.0.1:5173）。

默认账号：`admin` / `admin123`

## 能力

- 登录 / 退出
- 任务列表筛选、新建、更新进度、闭环（演示去重键规则）
- 店铺主数据只读列表
- 触发飞书同步入队
- API 健康状态指示

Vite 已把 `/api` 与 `/health` 代理到 8000 端口。
