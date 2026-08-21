@echo off
:: STOPPED PERMANENTLY 2026-08-21 (owner instruction).
::
:: This launched the old scheduler.py, which was still posting tech_news,
:: ai_money and health_wellness reels to the SAME TikTok account as Genesis
:: News — e.g. a Tech Pulse Africa geopolitics reel at 07:12 today. The
:: TikTok account is for the soccer page only.
::
:: The original launcher is kept as run_scheduler.bat.disabled. It also had
:: an auto-restart loop, which is why stopping the task alone never held.
::
:: The scheduled task "AI Video Factory Scheduler" still exists and could not
:: be disabled from here (Access denied — it needs an elevated prompt), so
:: this launcher is the stop: it exits immediately and posts nothing.
echo [%date% %time%] run_scheduler.bat is disabled by owner instruction - exiting without posting >> logs\scheduler_output.log
exit /b 0
