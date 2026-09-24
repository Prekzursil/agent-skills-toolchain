<#
  Make the home side of the VM/home link survive sleep, reboot and logout.

  TWO LAYERS, BOTH REAL. Diagnose in this order:

    1. TAILSCALE reachability - if the node is offline, nothing else matters.
       Verified 2026-09-24: home showed "offline, last seen 2h" from the VM while
       rclone WAS listening locally on the desktop. A listening port is useless
       if the tailnet is down. This layer is checked first.
    2. RCLONE SERVE persistence - HOME-SETUP.md step 4 originally told you to run
       `rclone serve sftp` in a FOREGROUND shell, which dies with the shell, the
       session or the machine.

  COLLISION SAFETY. A session running on the desktop already installed a logon
  task named `home-link-serve` pointing at %LOCALAPPDATA%\rclone\home-link-serve.cmd,
  plus a Startup-folder copy. Both that task and this one bind 100.97.16.36:2022
  and :2023. Installing a SECOND pair means the loser fails to bind and you get a
  task that looks registered but never listens - worse than either alone.

  So this script ADOPTS an existing install rather than competing with it:
  it upgrades the task already present (adding a boot trigger, auto-restart and
  self-verification) instead of registering a rival.

  Run ONCE on home, in an ELEVATED PowerShell 7:
      pwsh -File C:\ProgramData\vm-link\install-home-service.ps1

  Idempotent. Re-running is safe.
      -Uninstall   remove whichever task this script manages
      -WhatIf      report what it would do, change nothing
#>
[CmdletBinding(SupportsShouldProcess)]
param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'

$Preferred = 'vm-link-serve-home'                                  # this script's name
$Existing  = 'home-link-serve'                                     # the desktop session's name
$MyCmd     = 'C:\ProgramData\vm-link\home-serve.cmd'
$TheirCmd  = Join-Path $env:LOCALAPPDATA 'rclone\home-link-serve.cmd'
$StartupLnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'home-link-serve.cmd'

function Get-ManagedTask {
    foreach ($n in @($Existing, $Preferred)) {
        $t = Get-ScheduledTask -TaskName $n -EA SilentlyContinue
        if ($t) { return $t }
    }
    return $null
}

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    $t = Get-ManagedTask
    if ($t) {
        if ($PSCmdlet.ShouldProcess($t.TaskName, 'Unregister-ScheduledTask')) {
            Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false
            Write-Host "SUCCESS:uninstalled $($t.TaskName)"
        }
    } else { Write-Host 'NOT-PRESENT: no managed task found' }
    if (Test-Path $StartupLnk) {
        Write-Host "  NOTE: a Startup-folder copy remains at $StartupLnk - remove it by hand if you want the link fully off."
    }
    return
}

# ------------------------------------------------- LAYER 1: tailscale first
Write-Host 'LAYER 1 - tailnet reachability'
$tsSvc = Get-Service -Name Tailscale -EA SilentlyContinue
if (-not $tsSvc) {
    Write-Warning '  Tailscale service not found. The link cannot work without it. Install Tailscale first.'
} else {
    Write-Host ("  service : {0} / startup {1}" -f $tsSvc.Status, (Get-CimInstance Win32_Service -Filter "Name='Tailscale'").StartMode)
    if ($tsSvc.Status -ne 'Running') {
        if ($PSCmdlet.ShouldProcess('Tailscale', 'Start-Service')) { Start-Service Tailscale; Write-Host '  started' }
    }
    $mode = (Get-CimInstance Win32_Service -Filter "Name='Tailscale'").StartMode
    if ($mode -ne 'Auto') {
        if ($PSCmdlet.ShouldProcess('Tailscale', 'Set startup to Automatic')) {
            Set-Service -Name Tailscale -StartupType Automatic
            Write-Host '  startup set to Automatic (was ' + $mode + ')'
        }
    }
    # Sleep is the usual reason a desktop vanishes from the tailnet.
    $sleepAc = (powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>$null | Select-String 'Current AC Power Setting Index').ToString()
    if ($sleepAc -and $sleepAc -notmatch '0x00000000') {
        Write-Warning '  This machine is configured to SLEEP on AC power. It will drop off the tailnet every time.'
        Write-Warning '  To keep the link alive:  powercfg /change standby-timeout-ac 0'
    }
}

# --------------------------------------------- LAYER 2: rclone persistence
Write-Host 'LAYER 2 - rclone serve persistence'
$task = Get-ManagedTask
$cmd  = $null

if ($task -and $task.TaskName -eq $Existing) {
    $cmd = ($task.Actions | Select-Object -First 1).Execute
    Write-Host "  ADOPTING the existing task '$Existing' -> $cmd"
    Write-Host '  (not registering a rival; both would bind :2022/:2023 and one would silently lose)'
} elseif (Test-Path $MyCmd) {
    $cmd = $MyCmd
    Write-Host "  installing fresh as '$Preferred' -> $cmd"
} elseif (Test-Path $TheirCmd) {
    $cmd = $TheirCmd
    Write-Host "  no task yet, but found the desktop session's script -> $cmd"
} else {
    throw "FAILED:install - no serve script found at $MyCmd or $TheirCmd"
}

$name = if ($task) { $task.TaskName } else { $Preferred }

if (-not (Test-Path "$env:USERPROFILE\.ssh\authorized_keys")) {
    Write-Warning "  no ~\.ssh\authorized_keys - the VM will not be able to authenticate"
}

# Boot AND logon. The desktop session's install was logon-only, so an unattended
# reboot left the link down until someone signed in.
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$action    = New-ScheduledTaskAction -Execute $cmd
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

if ($PSCmdlet.ShouldProcess($name, 'Register-ScheduledTask (boot + logon, auto-restart)')) {
    Register-ScheduledTask -TaskName $name -Trigger $triggers -Action $action `
        -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    Start-Sleep -Seconds 3
}

# A Startup-folder copy alongside the task is a second launcher racing for the
# same ports. Flag it; do not delete someone else's file silently.
if (Test-Path $StartupLnk) {
    Write-Warning "  A Startup-folder copy also exists: $StartupLnk"
    Write-Warning '  With the task registered this is redundant and races it for :2022/:2023.'
    Write-Warning '  Recommend removing it so there is exactly ONE launcher.'
}

# ------------------------------------------------------------- self-verify
$t = Get-ScheduledTask -TaskName $name -EA SilentlyContinue
$ports = @(Get-NetTCPConnection -State Listen -LocalPort 2022,2023 -EA SilentlyContinue |
           Select-Object -ExpandProperty LocalPort -Unique)
$rclone = @(Get-Process rclone -EA SilentlyContinue).Count

Write-Host ''
Write-Host ("  task            : {0} [{1}]" -f $name, $t.State)
Write-Host ("  ports listening : {0} of 2 ({1})" -f $ports.Count, ($ports -join ', '))
Write-Host ("  rclone procs    : {0}" -f $rclone)
Write-Host ("  tailnet         : {0}" -f (& 'C:\Program Files\Tailscale\tailscale.exe' status --self=true --peers=false 2>$null | Select-Object -First 1))

if ($ports.Count -ge 2) {
    Write-Host 'SUCCESS:home-link-persistent'
    Write-Host 'NOTE: listening locally is NOT proof the VM can reach you. The VM must see'
    Write-Host '      this node as online in `tailscale status`. If it reports "offline,'
    Write-Host '      last seen ...", this machine is asleep or Tailscale is down - layer 1.'
} else {
    Write-Host 'FAILED:home-link - task registered but ports are not listening.'
    Write-Host '      Check the rclone log the serve script writes to.'
}
