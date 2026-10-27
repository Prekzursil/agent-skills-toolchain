# WU-H7 — InstructionsLoaded diagnostic logger.
# Appends each loaded instruction file (path + reason + memory_type) to a log so the every-turn
# load can be verified continuously after each trim WU. Fail-safe: never throws, never blocks.
try {
  $raw = [Console]::In.ReadToEnd()
  $j = $null
  if ($raw) { try { $j = $raw | ConvertFrom-Json } catch {} }
  $log = "C:\Users\Prekzursil\.claude\logs\instructions-loaded.log"
  $dir = Split-Path $log
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $fp = if ($j) { $j.file_path } else { "" }
  $lr = if ($j) { $j.load_reason } else { "" }
  $mt = if ($j) { $j.memory_type } else { "" }
  $line = "{0}`t{1}`t{2}`t{3}" -f (Get-Date -Format o), $lr, $mt, $fp
  Add-Content -Path $log -Value $line -ErrorAction SilentlyContinue
} catch {}
exit 0
