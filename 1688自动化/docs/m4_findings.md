# M4 发布层实测结论（2026-07-20）

> 对应交接文档 §10 风险点 #1（JS SDK 发布模式）与 #3（cookie 过期）。  
> 证据目录：`output/_m4/`（probe / seller_probe / sdk_deep / api_inventory / 截图）。

---

## 1. 发布模式结论（§10-1）

**判定：混合模式（浏览器承载 JS SDK 出风控参数 + Open API 后端调用）**

| 证据 | 含义 |
|---|---|
| 方案页「开发人员参考」明确要求前端注入 `alife-open-sdk` + `pcAlgorithmSdk` | 发布链路强制浏览器侧算法 SDK |
| `openSdk.load({sdkNameList:['pcAlgorithmSdk']})` 成功，实例方法为 `PcAlgorithmInit` / `PcAlgorithmExecute` | 风控在浏览器内 Init → Execute |
| 方案「API及消息列表」给出完整 Open API（`alibaba.new.product.add` / `getSchema` / photobank / video…） | 商品数据走开放平台 API，不是纯页面表单 POST |
| 方案同时提供「SDK下载」（后端加签） | accessToken 签名在服务端；算法参数在浏览器 |

**架构含义（M4 实现方向）**：

```
Playwright 页面
  ├─ 登录态 cookie（企业卖家账号）
  ├─ 注入 __1688_OPEN_SDK_CONFIG + alife-open-sdk
  ├─ load pcAlgorithmSdk
  ├─ PcAlgorithmInit(...) → PcAlgorithmExecute(业务入参) → 风控/签名字段
  └─ 把算法输出 + 商品 Schema JSON 一并交给后端
        └─ 用 config/1688_credentials.json 的 accessToken 调
           alibaba.new.product.add / edit 等 Open API
```

尚未完全闭合的点：`PcAlgorithmInit` 在当前页面返回 `getModelInfo error`（见 §4），需在**真实发布页上下文**或按官方增量编辑示例补齐 Init 双参后再验 `Execute` 输出字段名。

---

## 2. Cookie / 登录态（§10-3）

| 项 | 结果 |
|---|---|
| 旧 cookie（2026-07-06） | **已失效** → 落到 login.taobao.com |
| 半自动刷新 | `refresh_cookies.py` 有头扫码/账密 → 回写 `config/1688_cookies.json` ✅ |
| 复验 | `test_m4_login.py` / `check_login()` ✅ 有效 |
| 默认落地 | **买家工作台**（账号 `tbn62695333`） |
| 切卖家 | 点击文案 **「切为卖家」**（不是「切换为卖家」）→ 卖家工作台 ✅ |
| 卖家侧阻塞 | 弹窗 **「当前非企业账号，请注册或登录企业账号进入商家工作台」** ⚠️ |

**关键阻塞**：当前 cookie 对应**个人买家号**，不是目标店铺「常州易之来照明有限公司」的**企业卖家主账号**。  
M4 发商品 / 图片银行 / Schema 必须以**企业诚信通账号**登录后重导 cookie。

刷新流程：

```text
.venv-m4\Scripts\python.exe refresh_cookies.py
# 弹出浏览器 → 用企业卖家账号登录 → 自动保存 cookie
.venv-m4\Scripts\python.exe test_m4_login.py
```

---

## 3. 卖家工作台入口（实测可用）

| 功能 | URL / 路径 |
|---|---|
| 卖家工作台首页 | `https://work.1688.com/?_path_=sellerPro/sellberBaseNew_Index/seller2018IndexPage` |
| 发布商品 | `https://work.1688.com/?_path_=sellerPro/2017sellerbase_offer/orderPost` |
| 商品管理（新） | `https://work.1688.com/?_path_=sellerPro/2017sellerbase_offer/shasngpinguanlinew` |
| 方案页 | `https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686` |

从买家台切卖家：页面可见「切为卖家」按钮（`src/publish/session.py` 的 `ensure_seller_workbench` 会点它）。

---

## 4. JS SDK 实测

### 4.1 注入（与官方一致）

```html
<script>
window.__1688_OPEN_SDK_CONFIG = {
  appKey: '9901201',
  appName: '易之来商品自动发布'   // 必须与开放平台应用名完全一致
};
</script>
<script src="https://o.alicdn.com/fuwu-assets/alife-open-sdk/index.js"></script>
```

