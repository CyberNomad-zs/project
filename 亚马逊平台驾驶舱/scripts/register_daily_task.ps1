# Register Windows scheduled task: hourly ASIN health batch
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Script = Join-Path $Root "scripts\run_daily.ps1"
$TaskName = "ASIN-Health-Daily"
$PsExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $Script)) { throw "script not found: $Script" }
if (-not (Test-Path -LiteralPath $PsExe)) { throw "powershell not found: $PsExe" }

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "removed old task: $TaskName"
}

$Arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$Action = New-ScheduledTaskAction -Execute $PsExe -Argument $Arg -WorkingDirectory $Root

# 每小时一次：从下一整点起，重复间隔 1 小时
$Start = (Get-Date).Date.AddHours((Get-Date).Hour + 1)
$Trigger = New-ScheduledTaskTrigger -Once -At $Start -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 9999)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Sellfox ASIN health hourly once (sync+rules+feishu; notify once per biz day)" | Out-Null

Write-Host "OK registered: $TaskName"
Write-Host "  trigger: every 1 hour (from $Start)"
Write-Host "  script:  $Script"
Write-Host "  workdir: $Root"
Write-Host "  logs:    $(Join-Path $Root 'data\logs')"
Write-Host "  note:    新异常按 task_id 及时通知负责人；群摘要按业务日去重"
Write-Host "test now:  Start-ScheduledTask -TaskName '$TaskName'"
