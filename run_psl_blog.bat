@echo off
REM Genesis News PSL blog - write articles from live headlines + deploy.
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
python -X utf8 blog\generate_blog.py --psl-only >> logs\psl_blog.log 2>&1
powershell -ExecutionPolicy Bypass -File blog\deploy.ps1 >> logs\psl_blog.log 2>&1
