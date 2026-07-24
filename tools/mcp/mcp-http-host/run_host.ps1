<#
.SYNOPSIS
  SUPERVISE a shared stdio->HTTP MCP bridge so every Claude / Codex session dials
  the ONE running instance over HTTP instead of each spawning its own stdio copy.

.DESCRIPTION
  The commodity stdio->HTTP TRANSPORT is now the `mcp-proxy` npm package (proven
  on this box to front the estate's `cmd /c npx` stdio servers: a full MCP
  initialize + tools/list handshake succeeds through it). This script is the
  SUPERVISION layer around that transport - the part #159 contributes and
  mcp-proxy does not: port-scoped children-first orphan reaping, a spawn-count
  invariant + health probe, an always-on logon Scheduled Task, and a dry-run
  argv preview.

  Two bridge modes:
    -Bridge mcp-proxy   (DEFAULT) drive `mcp-proxy` via npx.cmd, with a PINNED
                        `--host 127.0.0.1` (mcp-proxy defaults to `::`/IPv6, which
                        refuses 127.0.0.1) and `--shell` (so a `cmd /c npx` child
                        server spawns correctly). Pass the wrapped stdio server as
                        -ChildCommand 'cmd /c npx -y <server>'.
    -Bridge stdlib      Fallback with NO Node dependency: launch the in-repo
                        mcp_http_host.py UNCHANGED, wrapping tools/mcp/<Server>/hub.py.

.EXAMPLE
  # default: front a cmd/c-npx stdio server through mcp-proxy on :8900
  .\run_host.ps1 -Port 8900 -ChildCommand 'cmd /c npx -y @modelcontextprotocol/server-everything'

.EXAMPLE
  # no-Node fallback: the stdlib host wrapping a hub
  .\run_host.ps1 -Bridge stdlib -Server search-hub -Port 8900

.EXAMPLE
  .\run_host.ps1 -Port 8900 -ChildCommand 'cmd /c npx -y <server>' -DryRun   # print argv, launch nothing
  .\run_host.ps1 -Port 8900 -Status                                          # spawn-count invariant + health
  .\run_host.ps1 -Port 8900 -ChildCommand 'cmd /c npx -y <server>' -InstallTask   # always-on logon task
  .\run_host.ps1 -Port 8900 -UninstallTask                                   # remove task + reap the port tree

.NOTES
  ALWAYS-ON: -InstallTask registers a per-user logon Scheduled Task
  "McpHttpHost-<Port>", mirroring the proven MCPAgentMailSupervisor pattern
  (runs hidden at logon, no time limit, restart-on-failure, LIMITED run level).
  After the bridge is up, register the endpoint (Claude CLOSED) with
  apply_registration.py (--transport http for /mcp, --transport sse for /sse) and
  restart. Binds 127.0.0.1 only.
