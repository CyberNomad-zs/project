# Temu OpenAPI：下架 + 限流/低流量监测

基于 Partner 开放平台商品列表接口，**不依赖浏览器插件**，可服务器定时跑。

## 能力

| 监测项 | 接口/字段 | 告警条件 |
|--------|-----------|----------|
| 下架点名 | `bg.local.goods.list.query` / `temu.local.goods.list.retrieve` 在售集合 diff | 上轮在售、本轮不在 |
| 低流量 | `goodsSearchTags=1` 或 `lowTrafficTag=1` | 新进低流量集合 |
| 限流 | `goodsSearchTags=4` 或 `restrictedTrafficTag=1` | 新进限流集合 |

> 「商品流量近期有下降」后台行徽标 **开放平台无对应字段**，仍用 Chrome 插件。

## 前置条件

1. Partner 已有 **自主开发应用**（如「圣光ERP」），拿到 `appKey` / `appSecret`
2. **卖家中心授权**该应用（每个 mall 通常一份 `access_token`）
3. token 权限需包含商品列表，例如：
   - `bg.local.goods.list.query`
   - 或 `temu.local.goods.list.retrieve`
4. **半托管 agentseller 店**是否可用 Local 商品包 → 以 `probe` 实测为准

### 区域网关

| region | baseUrl |
|--------|---------|
| global | `https://openapi-b-global.temu.com` |
| us | `https://openapi-b-us.temu.com` |
| eu | `https://openapi-b-eu.temu.com` |

## 配置

```bash
cd temu-monitor
node src/openapi/cli.js init
# 编辑 openapi.config.json（已 gitignore）
```

必填：`appKey`、`appSecret`、各店 `accessToken`。  
飞书 webhook 可写在本文件，或沿用主 `config.json` 的 `feishuWebhooks`。

**安全：** 截图/聊天里出现过的 `appSecret` 请在 Partner **轮换**后再写入配置。

## 授权换 token

1. 在 Partner 应用配置 **Redirect URL**
2. 卖家打开授权页完成授权，回调 URL 带 `code=...`
3. 换取 token：

```bash
node src/openapi/cli.js token <code>
```

把输出的 `accessToken`、`mallId` 写入对应店铺。  
用 `probe` 看 `apiScopeList` 是否含商品列表接口。

## 命令

```bash
# 探测权限 + 拉 5 条商品样本
node src/openapi/cli.js probe
node src/openapi/cli.js probe HomeCove

# 干跑（不发飞书、不写快照）
node src/openapi/cli.js dry

# 正式一轮（首轮只建基准不告警）
node src/openapi/cli.js once

# 常驻（默认 15 分钟）
node src/openapi/cli.js start
# 或: npm run openapi:once / openapi:start
```

## 状态文件

`data/openapi-state.json`：按店保存 `activeMap` / `lowTrafficMap` / `restrictedMap`。  
删除该文件可重置基准（下一轮重新建基、不告警）。

## 防误报

- **首轮**不告警
- 在售数相对基准骤降超过 50%（且基准≥10）→ 跳过下架判定，避免接口异常误报
- 空店铺 / 拉失败不覆盖在售基准

## 与插件关系

| | OpenAPI | Chrome 插件 |
|--|---------|-------------|
| 下架全量 | ✅ 主路径 | 轮巡 DOM 兜底 |
| 低流量/限流标签 | ✅ 官方 tag | chip「待关注」 |
| 流量近期下降 | ❌ | ✅ 行徽标 |
| 需开浏览器 | ❌ | ✅ |

可两套并行；飞书可能对同一下架各报一次，确认稳定后可关掉插件侧下架告警。

## 常见失败

| 现象 | 处理 |
|------|------|
| `access_token don't have this api access` | 重新授权并勾选商品权限 |
| 两种 list 都失败 | 半托管可能无 Local 商品 API → 继续插件 |
| 样本无 `lowTrafficTag` | 用 `goodsSearchTags` 筛选；仍无则限流只能插件 |
| 编辑链接点开不对 | `goodsId` 与后台 `productId` 不一致，改 `editBaseUrl` 或映射字段 |
| 签名错误 | 检查 appSecret 是否轮换后未更新；`debug: true` 看请求 |

## 代码位置

```
temu-monitor/src/openapi/
  client.js    签名与 HTTP
  goods.js     列表分页与标签
  diff.js      快照 diff 与飞书文案
  monitor.js   一轮编排
  config.js    配置加载
  cli.js       命令行
```
