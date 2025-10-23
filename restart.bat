@echo off
echo Restarting panDirectServer...
timeout /t 1 /nobreak >nul
cd /d %~dp0
python app.py
pause