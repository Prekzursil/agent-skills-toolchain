<#
  Make the home side of the VM<->home link survive sleep, reboot and logout.

  WHY THIS EXISTS: HOME-SETUP.md originally told you to run `rclone serve sftp`
  in a foreground shell. That process dies with the shell, the session, or the
  machine, which is why the link kept dropping (open loop L-14). The VM side has
  had a boot-triggered task (`vm-link-serve`) all along; this gives home the same.

  Run ONCE on home, in an ELEVATED PowerShell 7:
      pwsh -File C:\ProgramData\vm-link\install-home-service.ps1

  Idempotent: re-running replaces the task rather than duplicating it.
  Uninstall:  Unregister-ScheduledTask -TaskName vm-link-serve-home -Confirm:$false
#>
[CmdletBinding()]
param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
$TaskName = 'vm-link-serve-home'
$Cmd      = 'C:\ProgramData\vm-link\home-serve.cmd'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -EA SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "SUCCESS:uninstalled $TaskName"
    } else { Write-Host "NOT-PRESENT: $TaskName" }
    return
}

if (-not (Test-Path $Cmd)) { throw "FAILED:install - missing $Cmd" }
if (-not (Test-Path "$env:USERPROFILE\.ssh\authorized_keys")) {
    Write-Warning "no ~\.ssh\authorized_keys - the VM will not be able to authenticate"
}

# Boot trigger + logon trigger: covers cold start AND the sleep/resume case where
# the service comes back before the network does.
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$action    = New-ScheduledTaskAction -Execute $Cmd
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Trigger $triggers -Action $action `
    -Principal $principal -Settings $settings -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3

$t = Get-ScheduledTask -TaskName $TaskName
$listening = @(Get-NetTCPConnection -State Listen -LocalPort 2022,2023 -EA SilentlyContinue).Count
Write-Host ("  task state      : {0}" -f $t.State)
Write-Host ("  ports listening : {0} of 2 (2022, 2023)" -f $listening)
if ($listening -ge 2) { Write-Host 'SUCCESS:home-link-persistent' }
else { Write-Host 'FAILED:home-link - task registered but ports are not listening; check serve-c.log / serve-d.log' }
