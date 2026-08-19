@echo off
cd /d "%~dp0"
python -X utf8 build_perf_report.py >> logs\perf_report.log 2>&1
