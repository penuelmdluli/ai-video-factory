@echo off
REM SAGA OF THE NORTH — engagement check. Pulls fresh Graph API numbers, diffs vs the saved
REM baseline, and writes logs\viking_engagement_report.md. One-time task (fires tomorrow morning).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
"C:\Program Files\Python312\python.exe" check_viking_engagement.py >> output\_viking_engagement.log 2>&1
