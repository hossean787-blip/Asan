@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo WARNING: LAN mode with HTTP is for testing only. NEVER expose to the internet.
echo You must set up the administrator password on localhost first.
echo Find local IP with: ipconfig
py -3 server.py --host 0.0.0.0 --port 8765
if errorlevel 1 (
  python server.py --host 0.0.0.0 --port 8765
)
pause