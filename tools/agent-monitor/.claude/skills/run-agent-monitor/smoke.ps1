#requires -Version 5
<#
  Deterministic, side-effect-free smoke driver for agent-monitor.

  Drives BOTH binaries against a committed fixture transcript (no live Claude
  session, NO window-spawning):
    [1] agent_monitor.py --dir <fixture\subagents>  -> one-shot dashboard table
    [2] tail_once.py <fixture jsonl>                 -> agent_tail.render() backfill

  Asserts on OUTPUT CONTENT (a row whose body printed 'fixture-agent'; a tool
  line that rendered 'echo hello'), not just exit codes - a malformed transcript
  would still exit 0 but print the wrong thing.

  We touch the fixture's mtime to now first, so the monitor's "RUNNING"
  detection (jsonl mtime within --active-secs, default 150s) fires deterministically.
#>
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'   # box-drawing + emoji glyphs in the table/feed

$root  = (Resolve-Path "$PSScriptRoot\..\..\..").Path          # D:\agent-monitor
$fix   = Join-Path $PSScriptRoot 'fixture\subagents'
$jsonl = Join-Path $fix 'agent-deadbeef.jsonl'
$tail1 = Join-Path $PSScriptRoot 'tail_once.py'

foreach ($p in @("$root\agent_monitor.py", $jsonl, $tail1)) {
    if (-not (Test-Path $p)) { throw "missing required file: $p" }
}

# Force the fixture to read as RUNNING (mtime within the recency window).
(Get-Item $jsonl).LastWriteTime = Get-Date

Push-Location $root
try {
    Write-Host "[1/2] agent_monitor.py --dir <fixture> (one-shot dashboard)" -ForegroundColor Cyan
    $mon = & python agent_monitor.py --dir $fix --active-secs 99999 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "agent_monitor.py exited $LASTEXITCODE" }
    Write-Host $mon
    if ($mon -notmatch 'fixture-agent') { throw "dashboard did not render the fixture agent row" }
    if ($mon -notmatch '1 running')     { throw "fixture agent was not counted as running" }

    Write-Host "[2/2] tail_once.py <fixture jsonl> (agent_tail.render backfill)" -ForegroundColor Cyan
    $tl = & python $tail1 $jsonl 5 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "tail_once.py exited $LASTEXITCODE" }
    Write-Host $tl
    if ($tl -notmatch 'fixture-agent') { throw "tail header missing agent name" }
    if ($tl -notmatch 'echo hello')    { throw "tail did not render the tool_use command (render path broken)" }

    Write-Host "OK: agent-monitor verified (dashboard + transcript render against fixture)." -ForegroundColor Green
}
finally {
    Pop-Location
}
