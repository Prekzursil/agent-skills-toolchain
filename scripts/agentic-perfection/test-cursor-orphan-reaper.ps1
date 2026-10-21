$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot 'cursor-orphan-reaper.ps1'
$work = Join-Path $env:TEMP ("cursor-orphan-test-{0}" -f [guid]::NewGuid().ToString('N'))
$state = Join-Path $work 'state.json'
$evidence = Join-Path $work 'evidence'
$killLog = Join-Path $work 'kills.jsonl'
$fails = @()

New-Item -ItemType Directory -Force -Path $work | Out-Null

function Check([string]$Name, [bool]$Condition) {
    if ($Condition) { Write-Output "PASS: $Name" }
    else { Write-Output "FAIL: $Name"; $script:fails += $Name }
}

function Write-Snapshot([string]$Path, [object[]]$Processes) {
    @{ processes = $Processes } |
        ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $Path -Encoding utf8
}

$orphan = @{
    pid = 100
    ppid = 999
    name = 'node.exe'
    executable = 'C:\Users\Prekzursil\AppData\Local\cursor-agent\versions\test\node.exe'
    created_unix = 100
    cpu_total_seconds = 10.0
    io_total_bytes = 100
    metrics_known = $true
    cpu_delta_seconds = 0.0
    io_delta_bytes = 0
    descendants = @(100, 101, 102)
}
$child1 = @{ pid = 101; ppid = 100; name = 'cmd.exe'; executable = 'C:\Windows\System32\cmd.exe'; created_unix = 101; cpu_total_seconds = 1.0; io_total_bytes = 10; metrics_known = $true; cpu_delta_seconds = 0.0; io_delta_bytes = 0; descendants = @(101) }
$child2 = @{ pid = 102; ppid = 101; name = 'node.exe'; executable = 'C:\Program Files\nodejs\node.exe'; created_unix = 102; cpu_total_seconds = 1.0; io_total_bytes = 10; metrics_known = $true; cpu_delta_seconds = 0.0; io_delta_bytes = 0; descendants = @(102) }
$snapshot = Join-Path $work 'snapshot.json'
Write-Snapshot $snapshot @($orphan, $child1, $child2)

Write-Output '--- report-only: never advances kill confirmation ---'
$reportOnly = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -NowUnix 900 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 | ConvertFrom-Json
Check 'report-only sees candidate' ($reportOnly.candidates -eq 1)
Check 'report-only writes no confirmation state' (-not (Test-Path $state))

Write-Output '--- first apply observation: record only ---'
$first = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 1000 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 -MinObservations 3 -Apply | ConvertFrom-Json
Check 'first observation reports candidate' ($first.candidates -eq 1)
Check 'first observation reaps nothing' ($first.reaped -eq 0)
Check 'first observation writes no kill request' (-not (Test-Path $killLog))

Write-Output '--- second observation: still grace ---'
$second = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 1301 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 -MinObservations 3 -Apply | ConvertFrom-Json
Check 'second observation still does not reap' ($second.reaped -eq 0)

Write-Output '--- third observation: confirmed orphan ---'
$third = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 1602 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 -MinObservations 3 -Apply | ConvertFrom-Json
Check 'third observation reaps exact root' ($third.reaped -eq 1)
Check 'kill recorder exists' (Test-Path $killLog)
$killRows = @(Get-Content $killLog | ForEach-Object { $_ | ConvertFrom-Json })
Check 'only orphan root requested' (($killRows.Count -eq 1) -and ($killRows[0].pid -eq 100))
Check 'exact tree requested' ((@($killRows[0].descendants) -join ',') -eq '100,101,102')
Check 'evidence snapshot written' ((Get-ChildItem $evidence -Filter '*.json' -File).Count -eq 1)

Write-Output '--- active orphan: never reap ---'
Remove-Item $state -Force -ErrorAction SilentlyContinue
Remove-Item $killLog -Force -ErrorAction SilentlyContinue
$active = $orphan.Clone()
$active.io_delta_bytes = 1
Write-Snapshot $snapshot @($active, $child1, $child2)
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 2000 -Apply | Out-Null
$activeResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 2400 -Apply | ConvertFrom-Json
Check 'active orphan not candidate' ($activeResult.candidates -eq 0)
Check 'active orphan not reaped' ($activeResult.reaped -eq 0)

