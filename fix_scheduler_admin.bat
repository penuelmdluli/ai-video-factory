@echo off
:: Run this as Administrator (right-click -> Run as administrator)
:: Fixes: adds daily 4:30AM trigger + removes 72h execution time limit

powershell -ExecutionPolicy Bypass -File "C:\Users\PenuelM\Documents\ai-video-factory\setup_scheduler.ps1"
pause
