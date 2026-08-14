@echo off
REM Genesis News matchday runner - fixture-aware posts.
REM Predicted XI in the pre-match window, result card at full-time.
REM Safe hourly: quiet days do nothing; matchday_state.json prevents reposts.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 matchday.py auto --post >> logs\matchday_auto.log 2>&1