Write-Output '--- between-run activity resets confirmation ---'
Remove-Item $state -Force -ErrorAction SilentlyContinue
Remove-Item $killLog -Force -ErrorAction SilentlyContinue
$quiet = $orphan.Clone()
Write-Snapshot $snapshot @($quiet, $child1, $child2)
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 2500 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 -MinObservations 3 -Apply | Out-Null
$worked = $orphan.Clone()
$worked.cpu_total_seconds = 11.0
Write-Snapshot $snapshot @($worked, $child1, $child2)
$workedResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 2801 -MinOrphanAgeMinutes 5 -ConfirmationSeconds 300 -MinObservations 3 -Apply | ConvertFrom-Json
Check 'inter-run CPU activity does not reap' ($workedResult.reaped -eq 0)
$stateAfterWork = Get-Content $state -Raw | ConvertFrom-Json
$candidateAfterWork = @($stateAfterWork.candidates.PSObject.Properties)[0].Value
Check 'inter-run CPU activity resets observations' ($candidateAfterWork.observations -eq 1)

Write-Output '--- live parent: never candidate ---'
$parent = @{ pid = 999; ppid = 1; name = 'pwsh.exe'; executable = 'C:\Program Files\PowerShell\7\pwsh.exe'; created_unix = 50; cpu_delta_seconds = 0.0; descendants = @(999) }
Write-Snapshot $snapshot @($orphan, $child1, $child2, $parent)
$parentResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 3000 -Apply | ConvertFrom-Json
Check 'live parent excludes root' ($parentResult.candidates -eq 0)

Write-Output '--- wrong executable: never candidate ---'
$wrong = $orphan.Clone()
$wrong.executable = 'C:\Program Files\nodejs\node.exe'
Write-Snapshot $snapshot @($wrong, $child1, $child2)
$wrongResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 4000 -Apply | ConvertFrom-Json
Check 'wrong executable excludes root' ($wrongResult.candidates -eq 0)

Write-Output '--- missing creation time: fail closed ---'
$noCreation = $orphan.Clone()
$noCreation.created_unix = 0
Write-Snapshot $snapshot @($noCreation, $child1, $child2)
$creationResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 4500 -Apply | ConvertFrom-Json
Check 'missing creation time excludes root' ($creationResult.candidates -eq 0)

Write-Output '--- unknown process metrics: fail closed ---'
$unknownMetrics = $orphan.Clone()
$unknownMetrics.metrics_known = $false
Write-Snapshot $snapshot @($unknownMetrics, $child1, $child2)
$metricsResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 4700 -Apply | ConvertFrom-Json
Check 'unknown process metrics excludes root' ($metricsResult.candidates -eq 0)

Write-Output '--- stale child PPID: exclude predating child ---'
Remove-Item $state -Force -ErrorAction SilentlyContinue
Remove-Item $killLog -Force -ErrorAction SilentlyContinue
$staleChild = $child1.Clone()
$staleChild.created_unix = 99
Write-Snapshot $snapshot @($orphan, $staleChild, $child2)
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 5000 -MinObservations 3 -ConfirmationSeconds 300 -Apply | Out-Null
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 5301 -MinObservations 3 -ConfirmationSeconds 300 -Apply | Out-Null
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 5602 -MinObservations 3 -ConfirmationSeconds 300 -Apply | Out-Null
$staleRows = @(Get-Content $killLog | ForEach-Object { $_ | ConvertFrom-Json })
Check 'predating child is excluded from kill tree' ((@($staleRows[0].descendants) -join ',') -eq '100')

