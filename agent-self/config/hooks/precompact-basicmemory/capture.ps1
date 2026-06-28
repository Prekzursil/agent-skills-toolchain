#requires -Version 5
<#
  PreCompact hook → basic-memory.
  Before the conversation is compacted, write a SEARCHABLE checkpoint note into the
  basic-memory vault (D:\basic-memory\compaction-checkpoints\). basic-memory's watcher
  indexes it (FTS + vector embedding) so the context is recoverable by semantic search
  long after compaction summarized it away.

  Complements the existing precompact-snapshot hook (which mirrors .remember/now.md to
  .remember/tmp/). This one makes the state queryable across ALL time and projects.

  Quiet by design: emits {"suppressOutput": true}.
#>
$ErrorActionPreference = 'SilentlyContinue'

$raw     = [Console]::In.ReadToEnd()
$ts      = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$trigger = 'unknown'; $sid = ''; $cwd = (Get-Location).Path; $tpath = ''
if ($raw) { try {
    $j = $raw | ConvertFrom-Json
    if ($j.trigger)         { $trigger = $j.trigger }
    if ($j.session_id)      { $sid     = $j.session_id }
    if ($j.cwd)             { $cwd     = $j.cwd }
    if ($j.transcript_path) { $tpath   = $j.transcript_path }
} catch {} }

$project = Split-Path $cwd -Leaf

# --- Gather substance ---------------------------------------------------------
# 1) The project's live work buffer (richest distilled state).
$nowContent = ''
$now = Join-Path $cwd '.remember/now.md'
if (Test-Path $now) { $nowContent = (Get-Content $now -Raw -ErrorAction SilentlyContinue) }

# 2) Last few user messages from the transcript (captures intent at compaction time).
$userMsgs = New-Object System.Collections.Generic.List[string]
if ($tpath -and (Test-Path $tpath)) {
    try {
        $lines = Get-Content $tpath -Tail 120 -ErrorAction SilentlyContinue
        foreach ($ln in $lines) {
            try {
                $o = $ln | ConvertFrom-Json
                if ($o.type -eq 'user' -and $o.message) {
                    $c = $o.message.content
                    $text = if ($c -is [string]) { $c }
                            elseif ($c) { ($c | Where-Object { $_.type -eq 'text' } | ForEach-Object { $_.text }) -join ' ' }
                            else { '' }
                    if ($text -and $text.Trim().Length -gt 0 -and $text -notmatch '^\s*<') {
                        $userMsgs.Add($text.Trim().Substring(0, [Math]::Min(400, $text.Trim().Length)))
                    }
                }
            } catch {}
        }
    } catch {}
}
$recentIntent = (($userMsgs | Select-Object -Last 5) -join "`n- ")

# --- Write the checkpoint note ------------------------------------------------
$vault = 'D:\basic-memory\compaction-checkpoints'
if (-not (Test-Path $vault)) { New-Item -ItemType Directory -Path $vault -Force | Out-Null }
$title = "Compaction checkpoint - $project - $stamp"
$note  = @"
---
title: $title
type: checkpoint
tags: [compaction-checkpoint, $project]
permalink: compaction-checkpoints/checkpoint-$stamp
---

# $title

- **When:** $ts
- **Trigger:** $trigger
- **Project / cwd:** $cwd
- **Session:** $sid
- **Transcript:** $tpath

## Recent user intent (pre-compaction)
- $recentIntent

## Live work buffer (.remember/now.md)
$nowContent
"@
$note | Out-File -FilePath (Join-Path $vault "checkpoint-$stamp.md") -Encoding utf8

# Retention: keep the 100 most recent checkpoints.
Get-ChildItem $vault -Filter 'checkpoint-*.md' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip 100 |
    ForEach-Object { try { [System.IO.File]::Delete($_.FullName) } catch {} }

'{"suppressOutput": true}'
