@echo off
rem First-run setup: config.json + npm install. Pure ASCII, path-safe.
cd /d "%~dp0."
title Temu first-run setup
echo.
echo === Temu Traffic Monitor - first run ===
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo [ERR] Node.js not found. Install LTS from https://nodejs.org
  echo Then run this bat again.
  pause
  exit /b 1
)

if not exist "config.json" (
  if exist "config.example.json" (
    echo [1/2] Creating config.json from example ...
    copy /Y "config.example.json" "config.json" >nul
    echo       Done. Please edit config.json later:
    echo       - feishuWebhooks
    echo       - storeList
    echo       - keep fullRun false
  ) else (
    echo [ERR] config.example.json missing. Wrong folder?
    pause
    exit /b 1
  )
) else (
  echo [1/2] config.json already exists.
)

echo.
echo [2/2] npm install (may take 1-3 minutes) ...
call npm install
if errorlevel 1 (
  echo.
  echo [ERR] npm install failed. Check network / Node install.
  pause
  exit /b 1
)

if not exist "node_modules\playwright" (
  echo [ERR] playwright still missing after npm install.
  pause
  exit /b 1
)

echo.
echo === OK. Next steps ===
echo   1. Optional: edit config.json (Feishu webhook + store names)
echo   2. Run start-menu.bat  or  launch-gui.bat
echo   3. Menu 1 = Login Temu
echo   4. Menu 2 = Traffic once   /  Menu 3 = keep running
echo.
pause
