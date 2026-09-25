<#
  Install / relocate a self-hosted GitHub Actions runner for
  Prekzursil/agent-skills-toolchain, boot-persistent, with NO credential on disk.

  WHY THIS EXISTS: the repo's gated jobs ask for
      runs-on: ${{ ... fromJson('["self-hosted", "linux"]') || 'ubuntu-latest' }}
  and `vars.QUALITY_RUNNER` is already 'self-hosted'. The label set is LINUX, so a
  native Windows runner can never match those jobs -- it would queue forever. This
  script therefore runs the runner inside WSL2 and refuses to proceed without it,
  rather than silently installing a Linux kernel on a disk that may not have room.

  It also defaults to an EPHEMERAL runner. That is the fix for the ghost-runner
  failure measured on 2026-09-24: home slept, GitHub still reported the runner
  'online busy=true', and 14 jobs queued behind it for up to 19.5 hours. An
  ephemeral runner takes one job then deregisters, so a machine that sleeps leaves
  no phantom for GitHub to assign work to.

  Persistence mirrors platform/vm-link/install-home-service.ps1: a Scheduled Task
  with -AtStartup AND -AtLogOn, StartWhenAvailable, RestartCount 999, no execution
  time limit, registered with -Force so re-running replaces rather than duplicates.
  A Scheduled Task is used instead of WSL systemd because systemd is not guaranteed
  enabled in the distro; the task works either way.

  CREDENTIALS: -RegistrationToken is a required runtime parameter. It is never
  defaulted, never written to disk, and is scrubbed from memory on exit. Tokens are
  short-lived (~1h) by design. Re-registration for ephemeral mode uses -TokenCommand,
  which defaults to a `gh api` call relying on AMBIENT gh auth -- so no secret is
  stored by this script either. This script never rotates, revokes or regenerates
  any credential.

  USAGE
    # short-lived registration token (never stored):
    gh api -X POST /repos/Prekzursil/agent-skills-toolchain/actions/runners/registration-token --jq .token

    pwsh -File install-runner.ps1 -RegistrationToken '<paste>'
    pwsh -File install-runner.ps1 -Status
    pwsh -File install-runner.ps1 -Uninstall -RemovalToken '<paste>'
        # removal token: gh api -X POST .../actions/runners/remove-token --jq .token
#>
[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install', Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$RegistrationToken,

    [Parameter(ParameterSetName = 'Uninstall', Mandatory = $true)]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = 'Uninstall')]
    [string]$RemovalToken,

    [Parameter(ParameterSetName = 'Status', Mandatory = $true)]
    [switch]$Status,

    [string]$RepoUrl      = 'https://github.com/Prekzursil/agent-skills-toolchain',
    [string]$Distro       = '',
    [string]$RunnerName   = "$env:COMPUTERNAME-wsl".ToLower(),
    [string]$Labels       = 'self-hosted,linux,x64',
    [string]$RunnerVersion= '2.328.0',
    [string]$LinuxHome    = '$HOME/actions-runner',
    [bool]  $Ephemeral    = $true,
    [string]$TokenCommand = '',
    [int]   $MinFreeGB    = 12
)

$ErrorActionPreference = 'Stop'
$TaskName  = 'gh-actions-runner'
$StateDir  = Join-Path $env:ProgramData 'gh-actions-runner'
$Wrapper   = Join-Path $StateDir 'run-runner.cmd'
$LoopSh    = Join-Path $StateDir 'runner-loop.sh'

function Ok   ($m) { Write-Host "SUCCESS:$m" }
function Die  ($m) { Write-Host "FAILED:$m";  exit 1 }
function Info ($m) { Write-Host "  $m" }

# ---------------------------------------------------------------- preflight ----
function Get-Distro {
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) { Die 'preflight - wsl.exe not found. The gated jobs require the "linux" label; a native Windows runner cannot match them.' }

    # wsl.exe emits UTF-16LE; normalise before parsing.
    $raw = (& wsl.exe -l -q 2>&1 | Out-String) -replace "`0", ''
    if ($raw -match 'not installed|no installed distributions') {
        Die 'preflight - WSL has no installed distribution. Install one first (this script deliberately does NOT), then re-run.'
    }
    $found = $raw -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if (-not $found) { Die 'preflight - could not enumerate WSL distributions.' }
    if ($Distro) {
        if ($found -notcontains $Distro) { Die "preflight - distro '$Distro' not present. Available: $($found -join ', ')" }
        return $Distro
    }
    return $found[0]
}

