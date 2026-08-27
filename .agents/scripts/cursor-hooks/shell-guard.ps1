# shell-guard.ps1 — Wave B (2026-08-27) Cursor beforeShellExecution guard, OBSERVE MODE.
# Mirrors the destructive-command deny-set from ~\.codex\rules\default.rules, but LOG-ONLY:
# a match is recorded as verdict "would-deny" and the command is STILL ALLOWED.
# Flip to enforcement (permission deny / failClosed) only per the criteria documented in
# ~\.cursor\hooks.json "_readme" — after ~1 week of latency evidence from these logs.
# FAIL-OPEN: every error path allows; exit is always 0.
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$verdict = "ok"
$cmd = ""
try {
    $raw = [Console]::In.ReadToEnd()
    try { $payload = $raw | ConvertFrom-Json; $cmd = [string]$payload.command } catch { $cmd = "" }

    # Deny-set mirrored from .codex\rules\default.rules (destructive git, disk/registry
    # destruction, credential reads). Regexes over the full command string.
    $denyPatterns = @(
        'git\s+push\s+\S*.*(--force-with-lease|--force|\s-f(\s|$))',
        'git\s+reset\s+--hard',
        'git\s+clean\s+-(fdx|xdf)',
        '(^|[;&|]\s*)diskpart(\s|$)',
        '(^|[;&|]\s*)format(\.com)?\s+[a-zA-Z]:',
        '\breg(\.exe)?\s+delete\b',
        '\bbcdedit\s+/delete\b',
        '\bcipher\s+/w\b',
        '(Get-Content|type|cat)\s+\S*\.env\b',
        '(Get-Content|type|cat)\s+\S*[\\/]\.(ssh|aws)\b'
    )
    foreach ($p in $denyPatterns) {
        if ($cmd -match $p) { $verdict = "would-deny"; break }
    }

    $logDir = "C:\Users\Prekzursil\.agents\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $cmdShort = if ($cmd.Length -gt 300) { $cmd.Substring(0, 300) + "..." } else { $cmd }
    # JSON-escape the command excerpt
    $cmdEsc = $cmdShort -replace '\\', '\\\\' -replace '"', '\"' -replace "`t", ' ' -replace "[`r`n]+", ' '
    $line = '{"ts":"' + $ts + '","hook":"beforeShellExecution","verdict":"' + $verdict + '","hook_ms":' + $sw.ElapsedMilliseconds + ',"command":"' + $cmdEsc + '"}'
    Add-Content -Path (Join-Path $logDir "cursor-shell-guard.jsonl") -Value $line -Encoding UTF8
} catch { }

# OBSERVE MODE: always allow (would-deny is only logged).
Write-Output '{"permission":"allow"}'
exit 0
