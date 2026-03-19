$t = Get-ScheduledTask -TaskName "AI Video Factory Scheduler"
Write-Host "State: $($t.State)"
Write-Host "Triggers: $($t.Triggers.Count)"
foreach($tr in $t.Triggers) {
    Write-Host "  - $($tr.CimClass.CimClassName) At: $($tr.StartBoundary)"
}
Write-Host "ExecutionTimeLimit: $($t.Settings.ExecutionTimeLimit)"
Write-Host "RestartCount: $($t.Settings.RestartCount)"
