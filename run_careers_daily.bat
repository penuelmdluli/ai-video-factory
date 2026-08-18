@echo off
REM Mzansi Careers — post the next VERIFIED opportunity (card + reel).
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
python -X utf8 build_careers_post.py >> "logs\careers_daily.log" 2>&1
