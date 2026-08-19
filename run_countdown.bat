@echo off
cd /d "%~dp0"
python -X utf8 build_countdown.py >> logs\countdown.log 2>&1
