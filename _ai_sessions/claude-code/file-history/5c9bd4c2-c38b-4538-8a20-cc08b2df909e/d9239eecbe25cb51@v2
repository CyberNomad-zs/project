@echo off
chcp 936 >nul
cd /d "%~dp0"
echo === Feishu notify self-test (python notify.py) ===
where python >nul 2>nul && (python notify.py) || (py -3.12 notify.py)
echo.
pause
