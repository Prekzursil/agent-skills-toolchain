# guard-tracer-round.ps1 — Wave D (2026-08-27), airworthiness trio part 2/3 (tracer rounds).
# DRY-RUN, scheduled daily, no daemon. Fires synthetic contraband through the observe-mode
# Cursor shell guard (shell-guard.ps1) and verifies each round is flagged "would-deny".
# A guard that does not trip is logged as MEL-DEFERRAL (see .agents\mel.md rows 5/6).
# Never blocks anything; the contraband is never executed — it only transits the guard.

$ErrorActionPreference = "Continue"
$home_ = "C:\Users\Prekzursil"
$guard = Join-Path $home_ ".agents\scripts\cursor-hooks\shell-guard.ps1"
$log = Join-Path $home_ ".agents\logs\guard-tamper.log"
$guardLog = Join-Path $home_ ".agents\logs\cursor-shell-guard.jsonl"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
$now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")

if (-not (Test-Path $guard)) {
    Add-Content $log "$now TRACER MEL-DEFERRAL shell-guard.ps1 ABSENT ($guard)"
    exit 0
}

# Synthetic contraband: one representative per deny-family in shell-guard.ps1.
$rounds = @(
    'git push --force origin main',
    'git reset --hard HEAD~3',
    'git clean -fdx',
    'reg delete HKLM\SOFTWARE\test /f',
    'cat .env'
)

$fired = 0; $missed = @()
foreach ($cmd in $rounds) {
    $payload = '{"command":"' + ($cmd -replace '\\', '\\\\' -replace '"', '\"') + '","cwd":"C:/tracer-round","tracer":true}'
    try {
        $before = if (Test-Path $guardLog) { (Get-Content $guardLog -Tail 1) } else { "" }
        $payload | powershell -NoProfile -ExecutionPolicy Bypass -File $guard | Out-Null
        $after = if (Test-Path $guardLog) { (Get-Content $guardLog -Tail 1) } else { "" }
        if ($after -ne $before -and $after -match '"verdict":"would-deny"') { $fired++ }
        else { $missed += $cmd }
    } catch { $missed += $cmd }
}

if ($missed.Count -eq 0) {
    Add-Content $log "$now TRACER OK $fired/$($rounds.Count) contraband rounds flagged would-deny"
} else {
    Add-Content $log "$now TRACER MEL-DEFERRAL guard failed to trip on: $($missed -join ' | ')"
}
exit 0
