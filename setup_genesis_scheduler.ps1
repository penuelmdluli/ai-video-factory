# ====================================================
#  Genesis Content Engine — Windows Task Scheduler Setup
#  Registers a scheduled task that runs the Genesis
#  Content Engine daily at 4:00 AM UTC (6:00 AM SAST)
# ====================================================

$TaskName = "Genesis Content Engine"
$WorkingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $WorkingDir "run_genesis.bat"

# Remove old task if exists
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

# Action: run the batch file
$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $WorkingDir

# Triggers: at logon + daily at 4:00 AM (UTC) = 6:00 AM SAST
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At "04:00"

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $TriggerLogon, $TriggerDaily `
    -Settings $Settings `
    -RunLevel Highest `
    -Description "Genesis Content Engine - Daily AI video content pipeline using Brain Studio"

Write-Host ""
Write-Host "=== Genesis Content Engine Task Registered ==="
Write-Host "Task Name: $TaskName"
Write-Host "Triggers: At Logon + Daily 04:00 UTC (06:00 SAST)"
Write-Host "Script: $BatPath"
Write-Host ""
Write-Host "To start now: schtasks /run /tn '$TaskName'"
Write-Host "To check: schtasks /query /tn '$TaskName'"
Write-Host ""
