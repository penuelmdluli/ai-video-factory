@echo off
:: AI Video Factory - Scheduler launcher.
::
:: RESTORED 2026-08-29 (owner instruction). It was stopped on 21 Aug because
:: scheduler.py posted tech_news, ai_money and health_wellness reels to the
:: Genesis News TikTok, which belongs to the soccer page. That leak is fixed
:: in modules/uploader_tiktok.py: a page may only post to TikTok with its own
:: TIKTOK_SESSION_ID_<niche>, or as TIKTOK_OWNER_NICHE.
::
:: Three guards the original did not have, because scheduler.py is a resident
:: daemon (while True) launched by a DAILY task:
::
::   1. SINGLETON. Without it every morning's run started another immortal
::      copy alongside yesterday's, each posting independently. That is the
::      same orphan-accumulation that duplicated matchday posts.
::   2. A KILL SWITCH. The old loop was "goto loop" with no exit, which is
::      why the owner's note says stopping the task alone never held. Create
::      logs\scheduler.stop to bring it down without editing this file.
::   3. A BOUNDED restart count, so a crash-loop cannot spin all day.

cd /d "C:\Users\PenuelM\Documents\ai-video-factory"

if exist "logs\scheduler.stop" (
  echo [%date% %time%] scheduler.stop present - not starting >> logs\scheduler_output.log
  exit /b 0
)

:: Singleton: another launcher already holds the lock.
if exist "logs\scheduler.lock" (
  echo [%date% %time%] another scheduler launcher is running - exiting >> logs\scheduler_output.log
  exit /b 0
)
echo %date% %time% > "logs\scheduler.lock"

set /a TRIES=0

:loop
if exist "logs\scheduler.stop" goto done
if %TRIES% GEQ 12 (
  echo [%date% %time%] 12 restarts - giving up, something is wrong >> logs\scheduler_output.log
  goto done
)
echo [%date% %time%] Starting AI Video Factory Scheduler... >> logs\scheduler_output.log
python scheduler.py >> logs\scheduler_output.log 2>&1
set /a TRIES+=1
echo [%date% %time%] Scheduler exited (%ERRORLEVEL%). Restart %TRIES% of 12 in 60s... >> logs\scheduler_output.log
timeout /t 60 /nobreak > nul
goto loop

:done
del "logs\scheduler.lock" 2>nul
echo [%date% %time%] launcher stopped >> logs\scheduler_output.log
exit /b 0