function Test-Space {
    $sys = (Get-Item $env:SystemDrive).Root.Name.TrimEnd('\')
    $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$sys'" -ErrorAction SilentlyContinue
    if ($d) {
        $free = [math]::Round($d.FreeSpace / 1GB, 1)
        Info "free on ${sys} : $free GB (need >= $MinFreeGB GB)"
        if ($free -lt $MinFreeGB) { Die "preflight - only $free GB free on $sys; the runner plus its _work tree needs headroom. Free space or pass -MinFreeGB to override deliberately." }
    }
}

# -------------------------------------------------------------------- status ----
if ($Status) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        $i = Get-ScheduledTaskInfo -TaskName $TaskName
        Info "task          : $($t.State)  lastResult=$($i.LastTaskResult)  lastRun=$($i.LastRunTime)"
    } else { Info 'task          : NOT REGISTERED' }
    Info "state dir     : $(if (Test-Path $StateDir) { $StateDir } else { 'absent' })"
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        Info 'registered runners (GitHub side):'
        & gh api "$($RepoUrl -replace 'https://github.com/','/repos/')/actions/runners" `
            --jq '.runners[] | "    \(.name) status=\(.status) busy=\(.busy) labels=\([.labels[].name]|join(","))"' 2>&1 |
            ForEach-Object { Write-Host $_ }
        Write-Host ''
        Write-Host '  NOTE: a runner reporting online+busy while its host is unreachable is a GHOST.'
        Write-Host '        Clear it with: gh api -X DELETE <repo>/actions/runners/<id>'
    } else { Info 'gh not on PATH - skipping GitHub-side runner list' }
    exit 0
}

# ----------------------------------------------------------------- uninstall ----
if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask   -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Info "unregistered task $TaskName"
    } else { Info "task $TaskName not present" }

    if ($RemovalToken) {
        $d = Get-Distro
        $rm = "cd $LinuxHome 2>/dev/null && ./config.sh remove --token '$RemovalToken' || echo 'config.sh remove skipped'"
        & wsl.exe -d $d -- bash -lc $rm 2>&1 | ForEach-Object { Info $_ }
        $RemovalToken = $null
    } else {
        Info 'no -RemovalToken given; GitHub-side registration left in place.'
        Info 'get one: gh api -X POST <repo>/actions/runners/remove-token --jq .token'
    }
    Ok 'runner-uninstalled'
    exit 0
}

# ------------------------------------------------------------------- install ----
Info "repo          : $RepoUrl"
Info "runner name   : $RunnerName"
Info "labels        : $Labels"
Info "ephemeral     : $Ephemeral"

$d = Get-Distro
Info "wsl distro    : $d"
Test-Space

# Ephemeral runners deregister after one job, so the loop needs a FRESH registration
# token each pass. Default to ambient `gh` auth rather than storing anything.
if ($Ephemeral -and -not $TokenCommand) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Die 'ephemeral mode needs a way to mint fresh registration tokens. Either install/authenticate gh, pass -TokenCommand, or use -Ephemeral $false.'
    }
    $apiPath = ($RepoUrl -replace 'https://github.com/', '/repos/') + '/actions/runners/registration-token'
    $TokenCommand = "gh api -X POST $apiPath --jq .token"
    Info "token command : $TokenCommand   (ambient gh auth; nothing stored)"
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# --- stage the runner inside WSL (idempotent: skips download if config.sh exists)
$arch = 'x64'
$tarball = "actions-runner-linux-$arch-$RunnerVersion.tar.gz"
$url = "https://github.com/actions/runner/releases/download/v$RunnerVersion/$tarball"

$stage = @"
set -euo pipefail
mkdir -p $LinuxHome && cd $LinuxHome
if [ ! -f ./config.sh ]; then
  echo "downloading $tarball"
  curl -fsSL -o "/tmp/$tarball" "$url"
  tar xzf "/tmp/$tarball" -C .
  rm -f "/tmp/$tarball"
  if [ -f ./bin/installdependencies.sh ]; then sudo ./bin/installdependencies.sh >/dev/null 2>&1 || true; fi
else
  echo "runner already staged - skipping download"
fi
"@
Info 'staging runner in WSL...'
& wsl.exe -d $d -- bash -lc $stage 2>&1 | ForEach-Object { Info $_ }
if ($LASTEXITCODE -ne 0) { Die 'install - could not stage the runner inside WSL' }

# --- first registration (token passed via env, never written to a file)
$ephFlag = if ($Ephemeral) { '--ephemeral' } else { '' }
$cfg = @"
set -euo pipefail
cd $LinuxHome
if [ -f .runner ]; then ./config.sh remove --token "`$RUNNER_TOKEN" >/dev/null 2>&1 || true; fi
./config.sh --unattended --replace $ephFlag \
  --url '$RepoUrl' --token "`$RUNNER_TOKEN" \
  --name '$RunnerName' --labels '$Labels' --work _work
