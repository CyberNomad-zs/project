# -*- 清理浏览器缓存(保留登录态)-*-
# 由 启动.bat 的菜单项 [7] 调用,也可单独右键"用 PowerShell 运行"。
$ErrorActionPreference = 'SilentlyContinue'
$p = Join-Path $PSScriptRoot '.browser_profile'

if (-not (Test-Path $p)) {
    Write-Host '未找到 .browser_profile,无需清理(可能还没首次登录)。'
    return
}

# 若浏览器/自动化正占用该 profile,文件被锁,先提示关闭
$busy = Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='chromium.exe'" |
    Where-Object { $_.CommandLine -like "*$p*" }
if ($busy) {
    Write-Host '检测到浏览器/自动化正在使用该 profile,请先关闭浏览器和正在运行的脚本再清理。'
    return
}

$before = (Get-ChildItem $p -Recurse -File | Measure-Object Length -Sum).Sum

# 只删纯缓存,登录态(Cookies / Login Data / Local Storage 等)一律不动
$targets = @(
    'Default\Cache',
    'Default\Code Cache',
    'Default\GPUCache',
    'Default\Service Worker\CacheStorage',
    'Default\Service Worker\ScriptCache',
    'Default\DawnWebGPUCache',
    'Default\DawnGraphiteCache',
    'GrShaderCache',
    'ShaderCache',
    'GPUPersistentCache',
    'BrowserMetrics',
    'BrowserMetrics-spare.pma'
)
foreach ($t in $targets) {
    $full = Join-Path $p $t
    if (Test-Path $full) { Remove-Item $full -Recurse -Force }
}

$after = (Get-ChildItem $p -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ('清理完成:{0:N1} MB  ->  {1:N1} MB,释放 {2:N1} MB(登录态已保留,无需重新登录)。' -f ($before/1MB), ($after/1MB), (($before-$after)/1MB))
