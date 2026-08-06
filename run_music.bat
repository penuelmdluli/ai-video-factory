@echo off
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
if not exist "output\music" mkdir "output\music"
echo ==== music %DATE% %TIME% ==== >> "output\music\scheduler.log"
python make_music.py >> "output\music\scheduler.log" 2>&1
