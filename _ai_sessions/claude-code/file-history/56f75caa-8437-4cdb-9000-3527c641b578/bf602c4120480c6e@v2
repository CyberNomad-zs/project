# 为「清泉 · AMZ 驾驶舱」三张多维表创建字段（T1/T3/T6）
# 用法：先在飞书 Base 里建好三张空表（或仅有默认「文本」列），填入 table id 后运行。
#
#   $env:FEISHU_APP_ID="cli_xxx"
#   $env:FEISHU_APP_SECRET="xxx"
#   $env:FEISHU_APP_TOKEN="bascn..."          # Base app_token
#   $env:FEISHU_TABLE_AMZ_SHOP_DAILY="tbl..." # T1 店铺日经营
#   $env:FEISHU_TABLE_AMZ_LINK_DAILY="tbl..." # T3 链接日指标
#   $env:FEISHU_TABLE_AMZ_RISK="tbl..."       # T6 风险告警
#   # 也可只建一张：设 FEISHU_TABLE_ID + FEISHU_AMZ_TABLE_KIND=shop|link|risk
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\feishu-amz-create-fields.ps1

$ErrorActionPreference = 'Stop'

$appId = $env:FEISHU_APP_ID
$appSecret = $env:FEISHU_APP_SECRET
$appToken = $env:FEISHU_APP_TOKEN
if (-not $appToken) { $appToken = $env:FEISHU_BITABLE_APP_TOKEN_AMZ }
if (-not $appToken) { $appToken = $env:FEISHU_BITABLE_APP_TOKEN }

function Invoke-FeishuJson {
  param(
    [string]$Method,
    [string]$Url,
    [hashtable]$Headers,
    [object]$Body
  )
  $params = @{
    Method      = $Method
    Uri         = $Url
    Headers     = $Headers
    ContentType = 'application/json; charset=utf-8'
  }
  if ($null -ne $Body) {
    $json = $Body | ConvertTo-Json -Depth 12 -Compress
    $params.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
  }
  return Invoke-RestMethod @params
}

function New-TextField([string]$Name) {
  return @{ field_name = $Name; type = 1 }
}
function New-NumberField([string]$Name, [string]$Fmt = '0.00') {
  return @{ field_name = $Name; type = 2; property = @{ formatter = $Fmt } }
}
function New-DateField([string]$Name, [string]$Fmt = 'yyyy/MM/dd') {
  return @{ field_name = $Name; type = 5; property = @{ date_formatter = $Fmt; auto_fill = $false } }
}
function New-SingleSelect([string]$Name, [string[]]$Options) {
  $opts = @()
  foreach ($o in $Options) { $opts += @{ name = $o } }
  return @{ field_name = $Name; type = 3; property = @{ options = $opts } }
}

$T1 = @(
  (New-DateField '日期'),
  (New-TextField '店铺'),
  (New-TextField '店铺ID'),
  (New-TextField '站点'),
  (New-TextField '币种'),
  (New-NumberField '销售额'),
  (New-NumberField '订单量' '0'),
  (New-NumberField '销量' '0'),
  (New-NumberField '访客数' '0'),
  (New-NumberField '加购数' '0'),
  (New-NumberField '客单价'),
  (New-NumberField '退货量' '0'),
  (New-NumberField '退货率' '0.00%'),
  (New-NumberField '毛利'),
  (New-NumberField '广告花费'),
  (New-NumberField '广告销售额'),
  (New-NumberField 'ACoS' '0.00%'),
  (New-NumberField '广告贡献毛利'),
  (New-NumberField '净利润'),
  (New-NumberField '净利率' '0.00%'),
  (New-NumberField 'ROI'),
  (New-NumberField '销售额环比' '0.00%'),
  (New-NumberField '利润环比' '0.00%'),
  (New-NumberField '销售额同比' '0.00%'),
  (New-SingleSelect '数据状态' @('success', 'partial', 'error')),
  (New-DateField '抓取时间' 'yyyy/MM/dd HH:mm'),
  (New-TextField '数据源'),
  (New-TextField '本地ID')
)

$T3 = @(
  (New-DateField '日期'),
  (New-TextField '店铺ID'),
  (New-TextField 'ASIN'),
  (New-TextField 'SKU'),
  (New-TextField '标题'),
  (New-TextField '类目'),
  (New-NumberField '销量' '0'),
  (New-NumberField '销售额'),
  (New-TextField '币种'),
  (New-NumberField '访客数' '0'),
  (New-NumberField '广告花费'),
  (New-NumberField 'ACoS' '0.00%'),
  (New-NumberField '单品净利润'),
  (New-NumberField 'FBA可售' '0'),
  (New-NumberField '可售天数' '0.0'),
  (New-NumberField '退货率' '0.00%'),
  (New-NumberField '销量环比' '0.00%'),
  (New-NumberField '销售额环比' '0.00%'),
  (New-TextField '问题标签'),
  (New-TextField '第一负责人'),
  (New-DateField '抓取时间' 'yyyy/MM/dd HH:mm'),
  (New-TextField '本地ID')
)

$T6 = @(
  (New-TextField '告警ID'),
  (New-DateField '发现日期'),
  (New-TextField '店铺'),
  (New-TextField '店铺ID'),
  (New-TextField '对象'),
  (New-TextField '风险类型'),
  (New-SingleSelect '优先级' @('P0', 'P1', 'P2')),
  (New-TextField '摘要'),
  (New-TextField '指标快照'),
  (New-SingleSelect '状态' @('未处理', '处理中', '已闭环', '忽略')),
  (New-TextField '第一负责人'),
  (New-TextField '关联任务ID'),
  (New-DateField '更新时间' 'yyyy/MM/dd HH:mm'),
  (New-TextField '本地ID')
)

