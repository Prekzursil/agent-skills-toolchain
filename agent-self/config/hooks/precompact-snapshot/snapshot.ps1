#requires -Version 5
# PreCompact hook: preserve volatile context before the model's history is compacted.
#  1) Append a recovery breadcrumb (trigger + transcript path) to a global JSONL log.
#  2) Snapshot the project's .remember/now.md scratch buffer into .remember/tmp/.
# Quiet by design: emits {"suppressOutput": true} so nothing clutters the transcript.

$ErrorActionPreference = 'SilentlyContinue'

$raw     = [Console]::In.ReadToEnd()
$ts      = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
$trigger = 'unknown'
$sid     = ''
$cwd     = (Get-Location).Path
$tpath   = ''

if ($raw) {
    try {
        $j = $raw | ConvertFrom-Json
        if ($j.trigger)         { $trigger = $j.trigger }
        if ($j.session_id)      { $sid     = $j.session_id }
        if ($j.cwd)             { $cwd     = $j.cwd }
        if ($j.transcript_path) { $tpath   = $j.transcript_path }
    } catch {}
}

# 1) Global compaction log — searchable across every project.
$entry = [pscustomobject]@{
    ts              = $ts
    trigger         = $trigger
    session_id      = $sid
    cwd             = $cwd
    transcript_path = $tpath
}
($entry | ConvertTo-Json -Compress) |
    Out-File -FilePath 'C:/Users/Prekzursil/.claude/compaction-log.jsonl' -Append -Encoding utf8

# 2) Snapshot the volatile remember buffer if this project has one.
$now = Join-Path $cwd '.remember/now.md'
if (Test-Path $now) {
    $snapDir = Join-Path $cwd '.remember/tmp'
    if (-not (Test-Path $snapDir)) { New-Item -ItemType Directory -Path $snapDir -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    # The session id goes in the FILENAME, not just the JSONL log. Without it the restore
    # side cannot tell whose snapshot it is and falls back to "newest globally" — which
    # injected one session's pre-compaction context into a different session. A snapshot
    # with no session id is written un-matchable on purpose: losing a recovery is a far
    # smaller harm than steering another session with foreign context.
    $sidTag = if ($sid) { ($sid -replace '[^A-Za-z0-9]', '').Substring(0, [Math]::Min(16, ($sid -replace '[^A-Za-z0-9]', '').Length)) } else { 'nosession' }
    Copy-Item $now (Join-Path $snapDir "precompact-$sidTag-$stamp.md") -Force
    # Keep only the 40 most recent snapshots.
    Get-ChildItem $snapDir -Filter 'precompact-*.md' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 40 |
        Remove-Item -Force
}

'{"suppressOutput": true}'
