@echo off
echo Starting Daily Data Collection...
cd /d "%~dp0"
python collector.py
echo Update Complete.
pause
