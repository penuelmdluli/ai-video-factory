@echo off
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 build_fb_hitlist.py >> logs\hitlist.log 2>&1
