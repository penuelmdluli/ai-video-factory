@echo off
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
echo ==== maintenance %DATE% %TIME% ==== >> "maintenance\maintenance.log"
python "maintenance\music_maintenance.py" >> "maintenance\maintenance.log" 2>&1
