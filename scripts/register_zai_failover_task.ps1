# Registers the Z.AI dual-key failover scheduled task (user scope, no admin).
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\Users\Prekzursil\.agents\scripts\zai_key_failover.py"
$morning = New-ScheduledTaskTrigger -Daily -At "09:00"
$evening = New-ScheduledTaskTrigger -Daily -At "21:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "ZAI-Key-Failover" -Action $action -Trigger $morning, $evening -Settings $settings -Description "Z.AI coding-plan dual-key failover: probe both plan keys twice daily; flip ZAI_API_KEY if the active one is exhausted (selection only, never regeneration)" -Force | Out-Null
Get-ScheduledTask -TaskName "ZAI-Key-Failover" | Select-Object TaskName, State
