@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 backup_database.py
if errorlevel 1 python backup_database.py
pause