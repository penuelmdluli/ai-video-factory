@echo off
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 build_log_card.py --post >> logs\log_card.log 2>&1
