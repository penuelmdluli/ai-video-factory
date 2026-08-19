@echo off
cd /d "%~dp0"
python -X utf8 build_careers_daily.py >> logs\careers_daily.log 2>&1
