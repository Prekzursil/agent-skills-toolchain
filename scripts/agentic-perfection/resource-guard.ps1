#requires -Version 5.1
<#
  Resource Guard  (5-minute Scheduled Task: 'Resource-Guard')  -- ANTICIPATORY layer producer.

  Samples three EXTERNAL signals every hour and, ONLY when a threshold is crossed,
  appends ONE dated line to the BACKGROUND-DIGEST so the next session surfaces it:

    * free physical RAM (GB)         -- targets the documented RAM-OOM (we saw ~3 GB free)
    * C: free space (% used / GB)    -- targets the documented C:-drive bloat
    * duplicate MCP-server processes + semgrep-family resident MB
                                     -- targets per-session MCP duplication / osemgrep-pro RAM

  Resource alerts stay LOG + SURFACE + PROPOSE. The one exception is the dedicated
  cursor-orphan-reaper micro-guard when -ReapOrphanCursorAgents is set: it can terminate
  only an exact Cursor Agent process tree after dead-parent, age, whole-tree-idle, and
  repeated-observation checks. It never kills by process name. Anti-spam:
  a digest line is appended only when the crossed-threshold signature CHANGES or a cooldown
  window elapses, so an unchanging condition does not enqueue a line every hour. Every run
  (alert or OK) is recorded to resource-guard.log (rotated). Fully fail-open: every path is
  wrapped in try/catch and the script can only ever exit 0.

  Built 2026-06-29.

  Overrides exist for TESTING (inject metrics + redirect files) without touching real state.
#>

[CmdletBinding()]
param(
    [string]$DigestFile = 'C:\Users\Prekzursil\.claude\BACKGROUND-DIGEST.md',
    [string]$StateFile  = 'C:\Users\Prekzursil\.agent-guard\resource-guard\state\resource-guard.state.json',
    [string]$LogFile    = 'C:\Users\Prekzursil\.agent-guard\resource-guard\log\resource-guard.log',

    [double]$MinFreeRamGb = 4.0,     # alert when free RAM below this
    [int]   $MaxCUsedPct  = 90,      # alert when C: used% at/above this
    [int]   $MinDupProcs  = 8,       # alert when ONE MCP server has >= this many copies (leak)
    [int]   $MinSemgrepMb = 400,     # alert when semgrep-family resident MB at/above this
    [double]$CooldownHours = 12.0,   # re-enqueue an unchanged alert at most this often
    [string]$OrphanReaper = 'C:\Users\Prekzursil\.agents\scripts\agentic-perfection\cursor-orphan-reaper.ps1',
    [string]$OrphanStateFile = 'C:\Users\Prekzursil\.agent-guard\resource-guard\state\cursor-orphan-reaper.state.json',
    [string]$OrphanEvidenceRoot = 'C:\Users\Prekzursil\.agent-guard\resource-guard\evidence',
    [switch]$ReapOrphanCursorAgents,

    # Process-hygiene supervisor liveness (tools/process-hygiene-supervisor, 2026-09-02).
    # A dead watchdog and a quiet box look identical from its own output, so this
    # producer asks the supervisor's read-only doctor whether the heartbeat is stale and
    # lets the doctor append its own (12 h cooldown) digest line. INERT until the
    # supervisor is deployed: when the doctor file is absent this is one log line.
    [string]$HygieneDoctor = 'C:\Users\Prekzursil\.agent-guard\process-hygiene\hygiene_doctor.py',
    [string]$HygieneRoot   = 'C:\Users\Prekzursil\.agent-guard\process-hygiene',
    [string]$HygienePython = 'C:\Python314\python.exe',

    # --- test/simulation overrides (when set, skip live sampling for that metric) ---
    [Nullable[double]]$FreeRamGbOverride = $null,
    [Nullable[int]]   $CUsedPctOverride  = $null,
    [Nullable[int]]   $DupProcsOverride  = $null,
    [Nullable[int]]   $SemgrepMbOverride = $null,
    [Nullable[double]]$CFreeGbOverride   = $null
)

