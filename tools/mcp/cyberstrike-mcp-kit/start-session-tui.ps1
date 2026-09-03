#Requires -Version 5.1
# Resume one session. Do NOT put --prompt on argv (it gets glued onto -s).
$ErrorActionPreference = 'Stop'
$Launch = 'D:\opt\cyberstrike-mcp\cyberstrike-launch.ps1'
$Inject = 'D:\opt\cyberstrike-mcp\inject-cyberstrike-prompt.ps1'
$Session = 'ses_f9c9ab90cffetNo68ohzF6RZAq'
Write-Host "G-8 A resume session=$Session (prompt via API after :4096)"
Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList @('-NoProfile','-File',$Inject) -WindowStyle Hidden
& $Launch @('-s', $Session)
exit $LASTEXITCODE