Write-Output '--- PID reuse: confirmation resets ---'
Remove-Item $state -Force -ErrorAction SilentlyContinue
$firstSeen = $orphan.Clone()
Write-Snapshot $snapshot @($firstSeen, $child1, $child2)
& $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 5000 -Apply | Out-Null
$reused = $orphan.Clone()
$reused.created_unix = 4999
Write-Snapshot $snapshot @($reused, $child1, $child2)
$reuseResult = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 5400 -Apply | ConvertFrom-Json
Check 'PID reuse does not inherit confirmation' ($reuseResult.reaped -eq 0)

Write-Output '--- real exact-PID kill path: disposable sleeper ---'
$fakeDir = Join-Path $work 'cursor-agent\versions\fixture'
New-Item -ItemType Directory -Force -Path $fakeDir | Out-Null
$fakeNode = Join-Path $fakeDir 'node.exe'
Copy-Item -LiteralPath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Destination $fakeNode
$sleeper = $null
try {
    $sleeper = Start-Process -FilePath $fakeNode -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 120' -PassThru
    Start-Sleep -Seconds 1
    $sleeperCim = Get-CimInstance Win32_Process -Filter "ProcessId=$($sleeper.Id)"
    $created = ([DateTimeOffset]$sleeperCim.CreationDate).ToUnixTimeSeconds()
    $metric = Get-Process -Id $sleeper.Id
    $realRow = @{
        pid = $sleeper.Id
        ppid = 999999
        name = 'node.exe'
        executable = $sleeperCim.ExecutablePath
        created_unix = $created
        cpu_total_seconds = [double]$metric.CPU
        io_total_bytes = [long]$sleeperCim.ReadTransferCount + [long]$sleeperCim.WriteTransferCount
        metrics_known = $true
        cpu_delta_seconds = 0.0
        io_delta_bytes = 0
        descendants = @($sleeper.Id)
    }
    $realSnapshot = Join-Path $work 'real-snapshot.json'
    $realState = Join-Path $work 'real-state.json'
    Write-Snapshot $realSnapshot @($realRow)
    & $script -ProcessSnapshotFile $realSnapshot -StateFile $realState -EvidenceRoot $evidence -NowUnix ($created + 3600) -MinOrphanAgeMinutes 0 -ConfirmationSeconds 0 -MinObservations 3 -MaxTreeCpuDeltaSeconds 100 -MaxTreeIoDeltaBytes 999999999 -Apply | Out-Null
    & $script -ProcessSnapshotFile $realSnapshot -StateFile $realState -EvidenceRoot $evidence -NowUnix ($created + 3601) -MinOrphanAgeMinutes 0 -ConfirmationSeconds 0 -MinObservations 3 -MaxTreeCpuDeltaSeconds 100 -MaxTreeIoDeltaBytes 999999999 -Apply | Out-Null
    $realResult = & $script -ProcessSnapshotFile $realSnapshot -StateFile $realState -EvidenceRoot $evidence -NowUnix ($created + 3602) -MinOrphanAgeMinutes 0 -ConfirmationSeconds 0 -MinObservations 3 -MaxTreeCpuDeltaSeconds 100 -MaxTreeIoDeltaBytes 999999999 -Apply | ConvertFrom-Json
    Check 'real kill path reports one reaped tree' ($realResult.reaped -eq 1)
    Check 'disposable sleeper is gone' (-not (Get-Process -Id $sleeper.Id -ErrorAction SilentlyContinue))
}
finally {
    if ($sleeper -and (Get-Process -Id $sleeper.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $sleeper.Id -Force
    }
}

Write-Output '--- malformed state: fail closed, no kill ---'
'{not-json' | Set-Content -LiteralPath $state -Encoding utf8
Remove-Item $killLog -Force -ErrorAction SilentlyContinue
$malformedOutput = & $script -ProcessSnapshotFile $snapshot -StateFile $state -EvidenceRoot $evidence -KillRecorderFile $killLog -NowUnix 6000 -Apply
$malformedExit = $LASTEXITCODE
Check 'malformed state exits nonzero' ($malformedExit -eq 1)
Check 'malformed state emits error status' (($malformedOutput | ConvertFrom-Json).status -eq 'error')
Check 'malformed state performs no kill' (-not (Test-Path $killLog))

$scriptText = Get-Content -LiteralPath $script -Raw
Check 'no kill-by-name' ($scriptText -notmatch '(?i)/IM\s+node|Stop-Process\s+.*-Name')
Check 'no taskkill tree discovery flag' ($scriptText -notmatch '(?i)taskkill\.exe[^\r\n]*/T')

$resourceGuard = Join-Path $PSScriptRoot 'resource-guard.ps1'
$guardText = Get-Content -LiteralPath $resourceGuard -Raw
Check 'resource guard invokes orphan micro-guard' ($guardText -match 'cursor-orphan-reaper\.ps1')
Check 'resource guard has explicit reap switch' ($guardText -match 'ReapOrphanCursorAgents')
Check 'resource guard runs canonical tested reaper' ($guardText -match [regex]::Escape('C:\Users\Prekzursil\.agents\scripts\agentic-perfection\cursor-orphan-reaper.ps1'))
Check 'resource guard state is under protected runtime root' ($guardText -match [regex]::Escape('C:\Users\Prekzursil\.agent-guard\resource-guard\state\cursor-orphan-reaper.state.json'))
Check 'resource guard evidence is under protected runtime root' ($guardText -match [regex]::Escape('C:\Users\Prekzursil\.agent-guard\resource-guard\evidence'))
Check 'resource guard own state is protected' ($guardText -match [regex]::Escape('C:\Users\Prekzursil\.agent-guard\resource-guard\state\resource-guard.state.json'))
Check 'resource guard log is protected' ($guardText -match [regex]::Escape('C:\Users\Prekzursil\.agent-guard\resource-guard\log\resource-guard.log'))

$stub = Join-Path $work 'stub-reaper.ps1'
$stubMarker = Join-Path $work 'stub-marker.txt'
@'
param(
    [string]$StateFile,
    [string]$EvidenceRoot,
    [switch]$Apply
)
Set-Content -LiteralPath $env:CURSOR_ORPHAN_STUB_MARKER -Value ([string][bool]$Apply)
'{"status":"success","reaped":0}'
exit 0
'@ | Set-Content -LiteralPath $stub -Encoding utf8
$env:CURSOR_ORPHAN_STUB_MARKER = $stubMarker
$guardLog = Join-Path $work 'resource-guard.log'
& $resourceGuard -OrphanReaper $stub -ReapOrphanCursorAgents `
    -LogFile $guardLog -DigestFile (Join-Path $work 'digest.md') `
    -StateFile (Join-Path $work 'guard-state.json') `
    -FreeRamGbOverride 99 -CUsedPctOverride 1 -CFreeGbOverride 999 `
    -DupProcsOverride 0 -SemgrepMbOverride 0
Check 'PowerShell 5 resource guard passes Apply switch' ((Get-Content $stubMarker -Raw).Trim() -eq 'True')
Check 'resource guard records successful reaper call' ((Get-Content $guardLog -Raw) -match 'ORPHAN-GUARD exit=0 apply=1')

Remove-Item $stubMarker -Force -ErrorAction SilentlyContinue
& $resourceGuard -OrphanReaper $stub `
    -OrphanStateFile (Join-Path $work 'orphan-state.json') `
    -OrphanEvidenceRoot (Join-Path $work 'orphan-evidence') `
    -LogFile $guardLog -DigestFile (Join-Path $work 'digest.md') `
    -StateFile (Join-Path $work 'guard-state.json') `
    -FreeRamGbOverride 99 -CUsedPctOverride 1 -CFreeGbOverride 999 `
    -DupProcsOverride 0 -SemgrepMbOverride 0
Check 'resource guard defaults to report-only' ((Get-Content $stubMarker -Raw).Trim() -eq 'False')
Remove-Item Env:CURSOR_ORPHAN_STUB_MARKER -ErrorAction SilentlyContinue

Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue

if ($fails.Count) {
    Write-Output ("FAILED ({0}): {1}" -f $fails.Count, ($fails -join ', '))
    exit 1
}
Write-Output 'SUCCESS:cursor-orphan-reaper-tests'
exit 0
