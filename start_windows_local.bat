@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Accounting Interview - local server
py -3 server.py --host 127.0.0.1 --port 8765
if errorlevel 1 (
  echo Trying Python installed on PATH...
  python server.py --host 127.0.0.1 --port 8765
)
pause