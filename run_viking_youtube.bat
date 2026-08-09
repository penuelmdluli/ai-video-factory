@echo off
REM SAGA OF THE NORTH — upload the next built episode(s) to YouTube (Blissful Moments channel).
REM Runs daily; count kept low to stay inside the YouTube upload quota.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
"C:\Program Files\Python312\python.exe" upload_viking_youtube.py --count 2 >> output\_scheduled_viking_youtube.log 2>&1
