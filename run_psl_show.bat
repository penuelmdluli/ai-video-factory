@echo off
REM Genesis News long-form preview show (Fri) - builds + posts to YouTube.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 build_psl_show.py --post >> logs\psl_show.log 2>&1
