@echo off
:: AI Video Factory — Growth Engine + Scheduler
:: Runs the full pipeline: videos + engagement + community + cross-promo
:: Auto-restarts on crash with 60s delay

cd /d "C:\Users\PenuelM\Documents\ai-video-factory"

echo ============================================================
echo   AI Video Factory - Growth Engine Started
echo   %date% %time%
echo ============================================================
echo.
echo   Schedule:
echo     Videos: BUILD 5AM/11AM/5PM - UPLOAD 8AM/2PM/8PM
echo     Engagement: 9AM, 12PM, 3PM, 6PM, 9PM (1 post per niche)
echo     Community: Every 2 hours (8AM-8PM)
echo     Cross-Promo: 11AM daily
echo     Insights: 6AM daily
echo     Report: 10PM daily
echo.
echo   Press Ctrl+C to stop
echo ============================================================

:loop
echo [%date% %time%] Starting scheduler... >> logs\scheduler_output.log
python scheduler.py >> logs\scheduler_output.log 2>&1

echo [%date% %time%] Scheduler exited with code %ERRORLEVEL%. Restarting in 60s... >> logs\scheduler_output.log
timeout /t 60 /nobreak > nul
goto loop
