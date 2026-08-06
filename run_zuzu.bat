@echo off
REM Zuzu & Friends daily auto-pipeline — produces + posts one edutainment video.
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
if not exist "output\zuzu" mkdir "output\zuzu"
echo ==== Zuzu run %DATE% %TIME% ==== >> "output\zuzu\scheduler.log"
REM --remotion = crisp programmatic episode (Zuzu character + karaoke), no SDXL/LTX wobble
python make_zuzu.py --remotion >> "output\zuzu\scheduler.log" 2>&1
echo ---- exit %ERRORLEVEL% ---- >> "output\zuzu\scheduler.log"
