@echo off
REM Auto-reply to Facebook comments across all pages (safe engagement booster).
REM Runs on a schedule; community_manager has war-neutral safety + rate limiting.
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
if not exist logs mkdir logs
echo ==== community %DATE% %TIME% ==== >> logs\community.log
python -m modules.community_manager >> logs\community.log 2>&1
echo ---- exit %ERRORLEVEL% ---- >> logs\community.log
