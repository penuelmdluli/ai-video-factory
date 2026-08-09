@echo off
REM SAGA OF THE NORTH — autonomous top-up builder. Runs daily (06:00) before the posting slots,
REM keeps a buffer of ready episodes so post_next_viking.py never runs dry, stops on its own when
REM the whole season is built.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
"C:\Program Files\Python312\python.exe" auto_viking_build.py >> output\_scheduled_viking_build.log 2>&1
