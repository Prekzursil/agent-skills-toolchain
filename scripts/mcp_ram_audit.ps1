# RAM / MCP process audit — what is actually eating memory.
# Output: overall top consumers, MCP-class processes grouped by command line,
# orphan detection (parent PID no longer alive), commit totals.
$ErrorActionPreference = 'SilentlyContinue'

$procs = Get-CimInstance Win32_Process |
    Select-Object ProcessId, ParentProcessId, Name,
        @{n='WS_MB';e={[math]::Round($_.WorkingSetSize/1MB,0)}},
        # P1 2026-09-25: Win32_Process has NO PrivateMemorySize64 (that is a .NET Process
        # property). It was always $null -> 0 -> this tool reported 0.00 MB for EVERY process
        # while the true figure was 20.51 GB. PrivatePageCount is the CIM property, in BYTES.
        @{n='Priv_MB';e={[math]::Round($_.PrivatePageCount/1MB,0)}},
        CommandLine
$livePids = $procs | ForEach-Object { $_.ProcessId }

"=== OVERALL (top 10 by private commit) ==="
$procs | Sort-Object Priv_MB -Descending | Select-Object -First 10 Name, ProcessId, WS_MB, Priv_MB |
    Format-Table -AutoSize | Out-String -Width 100

"=== MCP-CLASS PROCESSES (node/python/uv/uvx/npx/bun/deno) ==="
$mcpNames = @('node.exe','python.exe','python3.exe','uv.exe','uvx.exe','npx.exe','npx.cmd','bun.exe','deno.exe')
$mcp = $procs | Where-Object { $mcpNames -contains $_.Name.ToLower() }
"MCP-class process count: {0}   total private: {1:N1} GB" -f @($mcp).Count, (($mcp | Measure-Object Priv_MB -Sum).Sum / 1024)

# P1 2026-09-25: group on the FULL command line and truncate only for DISPLAY, keeping the
# TAIL. The head is node.exe/npx-cli.js boilerplate; the package name lives at the END, so
# the old 4-token head-truncation collapsed 91 distinct servers into 1 apparent group and
# manufactured the false "90 identical wrappers from one command line" conclusion.
function Tail-Cmd([string]$c) {
    if (-not $c) { return '<no cmdline>' }
    $c = ($c -replace '\s+', ' ').Trim()
    if ($c.Length -le 110) { return $c }
    return '...' + $c.Substring($c.Length - 107)
}

"=== GROUPED BY COMMAND LINE (count, private GB, orphan count) ==="
$mcp | Group-Object CommandLine |
    ForEach-Object {
        $orphans = @($_.Group | Where-Object { $livePids -notcontains $_.ParentProcessId }).Count
        [pscustomobject]@{
            Count   = $_.Count
            Priv_GB = [math]::Round((($_.Group | Measure-Object Priv_MB -Sum).Sum / 1024), 2)
            Orphans = $orphans
            Cmd     = Tail-Cmd $_.Name
        }
    } | Sort-Object Priv_GB -Descending | Select-Object -First 25 |
    Format-Table -AutoSize | Out-String -Width 200

# P1 2026-09-25: a SECOND signal, independent of orphan-parentage. The orphan column above
# and reap_orphan_mcp.ps1 use the same parentage test, so they are blind in identical ways
# and cannot cross-check each other. Duplication + ownership is what distinguishes
# per-session multiplication (VM: 333 procs, ~97% under 4 claude.exe) from shared daemons
# (HOME: 109 procs, 0 session-owned) from true orphans.
"=== DUPLICATION + OWNERSHIP ==="
$byPid = @{}; foreach ($p in $procs) { $byPid[[int]$p.ProcessId] = $p }
$dupGroups = @($mcp | Group-Object CommandLine)
"distinct command lines: {0}   max multiplicity: {1}" -f $dupGroups.Count, (($dupGroups | Measure-Object Count -Maximum).Maximum)
$mcp | ForEach-Object {
        $cur = $_; $hops = 0; $owner = 'UNATTRIBUTED'
        while ($cur -and $hops -lt 12) {
            if ($cur.Name -match '^(claude|codex|cursor|Code|windsurf)\.exe$') { $owner = "SESSION:$($cur.Name):$($cur.ProcessId)"; break }
            if ($cur.Name -match '^(services|svchost|taskeng|taskhostw|wininit)\.exe$') { $owner = 'DAEMON(service/task)'; break }
            $pp = [int]$cur.ParentProcessId
            if (-not $byPid.ContainsKey($pp)) { $owner = 'DEAD-PARENT'; break }
            $cur = $byPid[$pp]; $hops++
        }
        [pscustomobject]@{ Owner = $owner }
    } | Group-Object Owner | Sort-Object Count -Descending |
    Select-Object @{n='Owner';e={$_.Name}}, Count | Format-Table -AutoSize | Out-String -Width 80
"SESSION:* dominant -> per-session MULTIPLICATION; an orphan reaper cannot help."
"DAEMON dominant    -> shared long-lived servers; supervision is the correct tool."
"DEAD-PARENT        -> true orphans; this is what reap_orphan_mcp.ps1 targets."

"=== SYSTEM COMMIT ==="
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_PageFileUsage | Select-Object Name, @{n='Size_GB';e={[math]::Round($_.AllocatedBaseSize/1024,1)}}
"free RAM GB: {0:N1}   commit charge GB: {1:N1} / limit {2:N1}" -f `
    ($os.FreePhysicalMemory/1MB), `
    (($os.TotalVirtualMemorySize - $os.FreeVirtualMemory)/1MB), `
    ($os.TotalVirtualMemorySize/1MB)
$cs | Format-Table -AutoSize | Out-String -Width 80
