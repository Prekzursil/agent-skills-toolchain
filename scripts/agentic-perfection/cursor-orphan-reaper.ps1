#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$StateFile = 'C:\Users\Prekzursil\.agent-guard\resource-guard\state\cursor-orphan-reaper.state.json',
    [string]$EvidenceRoot = 'C:\Users\Prekzursil\.agent-guard\resource-guard\evidence',
    [string]$ProcessSnapshotFile = '',
    [string]$KillRecorderFile = '',
    [Nullable[long]]$NowUnix = $null,
    [int]$MinOrphanAgeMinutes = 30,
    [int]$ConfirmationSeconds = 1800,
    [int]$MinObservations = 3,
    [double]$MaxTreeCpuDeltaSeconds = 0.10,
    [long]$MaxTreeIoDeltaBytes = 0,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$CursorAgentPathPattern = '(?i)\\cursor-agent\\versions\\[^\\]+\\node\.exe$'

function Get-NowUnix {
    if ($null -ne $NowUnix) { return [long]$NowUnix }
    return [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}

function Convert-ToUnix([object]$Value) {
    if ($Value -is [DateTime]) {
        return [DateTimeOffset]$Value | ForEach-Object { $_.ToUnixTimeSeconds() }
    }
    $parsed = [DateTimeOffset]::MinValue
    if ([DateTimeOffset]::TryParse([string]$Value, [ref]$parsed)) {
        return $parsed.ToUnixTimeSeconds()
    }
    return 0L
}

function Get-Descendants([int]$Root, [hashtable]$Children, [hashtable]$ById) {
    $seen = New-Object 'System.Collections.Generic.HashSet[int]'
    $queue = New-Object 'System.Collections.Generic.Queue[int]'
    $queue.Enqueue($Root)
    while ($queue.Count -gt 0) {
        $id = $queue.Dequeue()
        if ($seen.Add($id) -and $Children.ContainsKey($id)) {
            foreach ($child in $Children[$id]) {
                $parentCreated = [long]$ById[$id].created_unix
                $childCreated = [long]$ById[[int]$child].created_unix
                if ($parentCreated -gt 0 -and $childCreated -ge $parentCreated) {
                    $queue.Enqueue([int]$child)
                }
            }
        }
    }
    return @($seen)
}

function Read-LiveSnapshot {
    $cim = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $metrics = @{}
    foreach ($process in Get-Process -ErrorAction SilentlyContinue) {
        $metrics[[int]$process.Id] = $process
    }
    $rows = @()
    foreach ($process in $cim) {
        $id = [int]$process.ProcessId
        $metric = $metrics[$id]
        $ioTotal = [long]$process.ReadTransferCount + [long]$process.WriteTransferCount
        $rows += [pscustomobject]@{
            pid = $id
            ppid = [int]$process.ParentProcessId
            name = [string]$process.Name
            executable = [string]$process.ExecutablePath
            created_unix = Convert-ToUnix $process.CreationDate
            cpu_total_seconds = if ($metric) { [double]$metric.CPU } else { 0.0 }
            io_total_bytes = $ioTotal
            metrics_known = (
                $null -ne $metric -and
                $null -ne $metric.CPU -and
                $null -ne $process.ReadTransferCount -and
                $null -ne $process.WriteTransferCount
            )
            cpu_delta_seconds = 0.0
            io_delta_bytes = 0L
            working_set_bytes = if ($metric) { [int64]$metric.WorkingSet64 } else { 0L }
            private_bytes = if ($metric) { [int64]$metric.PrivateMemorySize64 } else { 0L }
        }
    }
    return $rows
}

function Read-Snapshot {
    if ($ProcessSnapshotFile) {
        $payload = Get-Content -LiteralPath $ProcessSnapshotFile -Raw | ConvertFrom-Json
        return @($payload.processes)
    }
    return @(Read-LiveSnapshot)
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StateFile)) {
        return @{ candidates = @{} }
    }
    try {
        $raw = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        if ($null -eq $raw -or $null -eq $raw.candidates) {
            throw 'missing candidates map'
        }
        $candidates = @{}
        foreach ($property in $raw.candidates.PSObject.Properties) {
            $value = $property.Value
            $members = @{}
            if ($null -ne $value.members) {
                foreach ($member in $value.members.PSObject.Properties) {
                    $members[$member.Name] = @{
                        cpu_total_seconds = [double]$member.Value.cpu_total_seconds
                        io_total_bytes = [long]$member.Value.io_total_bytes
                    }
                }
            }
            $candidates[$property.Name] = @{
                pid = [int]$value.pid
                created_unix = [long]$value.created_unix
                first_seen = [long]$value.first_seen
                last_seen = [long]$value.last_seen
                observations = [int]$value.observations
                tree_cpu_delta_seconds = [double]$value.tree_cpu_delta_seconds
                tree_io_delta_bytes = [long]$value.tree_io_delta_bytes
                tree_cpu_total_seconds = [double]$value.tree_cpu_total_seconds
                tree_io_total_bytes = [long]$value.tree_io_total_bytes
                members = $members
                descendants = @($value.descendants | ForEach-Object { [int]$_ })
            }
        }
        return @{ candidates = $candidates; updated_unix = [long]$raw.updated_unix }
    }
    catch {
        throw "state file is malformed or unreadable: $StateFile"
    }
}

