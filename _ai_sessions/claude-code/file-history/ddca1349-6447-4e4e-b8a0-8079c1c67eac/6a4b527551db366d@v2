@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 在已加赛狐 IP 白名单的机器上运行。
echo 用法示例: run_probe_tiktok.bat --shop 你的TK赛狐shopId
python probe_tiktok.py --config config\config.g2-3shops.yaml -o logs\tk_probe.json %*
echo exit=%ERRORLEVEL%
pause
