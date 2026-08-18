@echo off
REM Bring the PM2 bots (genesis-live, genesis-vault, shopmo-agent) back up
REM after a reboot. Safe to run repeatedly — already-online processes are
REM left alone.
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
"%APPDATA%\npm\pm2.cmd" resurrect >> "logs\pm2_resurrect.log" 2>&1
"%APPDATA%\npm\pm2.cmd" list >> "logs\pm2_resurrect.log" 2>&1
