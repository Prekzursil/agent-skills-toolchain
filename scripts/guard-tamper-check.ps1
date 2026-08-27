# guard-tamper-check.ps1 — Wave A-f (2026-08-27), per COUNCIL-NEXT-WAVE Security voice.
# DRY-RUN tracer: hashes the guard files themselves (the unwatched attack surface) and logs
# drift to .agents\logs\guard-tamper.log. It NEVER blocks, repairs, or alerts beyond the log.
# Scheduled daily via the GuardTamperTracer task (no daemon). Baseline is updated after each
# drift report so a change is reported once, not forever.

$ErrorActionPreference = "Continue"
$home_ = "C:\Users\Prekzursil"
$logDir = Join-Path $home_ ".agents\logs"
$log = Join-Path $logDir "guard-tamper.log"
$stateDir = Join-Path $home_ ".agents\state"
$baselineFile = Join-Path $stateDir "guard-tamper-baseline.json"

# The guard surface (order stable for deterministic output):
$guardFiles = @(
    (Join-Path $home_ ".cursor\hooks.json"),
    (Join-Path $home_ ".claude\hooks\_dispatch\manifest.json"),
    (Join-Path $home_ ".codex\rules\default.rules"),
    (Join-Path $home_ ".agents\agents.json")
)

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")

# Load baseline (missing/corrupt baseline => first run, seed it silently).
$baseline = @{}
if (Test-Path $baselineFile) {
    try {
        $raw = Get-Content $baselineFile -Raw | ConvertFrom-Json
        foreach ($p in $raw.PSObject.Properties) { $baseline[$p.Name] = $p.Value }
    } catch {
        Add-Content $log "$now BASELINE-CORRUPT reseeding ($($_.Exception.Message))"
        $baseline = @{}
    }
}

$current = @{}
$driftLines = @()
foreach ($f in $guardFiles) {
    if (Test-Path $f) {
        try { $h = (Get-FileHash -Algorithm SHA256 -Path $f).Hash }
        catch { $driftLines += "$now HASH-ERROR $f $($_.Exception.Message)"; continue }
        $current[$f] = $h
        if ($baseline.ContainsKey($f)) {
            if ($baseline[$f] -eq "NOT-PRESENT") { $driftLines += "$now APPEARED $f sha256=$h" }
            elseif ($baseline[$f] -ne $h)        { $driftLines += "$now DRIFT $f old=$($baseline[$f]) new=$h" }
        }
    } else {
        $current[$f] = "NOT-PRESENT"
        if ($baseline.ContainsKey($f) -and $baseline[$f] -ne "NOT-PRESENT") {
            $driftLines += "$now VANISHED $f (was sha256=$($baseline[$f]))"
        }
    }
}

if ($baseline.Count -eq 0) {
    Add-Content $log "$now BASELINE-SEEDED $($current.Count) guard files"
} elseif ($driftLines.Count -gt 0) {
    $driftLines | ForEach-Object { Add-Content $log $_ }
} else {
    Add-Content $log "$now OK no drift ($($current.Count) guard files)"
}

# Persist the new baseline (dry-run: record-and-move-on; drift is reported once).
$current | ConvertTo-Json | Set-Content $baselineFile -Encoding UTF8
exit 0
