Add-Type -AssemblyName System.Windows.Forms

# Check for any Open/file dialog
$procs = Get-Process | Where-Object { $_.MainWindowTitle -match 'Open|Choose|Select|Upload|file' }
if ($procs) {
    Write-Host "FOUND DIALOGS:"
    $procs | ForEach-Object { Write-Host "  PID=$($_.Id) Title='$($_.MainWindowTitle)'" }
} else {
    Write-Host "No file dialog found"
}

# List all windows with titles
Write-Host "---All visible windows---"
Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | ForEach-Object {
    Write-Host "  $($_.Id): $($_.MainWindowTitle)"
}
