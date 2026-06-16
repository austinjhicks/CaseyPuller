@echo off
cd /d "%~dp0"

echo Installing required packages...
py -m pip install -r requirements.txt

echo Starting CaseyPuller...
start http://127.0.0.1:5000
py app.py

pause