"@
Info 'registering runner...'
$prev = $env:WSLENV
$env:RUNNER_TOKEN = $RegistrationToken
$env:WSLENV = if ($prev) { "$prev`:RUNNER_TOKEN" } else { 'RUNNER_TOKEN' }
try {
    & wsl.exe -d $d -- bash -lc $cfg 2>&1 | ForEach-Object { Info ($_ -replace [regex]::Escape($RegistrationToken), '***') }
    $cfgExit = $LASTEXITCODE
} finally {
    Remove-Item Env:\RUNNER_TOKEN -ErrorAction SilentlyContinue
    if ($prev) { $env:WSLENV = $prev } else { Remove-Item Env:\WSLENV -ErrorAction SilentlyContinue }
    $RegistrationToken = $null
    [System.GC]::Collect()
}
if ($cfgExit -ne 0) { Die 'install - runner registration failed (token expired? tokens last ~1h)' }

# --- supervision loop. Ephemeral: re-register each pass with a fresh token.
$loop = @"
#!/usr/bin/env bash
# Generated by install-runner.ps1 -- do not edit by hand. Contains NO credential.
set -uo pipefail
cd $LinuxHome || exit 1
while true; do
  if [ "$($Ephemeral.ToString().ToLower())" = "true" ]; then
    TOK="`$(${TokenCommand} 2>/dev/null || true)"
    if [ -n "`$TOK" ]; then
      ./config.sh remove --token "`$TOK" >/dev/null 2>&1 || true
      ./config.sh --unattended --replace --ephemeral \
        --url '$RepoUrl' --token "`$TOK" \
        --name '$RunnerName' --labels '$Labels' --work _work >/dev/null 2>&1 || true
    fi
    unset TOK
  fi
  ./run.sh
  sleep 10
done
"@
# LF endings: a CRLF .sh is silently broken under real WSL.
[IO.File]::WriteAllText($LoopSh, ($loop -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding $false))
$wslLoop = (& wsl.exe -d $d -- wslpath -a ($LoopSh -replace '\\', '/') 2>&1 | Out-String).Trim()
& wsl.exe -d $d -- bash -lc "chmod +x '$wslLoop'" 2>&1 | Out-Null

@"
@echo off
rem Generated by install-runner.ps1 -- contains NO credential.
wsl.exe -d $d -- bash -lc "'$wslLoop'"
"@ | Set-Content -Path $Wrapper -Encoding ASCII

# --- persistence: same shape as vm-link-serve-home
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$action    = New-ScheduledTaskAction -Execute $Wrapper
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Trigger $triggers -Action $action `
    -Principal $principal -Settings $settings -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8

# --- self-verify
$t = Get-ScheduledTask -TaskName $TaskName
Info "task state    : $($t.State)"
$listener = (& wsl.exe -d $d -- bash -lc "pgrep -f 'Runner.Listener|run.sh' >/dev/null && echo up || echo down" 2>&1 | Out-String).Trim()
Info "runner proc   : $listener"

if ($t.State -in @('Running','Ready') -and $listener -match 'up') {
    Ok 'runner-installed-and-persistent'
} else {
    Die "runner - task registered but the listener is not up. Inspect: wsl -d $d -- bash -lc 'cd $LinuxHome && ls -la _diag && tail -50 _diag/*.log'"
}
