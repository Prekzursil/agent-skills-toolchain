# Reap orphaned MCP-server processes whose root agent session is dead.
# SAFE policy — a process is killed ONLY if ALL of the following hold:
#   1. its ancestry chain never reaches a live agent/TUI/terminal root
#      (see $agentRootNames + $hostRootNames) nor services.exe (real daemons),
#   2. its command line does not match the persistent-daemon whitelist
#      (mcp-hub, basic-memory, agent-mail, auth2api, actions-runner,
#       cc-gateway, socat bridges),
#   3. it is an MCP-class process (node/python/uv/uvx/npx/bun/deno),
#      or a truly-orphaned cmd.exe (parent gone AND no live children).
# NEVER a victim: conhost.exe (parent-gone != dead console - a live TUI's
# conhost whose launcher exited must survive; killing it kills the session).
# 2026-09-22 hardening after the silent-kill audit: root list extended with
# every TUI/agent this estate actually runs (zcode, opencode, gemini, grok,
# agy, goose, fabric, warp, ghostty, wezterm, alacritty, terminals, shells) —
# an unrecognized runtime is now PROTECTED by default, not reaped.
param([switch]$WhatIfOnly)

$ErrorActionPreference = 'SilentlyContinue'
$procs = Get-CimInstance Win32_Process |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine
$byPid = @{}
foreach ($p in $procs) { $byPid[[uint32]$p.ProcessId] = $p }
$livePids = $procs | ForEach-Object { [uint32]$_.ProcessId }

# Agent + TUI runtimes whose live ancestry PROTECTS everything below it.
$agentRootNames = @(
    'claude','code','cursor','codex','trae','windsurf','wedge',
    'zcode','opencode','gemini','grok','agy','goose','fabric',
    'nanoclaw','cai'
)
# Terminals and shells: a process chain that still reaches a LIVE terminal or
# interactive shell is a live session (manual MCP server, TUI child) - protect.
# Orphans stay reapable because their chain BREAKS at the dead session root.
$hostRootNames = @(
    'windowsterminal','openconsole','conhost','wezterm','alacritty','warp',
    'ghostty','tabby','hyper','putty','moba','teraterm','kitty',
    'powershell','pwsh','cmd'
)
$allRootNames = $agentRootNames + $hostRootNames

$whitelist = @('mcp-hub','basic-memory','agent-mail','auth2api',
               'actions-runner','cc-529-gateway','gateway.mjs','socat',
               '18765','18812','18317',
               'cyberstrike',  # 2026-09-22: TUI killed in 19:44-19:59 window, reaper-correlated (UNPROVEN); cockpit protected by default
               'zai-anon-mcp') # 2026-09-23: the free-GLM HTTP bridge (:18319) is a detached
                               # daemon (dead parent by design) - reaper killed it silently; whitelist

function Test-KeepAlive($proc) {
    if ($proc.CommandLine) {
        foreach ($w in $whitelist) {
            if ($proc.CommandLine -match [regex]::Escape($w)) { return 'whitelist' }
        }
    }
    $seen = @{}
    $cur = $proc
    while ($cur) {
        if ($seen[[uint32]$cur.ProcessId]) { return 'null-guard' }  # cycle -> keep (fail-safe)
        $seen[[uint32]$cur.ProcessId] = $true
        foreach ($rn in $allRootNames) {
            if ($cur.Name -and $cur.Name.ToLower().StartsWith($rn)) {
                return 'live-root' }
        }
        if ($cur.Name -eq 'services.exe') { return 'service' }
        $parentPid = [uint32]$cur.ParentProcessId
        if ($parentPid -eq 0 -or -not $byPid.ContainsKey($parentPid)) { return $null }
        $cur = $byPid[$parentPid]
    }
    return $null
}

$mcpClass = @('node.exe','python.exe','python3.exe','uv.exe','uvx.exe',
              'npx.exe','npx.cmd','bun.exe','deno.exe')

# children map: pid -> count of live children (for the cmd-zombie check)
$childCount = @{}
foreach ($p in $procs) {
    $pp = [uint32]$p.ParentProcessId
    if ($childCount.ContainsKey($pp)) { $childCount[$pp] = [int]$childCount[$pp] + 1 }
    else { $childCount[$pp] = 1 }
}

$killed = 0; $keptAgent = 0; $keptSvc = 0; $keptWl = 0
$victims = foreach ($p in $procs) {
    $n = $p.Name.ToLower()
    $isCmdZombie = ($n -eq 'cmd.exe') -and
        ($livePids -notcontains [uint32]$p.ParentProcessId) -and
        (-not $childCount.ContainsKey([uint32]$p.ProcessId))
    # conhost.exe is NEVER a victim (see header note)
    if (-not ($mcpClass -contains $n) -and -not $isCmdZombie) {
        continue
    }
    $why = Test-KeepAlive $p
    if ($why) {
        if ($why -eq 'whitelist') { $keptWl++ }
        elseif ($why -eq 'service') { $keptSvc++ }
        else { $keptAgent++ }
        continue
    }
    $killed++
    if (-not $WhatIfOnly.IsPresent) { Stop-Process -Id $p.ProcessId -Force }
    $cl = ($p.CommandLine -replace '\s+', ' ')
    $short = ''
    if ($cl) { $short = $cl.Substring(0, [Math]::Min(90, $cl.Length)) }
    [pscustomobject]@{ Pid = $p.ProcessId; Name = $p.Name; Cmd = $short }
}
"RESULT: would-kill/keep = $killed / (roots:$keptAgent services:$keptSvc whitelist:$keptWl)" +
    $(if ($WhatIfOnly) { '   [WHATIF]' })
$victims | Select-Object -First 40 | Format-Table -AutoSize | Out-String -Width 120
