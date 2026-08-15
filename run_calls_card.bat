@echo off
REM Weekly OUR CALLS accuracy card (Sun 17:00).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 build_calls_card.py --post >> logs\calls.log 2>&1
