@echo off
REM Keep the ShopMO WhatsApp agent alive: restore PM2 daemon + saved processes.
call pm2 resurrect >nul 2>&1
call pm2 start "C:\Users\PenuelM\Documents\SELLBOT\shopmo-whatsapp\ecosystem.config.cjs" --only shopmo-agent >nul 2>&1