$MaxLogLines = 300
$ReapTool = 'C:\Users\Prekzursil\.local\opt\re-harness\mcp_doctor.py'

function Get-Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

function Write-RgLog {
    param([string]$Line)
    try {
        $dir = Split-Path -Parent $LogFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        Add-Content -LiteralPath $LogFile -Value $Line -Encoding utf8
        $all = @(Get-Content -LiteralPath $LogFile -ErrorAction SilentlyContinue)
        if ($all.Count -gt $MaxLogLines) {
            $all | Select-Object -Last $MaxLogLines | Set-Content -LiteralPath $LogFile -Encoding utf8
        }
    } catch { }
}

function Add-DigestLine {
    # Append ONE entry line to the BACKGROUND-DIGEST queue. Single physical line only.
    param([string]$Source, [string]$Message, [string]$Propose)
    try {
        $dir = Split-Path -Parent $DigestFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        $clean = ($Message -replace '\r?\n', ' ').Trim()
        $line = "[{0}] [{1}] {2}" -f (Get-Stamp), $Source, $clean
        if ($Propose) { $line = "$line  | PROPOSE: $(( $Propose -replace '\r?\n',' ').Trim())" }
        Add-Content -LiteralPath $DigestFile -Value $line -Encoding utf8
        return $true
    } catch { return $false }
}

# ---- samplers (each fail-open to a benign value) ---------------------------
function Sample-FreeRamGb {
    if ($null -ne $FreeRamGbOverride) { return [double]$FreeRamGbOverride }
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        return [math]::Round($os.FreePhysicalMemory / 1MB, 1)   # KB -> GB
    } catch { return [double]::PositiveInfinity }               # unknown -> never alarm
}

function Sample-CDisk {
    # returns @{ UsedPct=<int>; FreeGb=<double> }
    if (($null -ne $CUsedPctOverride) -or ($null -ne $CFreeGbOverride)) {
        $up = if ($null -ne $CUsedPctOverride) { [int]$CUsedPctOverride } else { 0 }
        $fg = if ($null -ne $CFreeGbOverride) { [double]$CFreeGbOverride } else { 999.0 }
        return @{ UsedPct = $up; FreeGb = $fg }
    }
    try {
        $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction Stop
        if ($d.Size -gt 0) {
            $usedPct = [int][math]::Round((($d.Size - $d.FreeSpace) / $d.Size) * 100)
            $freeGb  = [math]::Round($d.FreeSpace / 1GB, 1)
            return @{ UsedPct = $usedPct; FreeGb = $freeGb }
        }
    } catch { }
    return @{ UsedPct = 0; FreeGb = 999.0 }                     # unknown -> never alarm
}

function Get-McpSignature {
    # FULL-PATH identity for an MCP-ish process (lowercased) so two different tools that
    # both ship an index.js / server.py are NOT conflated. Falls back to `-m <module>`.
    # Returns @{ Sig=<full-path-or-module>; Name=<basename> } or $null.
    param([string]$CmdLine)
    if ([string]::IsNullOrWhiteSpace($CmdLine)) { return $null }
    $m = [regex]::Match($CmdLine, '(?i)([^\s"'']+\.(?:py|js|mjs|cjs))')
    if ($m.Success) {
        $full = $m.Groups[1].Value
        return @{ Sig = $full.ToLower(); Name = (Split-Path -Leaf $full).ToLower() }
    }
    $m = [regex]::Match($CmdLine, '(?i)-m\s+([A-Za-z0-9_.]+)')
    if ($m.Success) { $mod = 'm:' + $m.Groups[1].Value.ToLower(); return @{ Sig = $mod; Name = $mod } }
    return $null
}

