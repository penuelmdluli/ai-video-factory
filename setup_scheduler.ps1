# AI Video Factory — Robust Scheduler Setup
# Run as Administrator: powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1

$taskName = "AI Video Factory Scheduler"
$batPath = "C:\Users\PenuelM\Documents\ai-video-factory\run_scheduler.bat"
$workDir = "C:\Users\PenuelM\Documents\ai-video-factory"

# Remove old task if exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed old task (if any)"

# Action: run the batch file
$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $workDir

# Trigger 1: At logon (backup)
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn

# Trigger 2: Daily at 4:30 AM (ensures scheduler is alive before 5 AM build)
$triggerDaily = New-ScheduledTaskTrigger -Daily -At "4:30AM"

# Settings:
# - No execution time limit (was 72h which killed the daemon!)
# - Restart on failure: 5 retries, 5 min apart
# - Start even if missed (StartWhenAvailable)
# - Run on battery
# - Don't create new instance if already running
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -MultipleInstances IgnoreNew

$description = "AI Video Factory scheduler daemon. Builds videos 3h before upload (5AM/11AM/5PM build -> 8AM/2PM/8PM upload). Engagement posts at 9AM/12PM/3PM/6PM/9PM. All 9 niches."

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $triggerLogon, $triggerDaily `
    -Settings $settings `
    -Description $description `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "=== Task Registered ===" -ForegroundColor Green
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
Get-ScheduledTask -TaskName $taskName | Select-Object -ExpandProperty Triggers | Format-Table Enabled, @{N="Type";E={$_.CimClass.CimClassName}}, @{N="At";E={$_.StartBoundary}} -AutoSize

# Start it now
Start-ScheduledTask -TaskName $taskName
Write-Host "Scheduler started!" -ForegroundColor Green

Write-Host ""
Write-Host "Two-Phase Schedule (Build 3h before Upload):" -ForegroundColor Cyan
Write-Host "  5:00 AM BUILD shorts    -> 8:00 AM UPLOAD shorts"
Write-Host "  11:00 AM BUILD podcasts -> 2:00 PM UPLOAD podcasts"
Write-Host "  5:00 PM BUILD long-form -> 8:00 PM UPLOAD long-form"
Write-Host ""
Write-Host "Engagement Posts: 9AM / 12PM / 3PM / 6PM / 9PM" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:"
Write-Host "  python scheduler.py --status   # Check today's status"
Write-Host "  python scheduler.py --once     # Run full build+upload now"
Write-Host "  python scheduler.py --build    # Build all videos (no upload)"
Write-Host "  python scheduler.py --upload   # Upload pre-built videos"
Write-Host "  python scheduler.py --engagement # Run engagement posts now"
