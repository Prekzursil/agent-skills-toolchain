# WU-H5 — SessionStart(source=compact) survival read-back.
# Reads the latest NON-EMPTY precompact snapshot and re-injects it via hookSpecificOutput.additionalContext.
# Fail-safe: never throws, never blocks (always exit 0). Pairs with the existing PreCompact snapshot.ps1 write-side.
try {
  $raw = [Console]::In.ReadToEnd()
  $j = $null
  if ($raw) { try { $j = $raw | ConvertFrom-Json } catch {} }
  $cwd = if ($j -and $j.cwd) { $j.cwd } else { (Get-Location).Path }
  # Restore ONLY this session's own snapshot. The previous version took the newest
  # snapshot in the directory, and fell back to the shared global dir, so a session whose
  # own snapshot was missing was handed whichever OTHER session compacted last — one
  # conversation's context steering another. No session id => restore nothing.
  $sid = if ($j -and $j.session_id) { ($j.session_id -replace '[^A-Za-z0-9]', '') } else { '' }
  $snap = $null
  if ($sid) {
    $sidTag = $sid.Substring(0, [Math]::Min(16, $sid.Length))
    $dirs = @("$cwd\.remember\tmp", "C:\Users\Prekzursil\.remember\tmp") | Select-Object -Unique
    foreach ($d in $dirs) {
      if (Test-Path $d) {
        $f = Get-ChildItem "$d\precompact-$sidTag-*.md" -ErrorAction SilentlyContinue |
             Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($f) { $snap = $f; break }
      }
    }
  }
  if ($snap) {
    # Bound the emission. now.md is an append-only shared buffer that reached 774 KB, and
    # -Raw re-injected all of it; the tail is the part that is actually recent.
    $maxChars = 24000
    $content = Get-Content $snap.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content.Length -gt $maxChars) {
      $content = "[truncated to the most recent $maxChars chars of $($content.Length)]`n" +
                 $content.Substring($content.Length - $maxChars)
    }
    if ($content) {
      $ctx = "[Recovered pre-compaction snapshot: $($snap.Name)]`n" + $content
      $out = @{ hookSpecificOutput = @{ hookEventName = "SessionStart"; additionalContext = $ctx } } |
             ConvertTo-Json -Depth 6 -Compress
      Write-Output $out
    }
  }
} catch {}
exit 0
