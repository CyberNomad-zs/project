@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Probe Sellfox Temu parent products (read-only)
python probe_temu_products.py --config config/config.g2-3shops.yaml %*
echo.
pause
