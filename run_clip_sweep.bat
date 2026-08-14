@echo off
REM Genesis News - daily CC clip library sweep (recent real footage per club).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 modules\clip_library.py --sweep >> logs\clip_sweep.log 2>&1
