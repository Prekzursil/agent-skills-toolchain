#Requires -Version 5.1
<#
  Fabric Session Distillery — nightly wrapper for the scheduled task.
  Hidden window, sequential fabric calls (T0 free OpenRouter), fail-open.
  Processes at most 40 sessions per night so the initial backlog (~373
  distill-eligible sessions) drains over ~10 nights without a multi-hour run.
#>
$ErrorActionPreference = 'Continue'
$log = "$env:USERPROFILE\.agents\logs\fabric-distillery.log"
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 400KB)) { Remove-Item $log -Force }
$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
"$stamp run start" | Out-File $log -Append -Encoding utf8
& C:\Python314\python.exe "$env:USERPROFILE\.agents\scripts\fabric_session_distillery.py" --limit 40 *>> $log
"$stamp run exit $LASTEXITCODE" | Out-File $log -Append -Encoding utf8
# keep the session catalog fresh for the next distillery pass
& C:\Python314\python.exe "$env:USERPROFILE\.agents\scripts\index-ai-sessions.py" *>> $log
