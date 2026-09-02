# Install a logon/daily reapply of phone ChatGPT cookies into the durable Chrome profile.
# Does NOT re-extract from phone (that needs ADB). Re-applies the last saved store.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\crcp\scripts\install_phone_cookie_reapply_task.ps1
#   powershell ... -File ... -Uninstall

param(
  [switch]$Uninstall,
  [string]$TaskName = "CRCPPhoneCookieReapply",
  [ValidateSet("Logon", "Daily")][string]$Trigger = "Logon"
)

$ErrorActionPreference = "Stop"
$python = (Get-Command python -ErrorAction Stop).Source
$apply = Join-Path $env:USERPROFILE ".crcp\cookie-bridge\apply_durable.py"
if (-not (Test-Path $apply)) {
  throw "Missing $apply - extract phone cookies first"
}

if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed task $TaskName"
  exit 0
}

$arg = "`"$apply`" apply --browser chrome --port 9340"
$action = New-ScheduledTaskAction -Execute $python -Argument $arg -WorkingDirectory (Split-Path $apply)
if ($Trigger -eq "Daily") {
  $trig = New-ScheduledTaskTrigger -Daily -At 9am
} else {
  $trig = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trig -Settings $settings -Force | Out-Null
Write-Host "Installed $TaskName ($Trigger) -> python apply_durable.py apply"
Write-Host "Note: cookies expire; re-run phone extract when WEB_SESSION fails."
