@echo off
REM Genesis News PSL - full news reel build + post (FB + YouTube + comments).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 build_psl_news.py --post >> logs\psl_news.log 2>&1
