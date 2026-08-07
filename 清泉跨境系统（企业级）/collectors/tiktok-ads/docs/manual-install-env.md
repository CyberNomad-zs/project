# 手动安装环境（脚本失败时用）

多店抓取依赖：**Node.js + ziniao-cli + 紫鸟桌面客户端**。  
优先用项目根目录 **`安装环境.bat`** / `scripts\install-deps.ps1`。若自动安装失败，按本文逐步手动装。

---

## 0. 目标检查清单

装完后，在 **新开的** PowerShell 窗口执行：

```powershell
node -v
npm -v
ziniao-cli -v
ziniao-cli doctor
```

期望大致如下：

| 命令 | 期望 |
|------|------|
| `node -v` | 有版本号，如 `v22.x` / `v24.x` |
| `npm -v` | 有版本号 |
| `ziniao-cli -v` | 有版本号（如 `1.0.7`） |
| `ziniao-cli doctor` | 配置 / API Key / ZClaw Bridge / 客户端登录尽量通过 |

另外：

- [ ] 紫鸟**桌面客户端**已安装并登录  
- [ ] 项目里有 `config\stores.config.json`（飞书凭证）  
- [ ] 能跑：`powershell -ExecutionPolicy Bypass -File .\scripts\run-multi-store.ps1 -ListOnly`

---

## 1. 安装 Node.js LTS（国内镜像）

### 方式 A：浏览器下载 MSI（最稳妥）

1. 打开 npmmirror 的 Node 镜像：  
   **https://npmmirror.com/mirrors/node/**  
   或目录索引：  
   **https://cdn.npmmirror.com/binaries/node/**
2. 进入 **最新 LTS** 版本目录（如 `v22.xx.x` 或带 LTS 标注的版本）。  
   - 不要刻意追最新 Current；**LTS** 更稳。
3. 下载 Windows 64 位安装包：  
   `node-vxx.x.x-x64.msi`
4. 双击 MSI → 一路下一步。  
   - 勾选 **Automatically install necessary tools** 可勾可不勾（本项目不强制）。  
   - 确保 **Add to PATH** 类选项保持默认开启。
5. **关掉所有已打开的 PowerShell / 启动器 / 黑窗口**，再新开一个 PowerShell，执行：

```powershell
node -v
npm -v
```

若提示找不到命令：

- 注销/重启一次 Windows；或  
- 确认 `C:\Program Files\nodejs\` 存在，并把该路径加到系统环境变量 **Path**。

### 方式 B：官网

- https://nodejs.org/  
- 选 **LTS** → Windows Installer (.msi)

### 方式 C：winget（需本机有 winget）

**以管理员身份**打开 PowerShell：

```powershell
winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
```

装完后**新开**终端再 `node -v`。

---

## 2. 配置 npm 国内镜像（加快后续安装）

新开 PowerShell：

```powershell
npm config set registry https://registry.npmmirror.com
npm config get registry
```

应输出：`https://registry.npmmirror.com`

（若必须用官方源：`npm config set registry https://registry.npmjs.org`）

---

## 3. 安装 ziniao-cli

```powershell
npm install -g @ziniao-open/cli
```

验证：

```powershell
ziniao-cli -v
```

### 若提示「不是内部或外部命令」

1. 查全局前缀：

```powershell
npm prefix -g
```

常见路径：`C:\Users\你的用户名\AppData\Roaming\npm`

2. 确认该目录下有 `ziniao-cli.cmd`。  
3. 把该目录加入用户 **Path**，然后**新开**终端。  
4. 或直接用 node 调入口（与本项目多店脚本兜底方式一致）：

```powershell
node "%APPDATA%\npm\node_modules\@ziniao-open\cli\scripts\run.js" -v
node "%APPDATA%\npm\node_modules\@ziniao-open\cli\scripts\run.js" doctor
```

### 若 npm 报权限 / EACCES

- 不要用奇怪的全局目录权限；  
- 用当前用户安装即可（默认装到 `%APPDATA%\npm`）；  
- 尽量**不要**在「被公司策略锁死的 Program Files」里硬装。

### 若下载极慢或超时

确认第 2 步 registry 已是 npmmirror；或临时：

```powershell
npm install -g @ziniao-open/cli --registry https://registry.npmmirror.com
```

---

## 4. 配置紫鸟 CLI 的 API Key

抓取店铺窗口依赖本地 **ZClaw Bridge**（紫鸟客户端），CLI 通常还需要在开放平台创建的 **API Key**（成员账号即可）。

### 4.1 拿 Key

1. 浏览器打开：https://open.ziniao.com/  
2. 登录有权限的账号  
3. 创建/进入应用 → 获取 **API Key**（按你们公司开放平台实际菜单）

### 4.2 写入本机配置

**交互方式（推荐）：**

```powershell
ziniao-cli config init --member
```

按提示粘贴 API Key。

**管道方式（适合复制粘贴一次）：**

```powershell
# 把 YOUR_KEY 换成真实密钥
echo YOUR_KEY| ziniao-cli config init --api-key-stdin --member --profile default
```

查看是否配置成功：

