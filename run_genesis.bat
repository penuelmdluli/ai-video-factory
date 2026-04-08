@echo off
REM ====================================================
REM  Genesis Content Engine — Daily Scheduler
REM  Runs the full pipeline: trends → scripts → videos → watermark → post
REM  Uses Genesis Studio Brain Studio for video generation
REM ====================================================

cd /d "%~dp0"

:loop
echo [%date% %time%] Starting Genesis Content Engine scheduler...
python -u -m genesis.scheduler
echo [%date% %time%] Scheduler exited. Restarting in 60 seconds...
timeout /t 60
goto loop
