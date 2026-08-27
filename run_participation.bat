@echo off
cd /d "%~dp0"
python -X utf8 build_participation.py >> logs\participation.log 2>&1
