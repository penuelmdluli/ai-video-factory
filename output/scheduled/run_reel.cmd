@echo off
REM ===========================================================================
REM Genesis dance reel — one scheduled run.
REM
REM Driven by Windows Task Scheduler, NOT by the Claude app. The in-app
REM scheduler only dispatches while the app is open, which silently missed the
REM 19:45 and 07:00 slots on 2026-08-31/09-01. Task Scheduler fires whether or
REM not anything is open, as long as the machine is powered on.
REM
REM make_dance_reel.py posts a queued reel if one is waiting, otherwise builds
REM a fresh one: picks an unused character, picks the least-used driver,
REM generates the still, transfers the motion, brands, hooks, posts, seeds the
REM first comment, and records both ledgers only on a confirmed publish.
REM ===========================================================================
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
set PYTHONIOENCODING=utf-8
echo. >> "output\scheduled\reel_cron.log"
echo ===== %DATE% %TIME% ===== >> "output\scheduled\reel_cron.log"
python make_dance_reel.py --post --show >> "output\scheduled\reel_cron.log" 2>&1
echo exit=%ERRORLEVEL% >> "output\scheduled\reel_cron.log"

REM Read view counts back off the profile AFTER the post, never before: a
REM scrape that hangs, or breaks on a Facebook layout change, must not be able
REM to delay or block publishing. The numbers feed dance_cast.pick(), which
REM only judges a setting once three posts have actually been measured for it
REM — so a run that collects nothing simply leaves the rotation on its
REM fairness order, which is what it did before any of this existed.
python -X utf8 -m modules.profile_stats >> "output\scheduled\reel_cron.log" 2>&1
echo stats_exit=%ERRORLEVEL% >> "output\scheduled\reel_cron.log"
