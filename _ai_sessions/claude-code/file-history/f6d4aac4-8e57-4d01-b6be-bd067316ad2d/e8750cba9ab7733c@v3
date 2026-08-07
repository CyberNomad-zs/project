# 在已有飞书多维表格中创建插件所需字段
# 用法：
#   $env:FEISHU_APP_ID="cli_xxx"
#   $env:FEISHU_APP_SECRET="xxx"
#   $env:FEISHU_APP_TOKEN="你的app_token"
#   $env:FEISHU_TABLE_ID="你的table_id"
#   powershell -ExecutionPolicy Bypass -File .\scripts\feishu-create-fields.ps1

$ErrorActionPreference = 'Stop'

$appId = $env:FEISHU_APP_ID
$appSecret = $env:FEISHU_APP_SECRET
$appToken = $env:FEISHU_APP_TOKEN
$tableId = $env:FEISHU_TABLE_ID

if (-not $appId -or -not $appSecret -or -not $appToken -or -not $tableId) {
  Write-Host "缺少环境变量。请设置："
  Write-Host '  $env:FEISHU_APP_ID="cli_xxxx"'
  Write-Host '  $env:FEISHU_APP_SECRET="你的App Secret"'
  Write-Host '  $env:FEISHU_APP_TOKEN="你的app_token"'
  Write-Host '  $env:FEISHU_TABLE_ID="你的table_id"'
  Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\feishu-create-fields.ps1"
  Write-Host ""
  Write-Host "说明：开放平台创建应用 → 开通多维表格权限并发布 → 表格中添加该应用 → 再运行本脚本"
  exit 1
}

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
    $json = $Body | ConvertTo-Json -Depth 10 -Compress
    $params.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
  }
  return Invoke-RestMethod @params
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
Write-Host "   OK"

Write-Host "2) 列出已有字段 ..."
$listUrl = "https://open.feishu.cn/open-apis/bitable/v1/apps/$appToken/tables/$tableId/fields?page_size=100"
$listResp = Invoke-FeishuJson -Method GET -Url $listUrl -Headers $auth -Body $null
if ($listResp.code -ne 0) {
  throw "列字段失败: code=$($listResp.code) msg=$($listResp.msg)"
}
$existing = @{}
foreach ($f in @($listResp.data.items)) {
  if ($f.field_name) { $existing[$f.field_name] = $f }
}
Write-Host ("   已有 {0} 个字段: {1}" -f $existing.Count, ($existing.Keys -join ', '))

# 与 extension/lib/constants.js BITABLE_FIELDS 对齐
$fieldsToCreate = @(
  @{ field_name = '日期'; type = 5; property = @{ date_formatter = 'yyyy/MM/dd'; auto_fill = $false } },
  @{ field_name = '店铺'; type = 1 },
  @{ field_name = '店铺ID'; type = 1 },
  @{ field_name = '品名'; type = 1 },
  @{ field_name = '广告花费'; type = 2; property = @{ formatter = '0.00' } },
  @{ field_name = '销量'; type = 2; property = @{ formatter = '0' } },
  @{ field_name = 'ROI'; type = 2; property = @{ formatter = '0.00' } },
  @{ field_name = '销售额'; type = 2; property = @{ formatter = '0.00' } },
  @{ field_name = '抓取时间'; type = 5; property = @{ date_formatter = 'yyyy/MM/dd HH:mm'; auto_fill = $false } },
  @{ field_name = '数据源URL'; type = 1 },
  @{ field_name = '状态'; type = 3; property = @{
      options = @(
        @{ name = 'success' },
        @{ name = 'partial' },
        @{ name = 'error' }
      )
    }
  }
)

$createUrl = "https://open.feishu.cn/open-apis/bitable/v1/apps/$appToken/tables/$tableId/fields"
$created = 0
$skipped = 0
$failed = @()

Write-Host "3) 创建缺失字段 ..."
foreach ($spec in $fieldsToCreate) {
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
  Start-Sleep -Milliseconds 200
}

Write-Host ""
Write-Host "完成: 新建 $created , 跳过 $skipped , 失败 $($failed.Count)"
if ($failed.Count -gt 0) {
  Write-Host "失败明细:"
  $failed | ForEach-Object { Write-Host "  - $_" }
}
Write-Host "App Token = $appToken"
Write-Host "Table ID  = $tableId"
