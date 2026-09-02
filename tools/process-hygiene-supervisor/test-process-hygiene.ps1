#requires -Version 5.1
<#
  Manual smoke test for process-hygiene.ps1 (needs python + hygiene.py present).
  Not run in CI (CI has no pwsh); the Python decision/actuation logic is covered
  by tests/ at 100%. This proves the PowerShell glue end-to-end on Windows:

    1. the LIVE sampler (Get-HygieneSnapshot) emits a snapshot hygiene.py accepts,
       INCLUDING the fields the newer rules need (connections for the network
       veto, wsl.docker_desktop_running / wsl.client_count for the idle gate);
    2. a scripted snapshot flows through the launcher and writes the ledger;
    3. report-only kills nothing; -Apply against absent fake PIDs is a safe no-op
       (the actuator cannot open the PID -> "vanished");
    4. an ESTABLISHED remote socket defers an otherwise-reapable orphan;
    5. a REAL spawned process is killed through the pinned-handle Win32 path,
       the ledger says `forced`, -DigestFile gets exactly one line, heartbeat written;
    6. a snapshot naming a live pid with a STALE creation time (PID reuse) is
       refused as identity-changed - the test's own process is the bait.

  Run:  pwsh -File test-process-hygiene.ps1
#>
param(
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'process-hygiene.ps1'
$fails = @()

if (-not $Python) {
    # (no `?.` - that is PowerShell 7 syntax and this file declares 5.1)
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    $Python = if ($cmd) { $cmd.Source } else { 'C:\Python314\python.exe' }
}

function Check([string]$Name, [bool]$Condition) {
    if ($Condition) { Write-Output "PASS: $Name" } else { Write-Output "FAIL: $Name"; $script:fails += $Name }
}

$work = Join-Path $env:TEMP ("process-hygiene-test-{0}" -f [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work | Out-Null
$policy = Join-Path $work 'policy.json'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'policy.example.json') -Destination $policy
$state = Join-Path $work 'state.json'
$ledger = Join-Path $work 'ledger.jsonl'

# 1) LIVE sampler must emit a snapshot hygiene.py validates.
$liveSnap = Join-Path $work 'live-snapshot.json'
& $launcher -EmitSnapshotOnly -SnapshotOut $liveSnap -Python $Python | Out-Null
$validate = & $Python (Join-Path $PSScriptRoot 'hygiene.py') validate-snapshot --snapshot $liveSnap
Check 'live sampler emits a valid snapshot' (($validate -join '') -match 'SUCCESS:process-hygiene-snapshot')
$live = Get-Content -LiteralPath $liveSnap -Raw | ConvertFrom-Json
Check 'live snapshot carries the wsl idle-shutdown gates' (
    ($null -ne $live.wsl.docker_desktop_running) -and ($null -ne $live.wsl.client_count))
Check 'live snapshot carries connections for the network veto' ($null -ne $live.connections)
Check 'live snapshot carries the pagefile block for the commit-ceiling rule' (
    ($null -ne $live.host.pagefile) -and ($null -ne $live.host.pagefile.automatic))
Check 'live connections look like pid/remote pairs' (
    (@($live.connections).Count -eq 0) -or
    (($null -ne @($live.connections)[0].pid) -and (@($live.connections)[0].remote -match ':')))

# 2) scripted snapshot: a retired AgentBridge bridge under a live grok + a
#    protected auth2api orphan. Report-only must record dry-run and touch nothing.
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$snapshot = [ordered]@{
    schema          = 'process-hygiene-snapshot-v1'
    taken_unix      = $now
    host            = [ordered]@{ physical_bytes = 33GB; free_bytes = 3GB; commit_total_bytes = 60GB; commit_limit_bytes = 64GB; compressed_bytes = 9GB }
    wsl             = [ordered]@{ available = $true; running_distros = @(); docker_desktop_running = $false; client_count = 0 }
    listeners       = @(@{ port = 8317; pid = 401 })
    connections     = @()
    supervisor_pids = @()
    processes       = @(
        [ordered]@{ pid = 200; ppid = 1; name = 'grok.exe'; executable = 'C:\Users\x\.local\bin\grok.exe'; command_line = 'grok'; created_unix = ($now - 3000); cpu_seconds = 1.0; io_bytes = 10; working_set_bytes = 100MB; private_bytes = 130MB },
        [ordered]@{ pid = 300; ppid = 200; name = 'node.exe'; executable = 'C:\Program Files\nodejs\node.exe'; command_line = 'node C:\Users\x\AppData\Roaming\npm\node_modules\@raysonmeng\agentbridge\dist\bridge-server.js'; created_unix = ($now - 1000); cpu_seconds = 1.0; io_bytes = 10; working_set_bytes = 150MB; private_bytes = 150MB },
        [ordered]@{ pid = 401; ppid = 9999; name = 'node.exe'; executable = 'C:\Program Files\nodejs\node.exe'; command_line = 'node C:\Users\x\Cowork\tools\auth2api\dist\index.js'; created_unix = ($now - 380000); cpu_seconds = 1.0; io_bytes = 10; working_set_bytes = 200MB; private_bytes = 200MB }
    )
}
$snapFile = Join-Path $work 'scripted.json'
$snapshot | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $snapFile -Encoding utf8

$reportOut = & $launcher -ProcessSnapshotFile $snapFile -PolicyFile $policy -StateFile $state -LedgerFile $ledger -ReaperAvailable no -Python $Python
$reportCode = $LASTEXITCODE
Check 'report-only exits 0' ($reportCode -eq 0)
Check 'report-only prints SUCCESS' (($reportOut -join '') -match 'SUCCESS:process-hygiene')
$rows = @(Get-Content $ledger | ForEach-Object { $_ | ConvertFrom-Json })
Check 'retired bridge is a dry-run stop' (@($rows | Where-Object { $_.rule -eq 'retired' -and $_.result -eq 'dry-run' }).Count -ge 1)
Check 'auth2api is never in a stop row' (@($rows | Where-Object { $_.action -eq 'stop' -and $_.pid -eq 401 }).Count -eq 0)

# 3) -Apply against fake absent PIDs is a safe no-op (actuator sees them gone).
Remove-Item $state, $ledger -Force -ErrorAction SilentlyContinue
$applyOut = & $launcher -ProcessSnapshotFile $snapFile -PolicyFile $policy -StateFile $state -LedgerFile $ledger -ReaperAvailable no -Apply -Python $Python
Check 'apply run exits 0 or 2' (($LASTEXITCODE -eq 0) -or ($LASTEXITCODE -eq 2))
$applyRows = @(Get-Content $ledger | ForEach-Object { $_ | ConvertFrom-Json })
Check 'apply recorded the retired bridge outcome' (@($applyRows | Where-Object { $_.rule -eq 'retired' -and $_.pid -eq 300 }).Count -ge 1)
Check 'apply still never targeted auth2api' (@($applyRows | Where-Object { $_.action -eq 'stop' -and $_.pid -eq 401 }).Count -eq 0)

# 4) an ESTABLISHED remote socket must DEFER the reapable orphan (network veto).
#    The orphan is a plain node.exe with a parentless ppid, observed 4x idle.
Remove-Item $state, $ledger -Force -ErrorAction SilentlyContinue
$vetoSnapshotFile = Join-Path $work 'veto.json'
for ($i = 0; $i -lt 4; $i++) {
    $veto = [ordered]@{
        schema          = 'process-hygiene-snapshot-v1'
        taken_unix      = ($now + ($i * 300))
        host            = [ordered]@{ physical_bytes = 33GB; free_bytes = 3GB; commit_total_bytes = 60GB; commit_limit_bytes = 64GB }
        wsl             = [ordered]@{ available = $false; running_distros = @() }
        listeners       = @()
        connections     = @(@{ pid = 500; remote = '52.10.20.30:443' })
        supervisor_pids = @()
        processes       = @(
            [ordered]@{ pid = 500; ppid = 9999; name = 'node.exe'; executable = 'C:\Program Files\nodejs\node.exe'; command_line = 'node C:\srv\worker.js'; created_unix = ($now - 40000); cpu_seconds = 1.0; io_bytes = 10; working_set_bytes = 100MB; private_bytes = 100MB }
        )
    }
    $veto | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $vetoSnapshotFile -Encoding utf8
    & $launcher -ProcessSnapshotFile $vetoSnapshotFile -PolicyFile $policy -StateFile $state -LedgerFile $ledger -ReaperAvailable no -Python $Python | Out-Null
}
$vetoRows = @(Get-Content $ledger | ForEach-Object { $_ | ConvertFrom-Json })
Check 'network veto defers the orphan' (
    @($vetoRows | Where-Object { $_.rule -eq 'orphan' -and $_.detail.network_veto -eq $true }).Count -ge 1)
Check 'network-vetoed orphan has no dry-run stop row' (
    @($vetoRows | Where-Object { $_.rule -eq 'orphan' -and $_.action -eq 'stop' }).Count -eq 0)

# 5) A REAL kill through the pinned-handle path. Spawn a harmless python sleeper
#    whose command line carries the retired AgentBridge tokens, snapshot it LIVE
#    (real pid / creation time / executable, so the identity check must agree with
#    the handle), and -Apply. This is the only place the Win32 OpenProcess ->
#    GetProcessTimes -> TerminateProcess -> WaitForSingleObject chain runs for real.
Remove-Item $state, $ledger -Force -ErrorAction SilentlyContinue
$digest = Join-Path $work 'BACKGROUND-DIGEST.md'
$victim = Start-Process -FilePath $Python -PassThru -WindowStyle Hidden -ArgumentList @(
    '-c', '"import time; time.sleep(600)  # agentbridge bridge-server smoke-test victim"')
try {
    Start-Sleep -Milliseconds 800
    $vcim = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $victim.Id) -ErrorAction Stop
    Check 'victim is alive before the run' ($null -ne $vcim)
    $victimSnap = [ordered]@{
        schema          = 'process-hygiene-snapshot-v1'
        taken_unix      = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        host            = [ordered]@{ physical_bytes = 33GB; free_bytes = 8GB; commit_total_bytes = 20GB; commit_limit_bytes = 64GB }
        wsl             = [ordered]@{ available = $false; running_distros = @() }
        listeners       = @()
        connections     = @()
        supervisor_pids = @([int]$PID)
        processes       = @(
            [ordered]@{
                pid = [int]$victim.Id; ppid = [int]$vcim.ParentProcessId; name = 'python.exe'
                executable = [string]$vcim.ExecutablePath; command_line = [string]$vcim.CommandLine
                created_unix = ([DateTimeOffset]$vcim.CreationDate).ToUnixTimeSeconds()
                cpu_seconds = 0.1; io_bytes = 0; working_set_bytes = 20MB; private_bytes = 20MB
            }
        )
    }
    $victimFile = Join-Path $work 'victim.json'
    $victimSnap | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $victimFile -Encoding utf8
    $killOut = & $launcher -ProcessSnapshotFile $victimFile -PolicyFile $policy -StateFile $state -LedgerFile $ledger -ReaperAvailable no -Apply -DigestFile $digest -Python $Python
    Check 'real-kill run exits 0' ($LASTEXITCODE -eq 0)
    Start-Sleep -Milliseconds 300
    Check 'victim is gone after the run' ($null -eq (Get-Process -Id $victim.Id -ErrorAction SilentlyContinue))
    $killRows = @(Get-Content $ledger | ForEach-Object { $_ | ConvertFrom-Json })
    Check 'ledger records the victim as forced on the pinned handle' (
        @($killRows | Where-Object { $_.rule -eq 'retired' -and $_.pid -eq $victim.Id -and $_.result -eq 'forced' }).Count -eq 1)
    Check 'digest line written once on a kill' (
        (Test-Path -LiteralPath $digest) -and (@(Get-Content $digest).Count -eq 1))
    Check 'digest names the tool, the rule and proposes a next step' (
        (Test-Path -LiteralPath $digest) -and ((Get-Content $digest -Raw) -match '\[process-hygiene\] stopped 1 tree\(s\) \[retired\].*PROPOSE:'))
    $heartbeat = Join-Path (Split-Path -Parent $state) 'heartbeat.json'
    Check 'heartbeat written next to the state file' (Test-Path -LiteralPath $heartbeat)
    Check 'heartbeat records the apply mode' (
        (Test-Path -LiteralPath $heartbeat) -and
        ((Get-Content -LiteralPath $heartbeat -Raw | ConvertFrom-Json).apply -eq $true))
}
finally {
    Stop-Process -Id $victim.Id -Force -ErrorAction SilentlyContinue
}

# 6) PID-reuse guard for real: a snapshot naming THIS test's own pid but with a
#    stale creation time must be refused as identity-changed, not killed.
Remove-Item $state, $ledger -Force -ErrorAction SilentlyContinue
$selfCim = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $PID)
$reuseSnap = [ordered]@{
    schema          = 'process-hygiene-snapshot-v1'
    taken_unix      = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    host            = [ordered]@{ physical_bytes = 33GB; free_bytes = 8GB; commit_total_bytes = 20GB; commit_limit_bytes = 64GB }
    wsl             = [ordered]@{ available = $false; running_distros = @() }
    listeners       = @()
    connections     = @()
    supervisor_pids = @()
    processes       = @(
        [ordered]@{
            pid = [int]$PID; ppid = 99999; name = 'pwsh.exe'
            executable = [string]$selfCim.ExecutablePath
            command_line = 'node agentbridge bridge-server (stale identity on purpose)'
            created_unix = (([DateTimeOffset]$selfCim.CreationDate).ToUnixTimeSeconds() - 7200)
            cpu_seconds = 0.1; io_bytes = 0; working_set_bytes = 20MB; private_bytes = 20MB
        }
    )
}
$reuseFile = Join-Path $work 'reuse.json'
$reuseSnap | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reuseFile -Encoding utf8
& $launcher -ProcessSnapshotFile $reuseFile -PolicyFile $policy -StateFile $state -LedgerFile $ledger -ReaperAvailable no -Apply -Python $Python | Out-Null
$reuseRows = @(Get-Content $ledger | ForEach-Object { $_ | ConvertFrom-Json })
Check 'a recycled pid with a stale creation time is refused, not killed' (
    @($reuseRows | Where-Object { $_.pid -eq $PID -and $_.result -eq 'identity-changed' }).Count -eq 1)
Check 'this test process is still alive (it obviously is, but the ledger must agree)' (
    @($reuseRows | Where-Object { $_.pid -eq $PID -and $_.result -in @('forced', 'graceful') }).Count -eq 0)

Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue

if ($fails.Count) {
    Write-Output ("FAILED ({0}): {1}" -f $fails.Count, ($fails -join ', '))
    exit 1
}
Write-Output 'SUCCESS:process-hygiene-launcher-tests'
exit 0
