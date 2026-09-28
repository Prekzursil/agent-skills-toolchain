$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "' + "$HOME\.local\bin\zai-bridge-guard.ps1" + '"')
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'ZaiBridgeGuard' -Action $a -Trigger $t -Settings $s -Force | Out-Null
"SUCCESS:zai-guard state=$((Get-ScheduledTask -TaskName ZaiBridgeGuard).State)"
