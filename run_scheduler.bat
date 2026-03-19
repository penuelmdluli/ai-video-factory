@echo off
:: AI Video Factory - Auto Scheduler Launcher with Auto-Restart
:: If the scheduler crashes, it waits 60s and restarts automatically.

cd /d "C:\Users\PenuelM\Documents\ai-video-factory"

:loop
echo [%date% %time%] Starting AI Video Factory Scheduler... >> logs\scheduler_output.log
python scheduler.py >> logs\scheduler_output.log 2>&1

:: If we get here, python exited (crash or error)
echo [%date% %time%] Scheduler exited with code %ERRORLEVEL%. Restarting in 60s... >> logs\scheduler_output.log
timeout /t 60 /nobreak > nul
goto loop
