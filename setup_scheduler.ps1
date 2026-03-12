# AI Video Factory - Setup Scheduled Task (Run as Administrator)
# Usage: Right-click PowerShell -> Run as Administrator -> .\setup_scheduler.ps1

$taskName = "AI Video Factory Scheduler"
$batPath = "C:\Users\PenuelM\Documents\ai-video-factory\run_scheduler.bat"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create a new scheduled task that runs on logon
$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory "C:\Users\PenuelM\Documents\ai-video-factory"
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "AI Video Factory: BUILD at 6AM/12PM/6PM -> UPLOAD at 8AM/2PM/8PM" -RunLevel Highest

Write-Host ""
Write-Host "Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host "The scheduler will start automatically when you log in."
Write-Host ""
Write-Host "Two-Phase Schedule (Build 2h before Upload):" -ForegroundColor Cyan
Write-Host "  6:00 AM BUILD shorts    -> 8:00 AM UPLOAD shorts"
Write-Host "  12:00 PM BUILD podcasts -> 2:00 PM UPLOAD podcasts"
Write-Host "  6:00 PM BUILD long-form -> 8:00 PM UPLOAD long-form"
Write-Host ""
Write-Host "Commands:"
Write-Host "  python scheduler.py --status   # Check today's status"
Write-Host "  python scheduler.py --once     # Run full build+upload now"
Write-Host "  python scheduler.py --build    # Build all videos (no upload)"
Write-Host "  python scheduler.py --upload   # Upload pre-built videos"