```powershell
ziniao-cli config show
ziniao-cli doctor
```

配置文件一般在：

```text
C:\Users\你的用户名\.ziniao-cli\config.json
```

密钥可能在系统凭据（Keychain）里，不要求明文出现在 json 中。

---

## 5. 安装并登录紫鸟桌面客户端（必做）

**脚本无法代替这一步。**

1. 安装公司指定的 **紫鸟浏览器 / 紫鸟客户端**（向管理员要安装包或内网下载地址）。  
2. 打开客户端并登录（与 CLI 同公司账号体系更佳）。  
3. 确认店铺已绑定设备/IP（本项目默认 `requireIp: true`，未绑 IP 的店会被跳过）。  
4. 保持客户端在线，再执行：

```powershell
ziniao-cli doctor
```

其中 **ZClaw Bridge**、**客户端登录状态** 应通过。

若 Bridge 失败：

- 确认紫鸟客户端真的在运行（托盘里有图标）  
- 重启客户端后再 `doctor`  
- 关闭可能拦截本机 `127.0.0.1` 的代理/安全软件后重试  
- 不要同时开多个冲突版本的紫鸟

---

## 6. 项目侧配置

1. 解压项目到本机路径（路径尽量短、少特殊字符；中文路径一般可用，但出问题时可改到如 `D:\TK广告投流监测`）。  
2. 确认存在：

```text
config\stores.config.json
```

若没有：

```text
复制 config\stores.config.example.json
改名为 config\stores.config.json
填写飞书 appId / appSecret / appToken / tableId
```

3. 按需改：

| 配置 | 说明 |
|------|------|
| `filter.excludeStoreIds` | 临时排除有问题的店 |
| `adsUrl.byPlatform` | 英区 / 欧盟广告页地址 |
| `options.dryRun` | `true` 干跑不写飞书 |

---

## 7. 首次验证（不要一上来就写飞书）

在项目根目录 PowerShell：

```powershell
# 1) 只列会抓哪些店（不打开广告页也可）
powershell -ExecutionPolicy Bypass -File .\scripts\run-multi-store.ps1 -ListOnly

# 2) 干跑（会开紫鸟店铺窗，不写飞书）
powershell -ExecutionPolicy Bypass -File .\scripts\run-multi-store.ps1 -DryRun true
```

或双击 **`启动器.bat` / `美化启动器.bat`**：

1. 预览店铺列表  
2. 干跑抓取  
3. 确认 `日报\` 下有最新日报后再「正式写入飞书」

---

## 8. 常见失败对照

| 现象 | 处理 |
|------|------|
| `node` / `npm` 找不到 | 重装 Node 并勾选 PATH；新开终端；检查 `C:\Program Files\nodejs` |
| `ziniao-cli` 找不到 | `npm i -g @ziniao-open/cli`；把 `%APPDATA%\npm` 加入 Path |
| npm 很慢 / 超时 | `npm config set registry https://registry.npmmirror.com` |
| `doctor` Bridge 失败 | 打开并登录紫鸟客户端 |
| `doctor` API Key 失败 | 重新 `ziniao-cli config init --member` |
| 自动安装日志里 `run: msiexec.exe` 后面没参数 | 旧版脚本 bug，换新包里的 `install-deps.ps1`（参数名已改为 CmdArgs） |
| `msiexec exit=1639` | 用本文 §1 手动双击 MSI；或以管理员运行 |
| 公司电脑禁止安装软件 | 找 IT 装 Node，或使用已预装 Node 的机器 |
| 执行策略限制脚本 | `powershell -ExecutionPolicy Bypass -File ...`（本项目 bat 已带） |
| 杀软隔离 MSI/npm | 加白目录：项目目录、`%TEMP%\tk-node-install`、`%APPDATA%\npm` |

---

## 9. 最小命令速查（复制区）

```powershell
# Node 装好后：
npm config set registry https://registry.npmmirror.com
npm install -g @ziniao-open/cli
ziniao-cli config init --member
ziniao-cli doctor

# 项目根目录：
cd /d 你的项目路径
powershell -ExecutionPolicy Bypass -File .\scripts\run-multi-store.ps1 -ListOnly
powershell -ExecutionPolicy Bypass -File .\scripts\run-multi-store.ps1 -DryRun true
```

---

## 10. 仍搞不定时请收集这些信息

发给维护人时尽量带上：

1. `node -v` / `npm -v` / `where.exe node` / `where.exe npm` 输出  
2. `npm prefix -g` 与 `npm config get registry`  
3. `ziniao-cli -v` 与 `ziniao-cli doctor` 全文  
4. 紫鸟客户端是否已登录（是/否）  
5. 系统：Win10/11、是否管理员、是否公司管控电脑  
6. 自动安装完整日志（若跑过 `安装环境.bat`）

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `安装环境.bat` | 一键自动装（优先） |
| `scripts\install-deps.ps1` | 自动安装脚本（默认国内镜像） |
| `docs\运维与排障.md` | 抓取/飞书日常排障 |
| `docs\每日定时任务.md` | 17:20 计划任务 |
| `config\stores.config.example.json` | 飞书与店铺筛选模板 |
