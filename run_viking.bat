@echo off
REM SAGA OF THE NORTH — post the next Viking short from the bank to the page. Run 3x/day.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
"C:\Program Files\Python312\python.exe" post_next_viking.py >> output\_scheduled_viking.log 2>&1