function Sample-McpPressure {
    # The "duplicate-MCP" signal = the WORST single-server duplication (max copies of one
    # full-path), which isolates a stuck/leaked server from healthy per-session spawns.
    # returns @{ Dup; DupName; Excess; SemgrepMb; TotalMcpMb; Note }
    if (($null -ne $DupProcsOverride) -or ($null -ne $SemgrepMbOverride)) {
        $dp = if ($null -ne $DupProcsOverride) { [int]$DupProcsOverride } else { 0 }
        $sm = if ($null -ne $SemgrepMbOverride) { [int]$SemgrepMbOverride } else { 0 }
        return @{ Dup = $dp; DupName = 'override'; Excess = $dp; SemgrepMb = $sm; TotalMcpMb = 0; Note = 'override' }
    }
    try {
        $procs = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            ($_.Name -match '(?i)^(node|python|python3.*|py)\.exe$') -or
            ($_.CommandLine -match '(?i)semgrep|osemgrep|mcp')
        })
        # semgrep-family resident MB (the documented osemgrep-pro RAM hog)
        $semProcs = @($procs | Where-Object { ($_.Name -match '(?i)semgrep') -or ($_.CommandLine -match '(?i)semgrep|osemgrep') })
        $semMb = 0
        if ($semProcs.Count -gt 0) {
            $sumBytes = ($semProcs | Measure-Object -Property WorkingSetSize -Sum).Sum
            if ($sumBytes) { $semMb = [int][math]::Round($sumBytes / 1MB) }
        }
        # MCP-server processes (cmdline mentions mcp) -> aggregate RAM + per-full-path counts
        $mcpish = @($procs | Where-Object { $_.CommandLine -match '(?i)mcp' })
        $totalMb = 0
        if ($mcpish.Count -gt 0) {
            $mb = ($mcpish | Measure-Object -Property WorkingSetSize -Sum).Sum
            if ($mb) { $totalMb = [int][math]::Round($mb / 1MB) }
        }
        $counts = @{}; $names = @{}
        foreach ($p in $mcpish) {
            $s = Get-McpSignature -CmdLine $p.CommandLine
            if ($s) {
                $k = $s.Sig
                if ($counts.ContainsKey($k)) { $counts[$k] = $counts[$k] + 1 } else { $counts[$k] = 1; $names[$k] = $s.Name }
            }
        }
        $maxDup = 0; $maxName = ''; $excess = 0
        foreach ($k in $counts.Keys) {
            $c = $counts[$k]
            if ($c -gt 1) { $excess += ($c - 1) }
            if ($c -gt $maxDup) { $maxDup = $c; $maxName = $names[$k] }
        }
        # top-3 offenders for the human note
        $top = @($counts.GetEnumerator() | Where-Object { $_.Value -gt 1 } |
                 Sort-Object Value -Descending | Select-Object -First 3 |
                 ForEach-Object { "{0}x{1}" -f $_.Value, $names[$_.Key] })
        $note = "worst={0}x{1}; excess={2}; mcpRAM={3}MB; top=[{4}]" -f `
                $maxDup, $maxName, $excess, $totalMb, ($top -join ',')
        if ($semProcs.Count -gt 0) { $note = "$note; semgrepx$($semProcs.Count)" }
        return @{ Dup = $maxDup; DupName = $maxName; Excess = $excess; SemgrepMb = $semMb; TotalMcpMb = $totalMb; Note = $note }
    } catch { return @{ Dup = 0; DupName = ''; Excess = 0; SemgrepMb = 0; TotalMcpMb = 0; Note = 'sample-error' } }
}

# ---- state (anti-spam) -----------------------------------------------------
function Read-State {
    try {
        if (Test-Path -LiteralPath $StateFile) {
            return (Get-Content -LiteralPath $StateFile -Raw -ErrorAction Stop | ConvertFrom-Json)
        }
    } catch { }
    return $null
}
function Write-State {
    param([string]$Sig)
    try {
        $dir = Split-Path -Parent $StateFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $obj = [ordered]@{ last_sig = $Sig; last_digest_unix = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); last_run = (Get-Stamp) }
        ($obj | ConvertTo-Json -Compress) | Set-Content -LiteralPath $StateFile -Encoding utf8
    } catch { }
}

# ---------------------------------------------------------------------------
try {
    $stamp = Get-Stamp

    # High-risk process mutation stays in a dedicated micro-guard. It only
    # targets an exact cursor-agent root after parent-absent + age + whole-tree
    # CPU-idle + repeated-observation checks. Never kill node.exe by name.
    if (Test-Path -LiteralPath $OrphanReaper -PathType Leaf) {
        try {
            if ($ReapOrphanCursorAgents) {
                $reaperOutput = @(
                    & $OrphanReaper `
                        -StateFile $OrphanStateFile `
                        -EvidenceRoot $OrphanEvidenceRoot `
                        -Apply 2>&1
                )
            }
            else {
                $reaperOutput = @(
                    & $OrphanReaper `
                        -StateFile $OrphanStateFile `
                        -EvidenceRoot $OrphanEvidenceRoot 2>&1
                )
            }
            $reaperExit = $LASTEXITCODE
            $reaperLine = (($reaperOutput | Select-Object -Last 1) -replace '\r?\n', ' ')
            if ($reaperLine.Length -gt 600) { $reaperLine = $reaperLine.Substring(0, 600) }
            Write-RgLog "[$stamp] ORPHAN-GUARD exit=$reaperExit apply=$([int][bool]$ReapOrphanCursorAgents) $reaperLine"
            $reaperResult = $null
            try { $reaperResult = $reaperLine | ConvertFrom-Json } catch { }
            if ($reaperExit -ne 0 -or ($reaperResult -and [int]$reaperResult.reaped -gt 0)) {
                $surface = if ($reaperExit -ne 0) {
                    "orphan reaper failed closed (exit $reaperExit)"
                } else {
                    "reaped $([int]$reaperResult.reaped) confirmed Cursor Agent orphan tree(s)"
                }
                Add-DigestLine -Source 'cursor-orphan-reaper' -Message $surface `
                    -Propose 'review the resource-guard log and secure-evidence receipt' | Out-Null
            }
        }
        catch {
            $detail = ($_.Exception.Message -replace '\r?\n', ' ').Trim()
            if ($detail.Length -gt 240) { $detail = $detail.Substring(0, 240) }
            Write-RgLog "[$stamp] ORPHAN-GUARD failed closed; no broad process kill attempted; reason=$detail"
        }
    }
    else {
        Write-RgLog "[$stamp] ORPHAN-GUARD missing: $OrphanReaper"
    }

    # Supervisor liveness. Read-only (--quick reads one heartbeat file, spawns nothing
    # else), fail-open, and the doctor owns its own anti-spam marker so this cannot
    # double-enqueue with the resource-guard signature below.
    if ($HygieneDoctor -and (Test-Path -LiteralPath $HygieneDoctor -PathType Leaf) -and (Test-Path -LiteralPath $HygienePython -PathType Leaf)) {
        try {
            $doctorOut = @(& $HygienePython $HygieneDoctor --quick --root $HygieneRoot --digest $DigestFile 2>&1)
            $doctorExit = $LASTEXITCODE
            $doctorLine = (($doctorOut | Select-Object -Last 1) -replace '\r?\n', ' ')
            if ($doctorLine.Length -gt 300) { $doctorLine = $doctorLine.Substring(0, 300) }
            Write-RgLog "[$stamp] HYGIENE-DOCTOR exit=$doctorExit $doctorLine"
        }
        catch {
            $detail = ($_.Exception.Message -replace '\r?\n', ' ').Trim()
            if ($detail.Length -gt 240) { $detail = $detail.Substring(0, 240) }
            Write-RgLog "[$stamp] HYGIENE-DOCTOR failed open; reason=$detail"
        }
    }
    else {
        Write-RgLog "[$stamp] HYGIENE-DOCTOR not deployed (skipped): $HygieneDoctor"
    }

    $ramGb  = Sample-FreeRamGb
    $disk   = Sample-CDisk
    $mcp    = Sample-McpPressure

    $crossed = @()
    if ($ramGb -lt $MinFreeRamGb)               { $crossed += ("RAM {0}GB free (<{1})" -f $ramGb, $MinFreeRamGb) }
    if ($disk.UsedPct -ge $MaxCUsedPct)         { $crossed += ("C: {0}% used (>={1}), {2}GB free" -f $disk.UsedPct, $MaxCUsedPct, $disk.FreeGb) }
    if ($mcp.Dup -ge $MinDupProcs)              { $crossed += ("{0} copies of {1} (worst MCP duplication, >={2}); {3}" -f $mcp.Dup, $mcp.DupName, $MinDupProcs, $mcp.Note) }
    if ($mcp.SemgrepMb -ge $MinSemgrepMb)       { $crossed += ("semgrep-family {0}MB resident" -f $mcp.SemgrepMb) }

    $metricLine = ("RAM={0}GB C:={1}%/{2}GBfree maxDupMCP={3}({4}) mcpRAM={5}MB semgrepMB={6}" -f `
        $ramGb, $disk.UsedPct, $disk.FreeGb, $mcp.Dup, $mcp.DupName, $mcp.TotalMcpMb, $mcp.SemgrepMb)

    if ($crossed.Count -eq 0) {
        Write-RgLog "[$stamp] OK   $metricLine"
        return
    }

    # build a stable signature of WHICH thresholds crossed (not the exact values) for anti-spam
    $sig = ("ram:{0}|disk:{1}|dup:{2}|semg:{3}" -f `
        [int]($ramGb -lt $MinFreeRamGb), [int]($disk.UsedPct -ge $MaxCUsedPct), `
        [int]($mcp.Dup -ge $MinDupProcs), [int]($mcp.SemgrepMb -ge $MinSemgrepMb))

    $state = Read-State
    $lastSig = if ($state) { [string]$state.last_sig } else { '' }
    $lastUnix = if ($state -and $state.last_digest_unix) { [double]$state.last_digest_unix } else { 0.0 }
    $nowUnix = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $elapsedHr = if ($lastUnix -gt 0) { ($nowUnix - $lastUnix) / 3600.0 } else { [double]::PositiveInfinity }

    $shouldEnqueue = ($sig -ne $lastSig) -or ($elapsedHr -ge $CooldownHours)

    # choose a PROPOSED remediation matching what crossed (never auto-run)
    $proposals = @()
    if (($mcp.Dup -ge $MinDupProcs) -or ($mcp.SemgrepMb -ge $MinSemgrepMb) -or ($ramGb -lt $MinFreeRamGb)) {
        $proposals += ("review pile-up: python `"$ReapTool`" audit  then  reap --apply if real")
    }
    if ($disk.UsedPct -ge $MaxCUsedPct) {
        $proposals += 'reclaim C:: pwsh -File C:\Users\Prekzursil\scripts\reclaim-c-drive.ps1'
    }
    $propose = ($proposals -join '  ||  ')

    $msg = ($crossed -join '; ')
    Write-RgLog "[$stamp] ALERT $metricLine  sig=$sig change=$([int]($sig -ne $lastSig)) elapsedHr=$([math]::Round($elapsedHr,1)) enqueue=$([int]$shouldEnqueue)"

    if ($shouldEnqueue) {
        $ok = Add-DigestLine -Source 'resource-guard' -Message $msg -Propose $propose
        if ($ok) {
            Write-RgLog "[$stamp]   -> digest append ok: $msg"
            # advance anti-spam state ONLY after a confirmed enqueue, else a failed delivery
            # would be silently suppressed for the cooldown window.
            Write-State -Sig $sig
        } else {
            Write-RgLog "[$stamp]   -> digest append FAILED (state NOT advanced; retries next run): $msg"
        }
    } else {
        Write-RgLog "[$stamp]   -> suppressed (same sig within cooldown ${CooldownHours}h)"
    }
}
catch {
    try { Write-RgLog "[$(Get-Stamp)] ERROR unhandled: $($_.Exception.Message)" } catch { }
}

exit 0   # deterministic success code (no native-cmd $LASTEXITCODE leakage to Task Scheduler)
