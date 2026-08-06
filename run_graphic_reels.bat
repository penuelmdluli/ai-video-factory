@echo off
REM $0 beat-synced reels -> Tech Pulse Africa (news), Smart Money AI (finance), Elevate You (motivation).
REM Launched 3x/day by Windows Task Scheduler. No RunPod video; only free local Kokoro voice.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
"C:\Program Files\Python312\python.exe" post_all.py >> output\_scheduled_graphic.log 2>&1
