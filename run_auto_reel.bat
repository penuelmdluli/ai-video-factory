@echo off
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
"C:\Program Files\Python312\python.exe" auto_reel.py >> logs\auto_reel_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