### 4.2 加载与实例

```js
const openSdk = window.__1688_OPEN_SDK;
const sdkLoadResult = await openSdk.load({ sdkNameList: ['pcAlgorithmSdk'] });
// sdkLoadResult[0] = { success: true, result: { PcAlgorithmInit, PcAlgorithmExecute } }
const algo = openSdk.getSdkInstance('pcAlgorithmSdk');
// algo.PcAlgorithmInit  length=2
// algo.PcAlgorithmExecute length=1
```

### 4.3 试探调用（当前页）

| 调用 | 返回 |
|---|---|
| `PcAlgorithmInit()` / `({})` / `({appKey})` | `{ isInit:false, reason: "getModelInfo error" }` |
| `PcAlgorithmExecute()` | `{ success:false, err: "input为空" }` |
| `PcAlgorithmExecute({})` / 带 api 名 | `{ success:false, err: "reInit Error" }`（未成功 Init） |

说明：Init 需要正确的**双参数 + 模型信息上下文**（官方示例写的是 `pcAlgorithmSdk.executeXXX(...)` 占位，真实方法名是 `PcAlgorithmInit`/`PcAlgorithmExecute`）。下一步应在发布页或对照「新版商品增量编辑接口参数示例」抓一次成功 Init。

代码封装：`src/publish/sdk.py`。

---

## 5. API 清单（方案页已抓）

完整索引：[`docs/m4_api_inventory.md`](m4_api_inventory.md)（70 条，含文档链接）。

发布主链路优先：

| 用途 | APIName |
|---|---|
| 类目搜索 | `alibaba.category.searchByKeyword` |
| 类目详情 | `alibaba.category.get` |
| 发布规则 Schema | `alibaba.new.product.getSchema` |
| 级联子 Schema | `alibaba.new.product.getSubSchema` |
| **新版发布** | `alibaba.new.product.add` |
| 新版编辑 | `alibaba.new.product.edit` |
| 图片银行上传 | `alibaba.photobank.photo.add` |
| 相册 | `alibaba.photobank.album.*` |
| 视频上传/绑定 | `alibaba.video.videocenter.upload` / `attach` / `get` |
| 运费模板 | `alibaba.logistics.myFreightTemplate.list.get` |
| 发货地址 | `alibaba.logistics.mySendGoodsAddress.list.get` |

---

## 6. 环境与入口脚本

| 项 | 说明 |
|---|---|
| Python | **M4 必须** `.venv-m4\Scripts\python.exe`（3.12 + Playwright；主环境 3.14 不跑浏览器） |
| 登录复验 | `test_m4_login.py` |
| Cookie 刷新 | `refresh_cookies.py` |
| 综合探针 | `test_m4_probe.py` |
| 卖家侧探针 | `test_m4_seller_probe.py` |
| SDK 深挖 | `test_m4_sdk_deep.py` |
| API 清单抓取 | `test_m4_scrape_apis.py` |

---

## 7. 下一步（M4 继续）

1. **用企业卖家账号重登** → `refresh_cookies.py`，确认卖家工作台无「非企业账号」弹窗，店铺名为易之来。
2. **Init 闭合**：在发布商品页或按官方示例找到 `PcAlgorithmInit` 双参含义，拿到 `isInit:true`。
3. **Open API 客户端**：用永久 `accessToken` 封装 `alibaba.new.product.getSchema` 只读探测（不发商品）。
4. **端到端最小发布**：图片银行 1 张测试图 → Schema 填最小必填 → Execute 风控 → `alibaba.new.product.add`（测试商品，可立刻下架）。

---

## 8. 文件索引

```
src/publish/
  session.py     cookie 加载/刷新/登录检测/切卖家
  sdk.py         alife-open-sdk + pcAlgorithmSdk 封装
  probe.py       发布页/网络探针
  __init__.py
docs/
  m4_findings.md          本文
  m4_api_inventory.md     API 清单
output/_m4/
  probe_report.json
  seller_probe_report.json
  sdk_deep_report.json
  api_inventory.json
  *.png                   截图
refresh_cookies.py / test_m4_*.py
```
