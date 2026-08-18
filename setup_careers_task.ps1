# Run this ONCE as Administrator (right-click > Run with PowerShell as admin).
# Creates the Mzansi Careers daily poster and the PM2 bots resurrect task
# with the same "runs whenever the PC is up" settings as every other task:
# starts on battery, never stops when unplugged, and catches up missed runs.
$root = "C:\Users\PenuelM\Documents\ai-video-factory"
$vbs = "$root\run_hidden.vbs"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "PenuelM" -LogonType Interactive

# ── Mzansi Careers — one verified opportunity every weekday morning ──
$act = New-ScheduledTaskAction -Execute "wscript.exe" `
    -Argument "`"$vbs`" `"$root\run_careers_daily.bat`""
$trg = New-ScheduledTaskTrigger -Daily -At 7:30AM
Register-ScheduledTask -TaskName "Mzansi Careers Daily" -Action $act `
    -Trigger $trg -Settings $settings -Principal $principal -Force

# ── PM2 bots back up after a reboot ──
$act2 = New-ScheduledTaskAction -Execute "wscript.exe" `
    -Argument "`"$vbs`" `"$root\run_pm2_resurrect.bat`""
$t1 = New-ScheduledTaskTrigger -AtLogOn
$t1.Delay = "PT90S"
$t2 = New-ScheduledTaskTrigger -Daily -At 6:15AM
Register-ScheduledTask -TaskName "Genesis Bots Resurrect" -Action $act2 `
    -Trigger $t1, $t2 -Settings $settings -Principal $principal -Force

# ── The two tasks that run elevated and could not be updated without admin ──
foreach ($n in @("AI Video Factory Scheduler", "Genesis Content Engine")) {
    try {
        Set-ScheduledTask -TaskName $n -Settings $settings -ErrorAction Stop |
            Out-Null
        Write-Host "OK   $n"
    } catch { Write-Host "SKIP $n :: $($_.Exception.Message)" }
}

Get-ScheduledTask -TaskName "Mzansi Careers Daily", "Genesis Bots Resurrect" |
    Select-Object TaskName, State
