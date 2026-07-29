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
    # Deduplicate before admitting the body. Test-Path above is the ONLY admission test,
    # so a PreCompact firing repeatedly on an UNCHANGED buffer copied the whole thing every
    # time: measured 4 invocations of a 93.8 KB now.md => 4 files, 1 distinct hash, 375 KB.
    # At this buffer's observed 774 KB that is ~30 MB of identical bodies, and every
    # duplicate burns a slot of the shared 40-entry ring below, evicting another session's
    # only recovery point. Skip the write when this session's newest snapshot already
    # holds identical content; the restore side finds that copy just as well.
    $prev = Get-ChildItem $snapDir -Filter "precompact-$sidTag-*.md" |
            Sort-Object CreationTime -Descending | Select-Object -First 1
    $isDup = $false
    if ($prev -and $prev.Length -eq (Get-Item $now).Length) {
        $prevHash = (Get-FileHash $prev.FullName -Algorithm SHA256).Hash
        $nowHash  = (Get-FileHash $now -Algorithm SHA256).Hash
        $isDup    = ($prevHash -and $nowHash -and $prevHash -eq $nowHash)
    }
    if (-not $isDup) {
        Copy-Item $now (Join-Path $snapDir "precompact-$sidTag-$stamp.md") -Force
    }
    # Keep only the 40 most recently CAPTURED snapshots. Order on CreationTime, NOT
    # LastWriteTime: Copy-Item preserves the SOURCE's LastWriteTime, so every snapshot
    # inherits now.md's edit time rather than its own capture time. Measured with capture
    # order FRESH-then-STALE (stale = a session whose buffer was last edited 10 days ago
    # but which compacted last): ordering by LastWriteTime evicted STALE, i.e. the NEWEST
    # snapshot, while CreationTime correctly evicted FRESH. The read-back side is
    # session-scoped (harness-trim/compact-restore.ps1:20), so the session whose snapshot
    # was wrongly evicted recovers nothing at all.
    Get-ChildItem $snapDir -Filter 'precompact-*.md' |
        Sort-Object CreationTime -Descending |
        Select-Object -Skip 40 |
        Remove-Item -Force
}

'{"suppressOutput": true}'
