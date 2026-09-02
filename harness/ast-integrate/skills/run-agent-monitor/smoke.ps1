#requires -Version 5
<#
  Deterministic, side-effect-free smoke driver for run-agent-monitor.

  Drives the surviving monitorcore surface against a committed fixture transcript
  (no live Claude session, NO window-spawning):
    [1] monitorcore.discovery.scan(<fixture\subagents>)  -> discovers the flat Task agent
    [2] tail_once.py <fixture jsonl>                      -> agent_tail.render() backfill

  Asserts on OUTPUT CONTENT (a discovered row named 'fixture-agent', RUNNING; a tail line
  that rendered 'echo hello'), not just exit codes.

  monitorcore is vendored inside the sibling workflow-monitor skill, so PYTHONPATH points
  there. We touch the fixture's mtime to now first, so scan's "running" detection fires.
#>
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'

$fix   = Join-Path $PSScriptRoot 'fixture\subagents'
$jsonl = Join-Path $fix 'agent-deadbeef.jsonl'
$tail1 = Join-Path $PSScriptRoot 'tail_once.py'
$wfmon = (Resolve-Path (Join-Path $PSScriptRoot '..\workflow-monitor')).Path

foreach ($p in @($jsonl, $tail1)) {
    if (-not (Test-Path $p)) { throw "missing required file: $p" }
}
$env:PYTHONPATH = $wfmon

# Force the fixture to read as RUNNING (mtime within the recency window).
(Get-Item $jsonl).LastWriteTime = Get-Date

Write-Host "[1/2] monitorcore.discovery.scan(<fixture>)" -ForegroundColor Cyan
# Print ASCII fields only (name/running/type) — the 'last' field's glyphs crash a cp1252 pipe.
$scan = & python -c "import sys, monitorcore.discovery as d; r = d.scan(sys.argv[1], 99999, 120)[0]; sys.stdout.write(r['name'] + ' ' + str(r['running']) + ' ' + r['type'])" $fix 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "discovery.scan exited $LASTEXITCODE" }
Write-Host $scan
if ($scan -notmatch 'fixture-agent') { throw "scan did not discover the fixture agent" }
if ($scan -notmatch 'True')          { throw "fixture agent was not counted as running" }

Write-Host "[2/2] tail_once.py <fixture jsonl> (agent_tail.render backfill)" -ForegroundColor Cyan
$tl = & python $tail1 $jsonl 5 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "tail_once.py exited $LASTEXITCODE" }
Write-Host $tl
if ($tl -notmatch 'fixture-agent') { throw "tail header missing agent name" }
if ($tl -notmatch 'echo hello')    { throw "tail did not render the tool_use command (render path broken)" }

Write-Host "OK: run-agent-monitor verified (discovery + transcript render against fixture)." -ForegroundColor Green
