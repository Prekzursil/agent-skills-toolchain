# RAM / MCP process audit — what is actually eating memory.
# Output: overall top consumers, MCP-class processes grouped by command line,
# orphan detection (parent PID no longer alive), commit totals.
$ErrorActionPreference = 'SilentlyContinue'

$procs = Get-CimInstance Win32_Process |
    Select-Object ProcessId, ParentProcessId, Name,
        @{n='WS_MB';e={[math]::Round($_.WorkingSetSize/1MB,0)}},
        @{n='Priv_MB';e={[math]::Round($_.PrivateMemorySize64/1MB,0)}},
        CommandLine
$livePids = $procs | ForEach-Object { $_.ProcessId }

"=== OVERALL (top 10 by private commit) ==="
$procs | Sort-Object Priv_MB -Descending | Select-Object -First 10 Name, ProcessId, WS_MB, Priv_MB |
    Format-Table -AutoSize | Out-String -Width 100

"=== MCP-CLASS PROCESSES (node/python/uv/uvx/npx/bun/deno) ==="
$mcpNames = @('node.exe','python.exe','python3.exe','uv.exe','uvx.exe','npx.exe','npx.cmd','bun.exe','deno.exe')
$mcp = $procs | Where-Object { $mcpNames -contains $_.Name.ToLower() }
"MCP-class process count: {0}   total private: {1:N1} GB" -f @($mcp).Count, (($mcp | Measure-Object Priv_MB -Sum).Sum / 1024)

function Short-Cmd([string]$c) {
    if (-not $c) { return '<no cmdline>' }
    # first 3 meaningful tokens of the command line, minus full paths
    $t = ($c -replace '\\', '/').Split(' ') | Where-Object { $_ } | Select-Object -First 4
    return ($t -join ' ').Substring(0, [Math]::Min(110, ($t -join ' ').Length))
}

"=== GROUPED BY COMMAND LINE (count, private GB, orphan count) ==="
$mcp | Group-Object { Short-Cmd $_.CommandLine } |
    ForEach-Object {
        $orphans = @($_.Group | Where-Object { $livePids -notcontains $_.ParentProcessId }).Count
        [pscustomobject]@{
            Count   = $_.Count
            Priv_GB = [math]::Round((($_.Group | Measure-Object Priv_MB -Sum).Sum / 1024), 2)
            Orphans = $orphans
            Cmd     = $_.Name
        }
    } | Sort-Object Priv_GB -Descending | Select-Object -First 25 |
    Format-Table -AutoSize | Out-String -Width 200

"=== SYSTEM COMMIT ==="
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_PageFileUsage | Select-Object Name, @{n='Size_GB';e={[math]::Round($_.AllocatedBaseSize/1024,1)}}
"free RAM GB: {0:N1}   commit charge GB: {1:N1} / limit {2:N1}" -f `
    ($os.FreePhysicalMemory/1MB), `
    (($os.TotalVirtualMemorySize - $os.FreeVirtualMemory)/1MB), `
    ($os.TotalVirtualMemorySize/1MB)
$cs | Format-Table -AutoSize | Out-String -Width 80
