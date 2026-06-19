@echo off
cd /d "%~dp0"
echo Starting SMS Sync...
python -m src.main
pause
