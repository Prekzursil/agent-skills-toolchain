# WU-H5 — SessionStart(source=compact) survival read-back.
# Reads the latest NON-EMPTY precompact snapshot and re-injects it via hookSpecificOutput.additionalContext.
# Fail-safe: never throws, never blocks (always exit 0). Pairs with the existing PreCompact snapshot.ps1 write-side.
try {
  $raw = [Console]::In.ReadToEnd()
  $j = $null
  if ($raw) { try { $j = $raw | ConvertFrom-Json } catch {} }
  $cwd = if ($j -and $j.cwd) { $j.cwd } else { (Get-Location).Path }
  $dirs = @("$cwd\.remember\tmp", "C:\Users\Prekzursil\.remember\tmp") | Select-Object -Unique
  $snap = $null
  foreach ($d in $dirs) {
    if (Test-Path $d) {
      $f = Get-ChildItem "$d\precompact-*.md" -ErrorAction SilentlyContinue |
           Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
      if ($f) { $snap = $f; break }
    }
  }
  if ($snap) {
    $content = Get-Content $snap.FullName -Raw -ErrorAction SilentlyContinue
    if ($content) {
      $ctx = "[Recovered pre-compaction snapshot: $($snap.Name)]`n" + $content
      $out = @{ hookSpecificOutput = @{ hookEventName = "SessionStart"; additionalContext = $ctx } } |
             ConvertTo-Json -Depth 6 -Compress
      Write-Output $out
    }
  }
} catch {}
exit 0
