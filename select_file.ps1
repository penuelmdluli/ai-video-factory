# Wait for the Open dialog to appear and type the file path
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic

$maxWait = 15
$waited = 0

while ($waited -lt $maxWait) {
    Start-Sleep -Milliseconds 500
    $waited += 0.5
    
    # Look for the Open dialog window
    $shell = New-Object -ComObject WScript.Shell
    $openDialog = Get-Process | Where-Object { $_.MainWindowTitle -match "Open|Choose|Select" }
    
    if ($openDialog) {
        Write-Host "Found dialog: $($openDialog.MainWindowTitle)"
        Start-Sleep -Milliseconds 500
        
        # Activate the dialog
        $shell.AppActivate($openDialog.Id)
        Start-Sleep -Milliseconds 300
        
        # Type the file path
        [System.Windows.Forms.SendKeys]::SendWait("C:\Users\PenuelM\Documents\ai-video-factory\output\ai_trading_podcast_20260311_162112\final_podcast.mp4")
        Start-Sleep -Milliseconds 300
        
        # Press Enter
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
        Write-Host "File path sent!"
        exit 0
    }
}

Write-Host "No dialog found after ${maxWait}s"
exit 1
