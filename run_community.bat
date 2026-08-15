@echo off
REM Genesis News community round - reply to FB + YouTube comments (family chat).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 modules\yt_community.py >> logs\community.log 2>&1
python -X utf8 -c "import asyncio; from modules.community_manager import run_community_round; asyncio.run(run_community_round(['sa_pulse']))" >> logs\community.log 2>&1
python -X utf8 modules\yt_outreach.py >> logs\community.log 2>&1
