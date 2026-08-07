@echo off
setlocal EnableDelayedExpansion
chcp 936 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo   发货哨兵 · 演示机一键生成（AI 处置建议 + 离线打包）
echo   流程： build -^> ai_enrich -^> build -^> pack
echo ============================================================
echo.

REM ---- 1. 定位 Python ----
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY (
  echo [错误] 没找到 Python。请先安装 Python 3 并加入 PATH，再重跑本脚本。
  goto :fail
)
echo [环境] Python: %PY%

REM ---- 2. 检查 API Key（未设也放行，可能用 ant auth login 登录态） ----
if defined ANTHROPIC_API_KEY (
  echo [环境] 已检测到 ANTHROPIC_API_KEY
) else (
  echo [提示] 未检测到 ANTHROPIC_API_KEY 环境变量。
  echo        - 若你已用  ant auth login  登录，可忽略本提示，脚本会继续。
  echo        - 否则请先在本窗口执行：  set ANTHROPIC_API_KEY=你的Key   再重跑本脚本。
  echo.
)

REM ---- 3. 模型（默认 claude-opus-4-8；把模型名作为第一个参数传入可覆盖，如 claude-haiku-4-5 省成本） ----
if not "%~1"=="" set "SENTINEL_AI_MODEL=%~1"
if defined SENTINEL_AI_MODEL ( echo [环境] 模型: %SENTINEL_AI_MODEL% ) else ( echo [环境] 模型: claude-opus-4-8（默认） )
echo.

REM ---- 4. 四步流水线（任一步失败即中断） ----
echo [1/4] 生成统一数据模型            (backend\build.py) ...
%PY% backend\build.py || goto :fail
echo.
echo [2/4] 调用大模型生成处置建议      (backend\ai_enrich.py，需联网 + Key) ...
%PY% backend\ai_enrich.py || goto :fail
echo.
echo [3/4] 把 AI 建议烘焙进离线数据    (backend\build.py) ...
%PY% backend\build.py || goto :fail
echo.
echo [4/4] 打包离线演示单文件          (backend\pack.py) ...
%PY% backend\pack.py || goto :fail

echo.
echo ============================================================
echo   ? 完成！离线演示包已更新（含「?? AI 处置建议」卡）。
echo      文件： dist\发货哨兵-离线演示.html
echo      演示现场只需双击这个单文件，可断网运行。
echo ============================================================
echo   正在打开演示包做最后确认 ...
start "" "dist\发货哨兵-离线演示.html"
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   ? 执行中断，未生成 AI 卡。请看上方错误信息。
echo   常见原因：
echo     - 未装 anthropic SDK    ->  pip install anthropic
echo     - 未配 ANTHROPIC_API_KEY 或未联网
echo     - 未装 Python / 不在 PATH
echo   （即便不跑本脚本，其余看板功能不受影响，仅缺 AI 处置建议卡）
echo ============================================================
echo.
pause
exit /b 1