function Write-State([hashtable]$State) {
    $directory = Split-Path -Parent $StateFile
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $temp = "$StateFile.$PID.tmp"
    try {
        $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temp -Encoding utf8
        Move-Item -LiteralPath $temp -Destination $StateFile -Force
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}

function Write-Evidence([object]$Record) {
    if (-not (Test-Path -LiteralPath $EvidenceRoot)) {
        New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
    }
    $path = Join-Path $EvidenceRoot (
        "orphan-{0}-{1}.json" -f $Record.pid, $Record.created_unix
    )
    $temp = "$path.$PID.tmp"
    try {
        $Record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temp -Encoding utf8
        Move-Item -LiteralPath $temp -Destination $path -Force
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
    return $path
}

function Invoke-ExactTreeKill([int]$RootPid, [object[]]$TreeRecords) {
    $treeIds = @($TreeRecords | ForEach-Object { [int]$_.pid })
    if ($KillRecorderFile) {
        $directory = Split-Path -Parent $KillRecorderFile
        if ($directory -and -not (Test-Path -LiteralPath $directory)) {
            New-Item -ItemType Directory -Force -Path $directory | Out-Null
        }
        @{ pid = $RootPid; descendants = @($TreeIds) } |
            ConvertTo-Json -Compress |
            Add-Content -LiteralPath $KillRecorderFile -Encoding utf8
        return @{ success = $true; survivors = @() }
    }

    # Revalidate every PID identity before the first irreversible action. A
    # recycled PID or changed executable aborts the entire tree.
    $liveRecords = @()
    foreach ($expected in $TreeRecords) {
        $id = [int]$expected.pid
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
        if (-not $current) { continue }
        $currentCreated = Convert-ToUnix $current.CreationDate
        if (
            $currentCreated -ne [long]$expected.created_unix -or
            [string]$current.ExecutablePath -ne [string]$expected.executable
        ) {
            return @{ success = $false; survivors = @($id); reason = 'identity-changed' }
        }
        $liveRecords += $expected
    }

    # Children first, exact PIDs only. Never ask taskkill to discover a live
    # `/T` tree from stale Windows PPIDs.
    foreach ($expected in @($liveRecords | Sort-Object created_unix -Descending)) {
        $id = [int]$expected.pid
        $immediate = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
        if (-not $immediate) { continue }
        if (
            (Convert-ToUnix $immediate.CreationDate) -ne [long]$expected.created_unix -or
            [string]$immediate.ExecutablePath -ne [string]$expected.executable
        ) {
            return @{ success = $false; survivors = @($id); reason = 'identity-changed-before-kill' }
        }
        & taskkill.exe /PID $id /F 2>$null | Out-Null
        $taskkillExit = $LASTEXITCODE
        $still = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
        if ($still) {
            $sameIdentity = (
                (Convert-ToUnix $still.CreationDate) -eq [long]$expected.created_unix -and
                [string]$still.ExecutablePath -eq [string]$expected.executable
            )
            if ($sameIdentity -or $taskkillExit -ne 0) {
                return @{ success = $false; survivors = @($id); reason = "taskkill-exit-$taskkillExit" }
            }
        }
    }
    return @{ success = $true; survivors = @() }
}

try {
    $now = Get-NowUnix
    $processes = @(Read-Snapshot)
    $byId = @{}
    $children = @{}
    foreach ($process in $processes) {
        $id = [int]$process.pid
        $byId[$id] = $process
        $parent = [int]$process.ppid
        if (-not $children.ContainsKey($parent)) { $children[$parent] = @() }
        $children[$parent] += $id
    }

    $previous = Read-State
    $nextCandidates = @{}
    $confirmed = @()
    $candidateCount = 0

    foreach ($process in $processes) {
        $id = [int]$process.pid
        $parent = [int]$process.ppid
        $path = [string]$process.executable
        if ([string]$process.name -ne 'node.exe') { continue }
        if ($path -notmatch $CursorAgentPathPattern) { continue }
        if ($byId.ContainsKey($parent)) { continue }
        if ([long]$process.created_unix -le 0) { continue }

        $tree = @(Get-Descendants -Root $id -Children $children -ById $byId)
        $treeCpu = 0.0
        $treeIo = 0L
        $treeCpuTotal = 0.0
        $treeIoTotal = 0L
        $treeMetricsKnown = $true
        $currentMembers = @{}
        foreach ($treeId in $tree) {
            if ($byId.ContainsKey($treeId)) {
                $member = $byId[$treeId]
                $treeCpu += [double]$member.cpu_delta_seconds
                $treeIo += [long]$member.io_delta_bytes
                $treeCpuTotal += [double]$member.cpu_total_seconds
                $treeIoTotal += [long]$member.io_total_bytes
                if (-not [bool]$member.metrics_known) { $treeMetricsKnown = $false }
                $memberKey = "{0}|{1}" -f [int]$member.pid, [long]$member.created_unix
                $currentMembers[$memberKey] = @{
                    cpu_total_seconds = [double]$member.cpu_total_seconds
                    io_total_bytes = [long]$member.io_total_bytes
                }
            }
        }
        $ageSeconds = $now - [long]$process.created_unix
        if ($ageSeconds -lt ($MinOrphanAgeMinutes * 60)) { continue }
        if (-not $treeMetricsKnown) { continue }
        if ($treeCpu -gt $MaxTreeCpuDeltaSeconds) { continue }
        if ($treeIo -gt $MaxTreeIoDeltaBytes) { continue }

        $candidateCount++
        $key = "{0}|{1}" -f $id, [long]$process.created_unix
        $old = if ($previous.candidates.ContainsKey($key)) { $previous.candidates[$key] } else { $null }
        $firstSeen = if ($old) { [long]$old.first_seen } else { $now }
        $observations = if ($old) { [int]$old.observations } else { 0 }
        $interRunCpu = 0.0
        $interRunIo = 0L
        $membershipChanged = $false
        if ($old) {
            $oldMembers = $old.members
            if ($oldMembers.Count -ne $currentMembers.Count) {
                $membershipChanged = $true
            }
            foreach ($memberKey in $currentMembers.Keys) {
                if (-not $oldMembers.ContainsKey($memberKey)) {
                    $membershipChanged = $true
                    continue
                }
                $cpuChange = (
                    [double]$currentMembers[$memberKey].cpu_total_seconds -
                    [double]$oldMembers[$memberKey].cpu_total_seconds
                )
                $ioChange = (
                    [long]$currentMembers[$memberKey].io_total_bytes -
                    [long]$oldMembers[$memberKey].io_total_bytes
                )
                if ($cpuChange -lt 0 -or $ioChange -lt 0) {
                    $membershipChanged = $true
                    continue
                }
                $interRunCpu += $cpuChange
                $interRunIo += $ioChange
            }
            foreach ($memberKey in $oldMembers.Keys) {
                if (-not $currentMembers.ContainsKey($memberKey)) {
                    $membershipChanged = $true
                }
            }
        }
        if ($Apply) {
            if (
                $old -and (
                    $membershipChanged -or
                    $interRunCpu -gt $MaxTreeCpuDeltaSeconds -or
                    $interRunIo -gt $MaxTreeIoDeltaBytes
                )
            ) {
                $firstSeen = $now
                $observations = 1
            }
            else {
                $observations++
            }
        }
        $entry = @{
            pid = $id
            created_unix = [long]$process.created_unix
            first_seen = $firstSeen
            last_seen = $now
            observations = $observations
            tree_cpu_delta_seconds = $treeCpu
            tree_io_delta_bytes = $treeIo
            tree_cpu_total_seconds = $treeCpuTotal
            tree_io_total_bytes = $treeIoTotal
            inter_run_cpu_delta_seconds = $interRunCpu
            inter_run_io_delta_bytes = $interRunIo
            membership_changed = $membershipChanged
            members = $currentMembers
            descendants = $tree
        }
        if ($Apply) { $nextCandidates[$key] = $entry }
        if ($Apply -and $observations -ge $MinObservations -and ($now - $firstSeen) -ge $ConfirmationSeconds) {
            $confirmed += [pscustomobject]@{ process = $process; state = $entry }
        }
    }

    $reaped = 0
    $failed = @()
    $evidence = @()
    foreach ($item in $confirmed) {
        $process = $item.process
        $entry = $item.state
        $record = [ordered]@{
            schema = 'cursor-orphan-reaper-v1'
            detected_unix = $now
            reason = 'exact cursor-agent executable; parent absent; age threshold; whole-tree CPU and IO idle; repeated observations'
            pid = [int]$process.pid
            ppid = [int]$process.ppid
            executable = [string]$process.executable
            created_unix = [long]$process.created_unix
            tree_cpu_delta_seconds = [double]$entry.tree_cpu_delta_seconds
            tree_io_delta_bytes = [long]$entry.tree_io_delta_bytes
            inter_run_cpu_delta_seconds = [double]$entry.inter_run_cpu_delta_seconds
            inter_run_io_delta_bytes = [long]$entry.inter_run_io_delta_bytes
            descendants = @($entry.descendants)
            working_set_bytes = [int64]$process.working_set_bytes
            private_bytes = [int64]$process.private_bytes
            apply = [bool]$Apply
        }
        $evidencePath = Write-Evidence $record
        $evidence += $evidencePath
        if ($Apply) {
            $treeRecords = @(
                $entry.descendants |
                    ForEach-Object { $byId[[int]$_] } |
                    Where-Object { $null -ne $_ }
            )
            $result = Invoke-ExactTreeKill -RootPid ([int]$process.pid) -TreeRecords $treeRecords
            if ($result.success) {
                $reaped++
                $nextCandidates.Remove(("{0}|{1}" -f [int]$process.pid, [long]$process.created_unix))
            }
            else {
                $failed += @($result.survivors)
            }
        }
    }

    if ($Apply) {
        Write-State @{ candidates = $nextCandidates; updated_unix = $now }
    }
    [ordered]@{
        status = if ($failed.Count) { 'error' } else { 'success' }
        summary = if ($Apply) { "confirmed orphan trees reaped: $reaped" } else { "confirmed orphan trees (report-only): $($confirmed.Count)" }
        next_actions = if ($failed.Count) { 'inspect survivor PIDs; do not kill by name' } else { 'none' }
        artifacts = $evidence
        candidates = $candidateCount
        confirmed = $confirmed.Count
        reaped = $reaped
        failed_survivors = $failed
    } | ConvertTo-Json -Depth 8 -Compress
    if ($failed.Count) { exit 2 }
    exit 0
}
catch {
    [ordered]@{
        status = 'error'
        summary = 'orphan reaper failed closed'
        next_actions = 'repair input/state; no process was killed after the failure'
        artifacts = @($StateFile)
        reason = $_.Exception.Message
    } | ConvertTo-Json -Compress
    exit 1
}
