@echo off
REM Community round - reply to FB + YouTube comments (family chat).
REM sa_pulse = Genesis News, motivation = Mzansi Careers (jobs page).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 modules\yt_community.py >> logs\community.log 2>&1
python -X utf8 -c "import asyncio; from modules.community_manager import run_community_round; asyncio.run(run_community_round(['sa_pulse','motivation']))" >> logs\community.log 2>&1
python -X utf8 modules\yt_outreach.py >> logs\community.log 2>&1
