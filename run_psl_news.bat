@echo off
REM Genesis News PSL - full news reel build + post (FB + YouTube + comments).
cd /d C:\Users\PenuelM\Documents\ai-video-factory
if not exist logs mkdir logs
REM The slot router picks the format from the fixture calendar:
REM   kickoff <30h  -> predicted XI
REM   kickoff <96h  -> selection debate (rotating position group)
REM   otherwise     -> news reel
REM It falls through to the news reel on any doubt, so a slot is never empty.
python -X utf8 build_psl_slot.py --post >> logs\psl_news.log 2>&1
