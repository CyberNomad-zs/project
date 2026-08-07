@echo off
setlocal
cd /d "%~dp0"
title TK Ad Monitor - install deps
echo.
echo ============================================================
echo   Install Node.js LTS + ziniao-cli
echo   Ziniao desktop client is NOT installed by this script
echo ============================================================
echo.
echo   If auto-install fails, open:
echo     docs\manual-install-env.md
echo   or:
echo     docs\  and read the Chinese manual md there.
echo.
echo   Optional: paste Ziniao API Key, or just press Enter to skip.
echo.
set "APIKEY="
set /p APIKEY=API Key (optional): 

set "PS1=%~dp0scripts\install-deps.ps1"
if not exist "%PS1%" (
  echo [ERROR] missing: %PS1%
  pause
  exit /b 1
)

where powershell >nul 2>nul
if errorlevel 1 (
  echo [ERROR] powershell.exe not found
  pause
  exit /b 1
)

if "%APIKEY%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -ApiKey "%APIKEY%"
)

set "EC=%ERRORLEVEL%"
echo.
echo ---------- done exit=%EC% ----------
pause
exit /b %EC%