#>
[CmdletBinding()]
param(
    [ValidateSet('mcp-proxy', 'stdlib')][string]$Bridge = 'mcp-proxy',
    [int]$Port = 8900,
    [string]$BindAddress = '127.0.0.1',

    # -- mcp-proxy mode --
    [string]$ChildCommand = '',
    [string]$ProxyPackage = 'mcp-proxy@6.5.4',

    # -- stdlib mode --
    [string]$Server = '',
    [string]$Python = 'C:\Python314\python.exe',
    [string]$Repo = "$HOME\source\agent-skills-toolchain",

    # -- actions --
    [switch]$Status,
    [switch]$InstallTask,
    [switch]$UninstallTask,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "McpHttpHost-$Port"   # port-unique: one supervisor task per bridge port

# --------------------------------------------------------------- port scoping
# Every reap/status query is PORT-SCOPED - it only ever touches the process(es)
# that own the target port and their descendants, NEVER machine-wide.

function Get-PortOwnerPids {
    param([int]$TargetPort)
    try {
        $conns = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction Stop
        return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        return @()   # Get-NetTCPConnection throws when nothing is listening
    }
}

function Get-ChildPids {
    param([int]$ParentId)
    return @(
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty ProcessId
    )
}

function Stop-ProcessTree {
    # Children FIRST (depth-first), so a parent never re-parents or respawns a
    # child mid-reap; then the root. Scoped to the tree rooted at $RootId.
    param([int]$RootId, [switch]$Preview)
    foreach ($childId in (Get-ChildPids -ParentId $RootId)) {
        Stop-ProcessTree -RootId $childId -Preview:$Preview
    }
    if ($Preview) { Write-Host "  would reap pid $RootId"; return }
    try {
        Stop-Process -Id $RootId -Force -ErrorAction Stop
        Write-Host "  reaped pid $RootId"
    } catch {
        Write-Warning "  could not reap pid $RootId : $($_.Exception.Message)"
    }
}

function Invoke-PortReap {
    param([int]$TargetPort, [switch]$Preview)
    $owners = Get-PortOwnerPids -TargetPort $TargetPort
    if (-not $owners) { Write-Host "reap: no process owns port $TargetPort (nothing to reap)"; return }
    Write-Host "reap: port $TargetPort owned by pid(s) $($owners -join ', ') - children-first, port-scoped"
    foreach ($ownerId in $owners) { Stop-ProcessTree -RootId $ownerId -Preview:$Preview }
}

# --------------------------------------------------------------- status probe
function Get-BridgeStatus {
    param([int]$TargetPort, [string]$Addr)
    $owners = @(Get-PortOwnerPids -TargetPort $TargetPort)
    $listeners = $owners.Count
    Write-Host "bridge status (port $TargetPort, mode $Bridge):"
    Write-Host "  listeners       : $listeners owner pid(s) [$($owners -join ', ')]"
    # spawn-count invariant: exactly ONE shared bridge process should own the port
    # (that is the whole point - S per-session copies collapse to 1).
    if ($listeners -eq 0) {
        Write-Host "  spawn-invariant : DOWN (0 owners; expected 1 when running)"
    } elseif ($listeners -eq 1) {
        Write-Host "  spawn-invariant : OK (1 shared bridge owns the port)"
    } else {
        Write-Warning "  spawn-invariant : VIOLATED ($listeners owners; expected 1) - reap with -UninstallTask"
    }
    # health: the stdlib host serves /healthz with the load-bearing child_spawn_count;
    # mcp-proxy has no /healthz, so the port-owner check above is authoritative there.
    try {
        $h = Invoke-RestMethod -Uri "http://${Addr}:${TargetPort}/healthz" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "  /healthz        : child_pid=$($h.child_pid) child_spawn_count=$($h.child_spawn_count) requests_served=$($h.requests_served)"
    } catch {
        Write-Host "  /healthz        : (none - mcp-proxy has no health endpoint; use the listener check)"
    }
    return $listeners
}

# --------------------------------------------------------------- argv builder
function Resolve-Argv {
    # Pure string assembly - NO filesystem/launch side effects, so -DryRun can
    # always print. Returns @{ Exe; Args; Label }.
    if ($Bridge -eq 'mcp-proxy') {
        if (-not $ChildCommand) { throw "mcp-proxy mode needs -ChildCommand (e.g. 'cmd /c npx -y <server>')" }
        $npx = Get-Command npx.cmd -ErrorAction SilentlyContinue
        $npxExe = if ($npx) { $npx.Source } else { 'npx.cmd' }
        $childTokens = $ChildCommand -split '\s+' | Where-Object { $_ -ne '' }
        # PIN --host (mcp-proxy default is '::' / IPv6, which refuses 127.0.0.1) and
        # --shell (cmd/c npx child). Wrapped stdio server follows the '--' separator.
        $argv = @('-y', $ProxyPackage, '--host', $BindAddress, '--port', "$Port", '--shell', '--') + $childTokens
        return @{ Exe = $npxExe; Args = $argv; Label = "mcp-proxy front of [$ChildCommand]" }
    }
    if (-not $Server) { throw "stdlib mode needs -Server (the hub under tools/mcp/<Server>/hub.py)" }
    $hostScript = Join-Path $here 'mcp_http_host.py'
    $hub = Join-Path $Repo "tools\mcp\$Server\hub.py"
    $argv = @($hostScript, '--eager', '--host', $BindAddress, '--port', "$Port", '--', $Python, $hub)
    return @{ Exe = $Python; Args = $argv; Label = "stdlib mcp_http_host wrapping $Server" }
}

# --------------------------------------------------------------- scheduled task
function Install-Task {
    $psExe = (Get-Command powershell.exe).Source
    $self = $MyInvocation.MyCommand.Path
    if (-not $self) { $self = Join-Path $here 'run_host.ps1' }
    # Re-invoke THIS script at logon with the same mode args (minus -InstallTask).
    $mode = "-Bridge $Bridge -Port $Port -BindAddress $BindAddress"
    if ($Bridge -eq 'mcp-proxy') {
        $mode += " -ChildCommand `"$ChildCommand`" -ProxyPackage $ProxyPackage"
    } else {
        $mode += " -Server $Server -Python `"$Python`" -Repo `"$Repo`""
    }
    $actArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$self`" $mode"
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $actArgs
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal `
        -Description "Always-on shared MCP bridge supervisor ($Bridge) on port $Port." | Out-Null
    Write-Host "Registered scheduled task '$TaskName' (runs this bridge hidden at logon)."
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started task '$TaskName' now."
}

function Uninstall-Task {
    # ORDER: remove the task (kills its supervised child) BEFORE reaping, so the
    # task cannot immediately restart what we are about to reap.
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task '$TaskName' found."
    }
    Invoke-PortReap -TargetPort $Port
}

# --------------------------------------------------------------- dispatch
if ($UninstallTask) { Uninstall-Task; return }
if ($Status) { Get-BridgeStatus -TargetPort $Port -Addr $BindAddress | Out-Null; return }

$resolved = Resolve-Argv   # throws early if the chosen mode is missing its inputs

if ($DryRun) {
    Write-Host "DRY-RUN ($($resolved.Label)):"
    Write-Host "  $($resolved.Exe) $($resolved.Args -join ' ')"
    return
}

if ($InstallTask) { Install-Task; return }

# --- launch (foreground) after a pre-launch port-scoped reap of any stale owner ---
if ($Bridge -eq 'stdlib') {
    if (-not (Test-Path $Python)) { throw "python not found: $Python" }
    $hub = Join-Path $Repo "tools\mcp\$Server\hub.py"
    if (-not (Test-Path $hub)) { throw "hub not found: $hub (is -Server correct?)" }
}
Invoke-PortReap -TargetPort $Port
Write-Host "mcp-http-host supervisor: $($resolved.Label) -> http://${BindAddress}:${Port} (health /healthz where served)"
& $resolved.Exe @($resolved.Args)
