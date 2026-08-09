@echo off
cd /d "C:\Users\PenuelM\Documents\ai-video-factory"
if not exist "blog\logs" mkdir "blog\logs"
echo ==== blog %DATE% %TIME% ==== >> "blog\logs\scheduler.log"
REM 1) write the next rotating SEO post + rebuild the static site
python blog\generate_blog.py >> "blog\logs\scheduler.log" 2>&1
REM 1b) publish any newly-built SAGA OF THE NORTH episodes as self-hosted video posts
python blog\viking_blog.py >> "blog\logs\scheduler.log" 2>&1
REM 2) deploy to Cloudflare Pages (needs one-time `wrangler login`; skips cleanly if not authed)
powershell -NoProfile -ExecutionPolicy Bypass -File "blog\deploy.ps1" >> "blog\logs\scheduler.log" 2>&1
REM 3) cross-promote the new post to the matching Facebook page
python blog\cross_post_fb.py >> "blog\logs\scheduler.log" 2>&1
echo ---- done %DATE% %TIME% ---- >> "blog\logs\scheduler.log"
