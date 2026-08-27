# cursor-hook-log.ps1 — Wave B (2026-08-27) generic observe-mode Cursor hook logger.
# Appends {"ts","hook_ms","payload":<raw stdin JSON>} to .agents\logs\<LogName>.
# FAIL-OPEN by design: any error is swallowed, exit is always 0, and -Allow emits
# {"permission":"allow"} for the before* veto hooks. Never blocks, never vetoes.
# hook_ms measures ONLY this script's body; process-spawn latency is measured by
# comparing wall-clock gaps in the calling event stream (flip-criteria evidence).
param(
    [string]$LogName = "cursor-hooks-misc.jsonl",
    [switch]$Allow
)
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = "{}" }
    $raw = ($raw -replace "[`r`n]+", " ").Trim()
    $logDir = "C:\Users\Prekzursil\.agents\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $line = '{"ts":"' + $ts + '","hook_ms":' + $sw.ElapsedMilliseconds + ',"payload":' + $raw + '}'
    Add-Content -Path (Join-Path $logDir $LogName) -Value $line -Encoding UTF8
} catch { }
if ($Allow) { Write-Output '{"permission":"allow"}' }
exit 0