$targets = @()
$shopTbl = $env:FEISHU_TABLE_AMZ_SHOP_DAILY
if (-not $shopTbl) { $shopTbl = $env:FEISHU_BITABLE_TABLE_AMZ_SHOP_DAILY }
$linkTbl = $env:FEISHU_TABLE_AMZ_LINK_DAILY
if (-not $linkTbl) { $linkTbl = $env:FEISHU_BITABLE_TABLE_AMZ_LINK_DAILY }
$riskTbl = $env:FEISHU_TABLE_AMZ_RISK
if (-not $riskTbl) { $riskTbl = $env:FEISHU_BITABLE_TABLE_AMZ_RISK }

if ($shopTbl) { $targets += @{ name = 'T1店铺日经营'; tableId = $shopTbl; fields = $T1 } }
if ($linkTbl) { $targets += @{ name = 'T3链接日指标'; tableId = $linkTbl; fields = $T3 } }
if ($riskTbl) { $targets += @{ name = 'T6风险告警'; tableId = $riskTbl; fields = $T6 } }

if ($targets.Count -eq 0 -and $env:FEISHU_TABLE_ID) {
  $kind = ($env:FEISHU_AMZ_TABLE_KIND | ForEach-Object { $_.ToLower() })
  switch ($kind) {
    'link' { $targets += @{ name = 'T3链接日指标'; tableId = $env:FEISHU_TABLE_ID; fields = $T3 } }
    'risk' { $targets += @{ name = 'T6风险告警'; tableId = $env:FEISHU_TABLE_ID; fields = $T6 } }
    default { $targets += @{ name = 'T1店铺日经营'; tableId = $env:FEISHU_TABLE_ID; fields = $T1 } }
  }
}

if (-not $appId -or -not $appSecret -or -not $appToken -or $targets.Count -eq 0) {
  Write-Host "缺少环境变量。需要："
  Write-Host '  FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_APP_TOKEN(或 BITABLE APP TOKEN)'
  Write-Host '  以及至少一张：FEISHU_TABLE_AMZ_SHOP_DAILY / LINK_DAILY / RISK'
  Write-Host '  或 FEISHU_TABLE_ID + FEISHU_AMZ_TABLE_KIND=shop|link|risk'
  exit 1
}

Write-Host "1) 获取 tenant_access_token ..."
$tokenResp = Invoke-FeishuJson -Method POST `
  -Url 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' `
  -Headers @{} `
  -Body @{ app_id = $appId; app_secret = $appSecret }
if ($tokenResp.code -ne 0) {
  throw "获取 token 失败: code=$($tokenResp.code) msg=$($tokenResp.msg)"
}
$token = $tokenResp.tenant_access_token
$auth = @{ Authorization = "Bearer $token" }
Write-Host "   OK  app_token=$appToken"

function Ensure-Fields {
  param($Label, $TableId, $FieldSpecs)
  Write-Host ""
  Write-Host "=== $Label  table=$TableId ==="
  $listUrl = "https://open.feishu.cn/open-apis/bitable/v1/apps/$appToken/tables/$TableId/fields?page_size=100"
  $listResp = Invoke-FeishuJson -Method GET -Url $listUrl -Headers $auth -Body $null
  if ($listResp.code -ne 0) {
    throw "列字段失败 ($Label): code=$($listResp.code) msg=$($listResp.msg)"
  }
  $existing = @{}
  foreach ($f in @($listResp.data.items)) {
    if ($f.field_name) { $existing[$f.field_name] = $f }
  }
  Write-Host ("   已有 {0} 字段" -f $existing.Count)

  $createUrl = "https://open.feishu.cn/open-apis/bitable/v1/apps/$appToken/tables/$TableId/fields"
  $created = 0; $skipped = 0; $failed = @()
  foreach ($spec in $FieldSpecs) {
    $name = $spec.field_name
    if ($existing.ContainsKey($name)) {
      Write-Host "   skip  $name"
      $skipped++
      continue
    }
    try {
      $r = Invoke-FeishuJson -Method POST -Url $createUrl -Headers $auth -Body $spec
      if ($r.code -eq 0) {
        Write-Host "   OK    $name"
        $created++
      }
      else {
        Write-Host "   FAIL  $name code=$($r.code) msg=$($r.msg)"
        $failed += "$name : $($r.msg)"
      }
    }
    catch {
      Write-Host "   ERR   $name $_"
      $failed += "$name : $_"
    }
    Start-Sleep -Milliseconds 250
  }
  Write-Host "   小结: 新建 $created , 跳过 $skipped , 失败 $($failed.Count)"
  if ($failed.Count -gt 0) {
    $failed | ForEach-Object { Write-Host "     - $_" }
  }
}

foreach ($t in $targets) {
  Ensure-Fields -Label $t.name -TableId $t.tableId -FieldSpecs $t.fields
}

Write-Host ""
Write-Host "完成。请将 table id 写入 .env："
Write-Host "  FEISHU_BITABLE_APP_TOKEN_AMZ=$appToken"
if ($shopTbl) { Write-Host "  FEISHU_BITABLE_TABLE_AMZ_SHOP_DAILY=$shopTbl" }
if ($linkTbl) { Write-Host "  FEISHU_BITABLE_TABLE_AMZ_LINK_DAILY=$linkTbl" }
if ($riskTbl) { Write-Host "  FEISHU_BITABLE_TABLE_AMZ_RISK=$riskTbl" }
