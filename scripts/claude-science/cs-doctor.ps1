# cs-doctor -- one read-only full-stack health report for Claude Science (local).
# Operationalizes the 2026-07-07 reliability audit into a repeatable PASS/WARN/FAIL table, and
# auto-detects the two gremlins that recur: a DUPLICATE watchdog and a STALE/hung watchdog.
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')
$script:rows = @()
function Add-Row($name, $status, $detail) { $script:rows += [pscustomobject]@{ Check = $name; Status = $status; Detail = $detail } }

# 1. WSL reachable
$wsl = Invoke-CSWsl 'echo ok' 15
Add-Row 'WSL reachable' $(if ($wsl -eq 'ok') { 'PASS' } elseif ($wsl -eq '__WSL_TIMEOUT__') { 'FAIL' } else { 'WARN' }) $(if ($wsl -eq '__WSL_TIMEOUT__') { 'wsl call timed out (VM wedged?)' } else { "distro=$script:CSDistro" })

# 2. CS daemon health + latency (the wedge signal)
$h = Test-CSHealth
Add-Row 'CS daemon' $(if ($h.State -eq 'HEALTHY') { 'PASS' } else { 'FAIL' }) ("state=$($h.State) http=$($h.Http) latency=$($h.Ms)ms" + $(if ($h.State -eq 'SLOW') { ' *** WEDGED ***' } else { '' }))

# 3. daemon detail
$stat = Invoke-CSWsl 'claude-science status 2>/dev/null' 15
if ($stat -and $stat -ne '__WSL_TIMEOUT__') {
  $dpid = ([regex]'"pid":\s*(\d+)').Match($stat).Groups[1].Value
  $ver = ([regex]'"version":\s*"([^"]+)"').Match($stat).Groups[1].Value
  $up = ([regex]'"uptime_ms":\s*(\d+)').Match($stat).Groups[1].Value
  $uph = if ($up) { [math]::Round(([int64]$up) / 3600000, 1) } else { '?' }
  Add-Row 'daemon detail' 'INFO' "pid=$dpid version=$ver uptime=${uph}h"
}

# 4. DB integrity + journal_mode + size
$dbline = Invoke-CSWsl 'DB=$(find $HOME/.claude-science/orgs -name operon-cli.db 2>/dev/null | head -1); if [ -n "$DB" ] && command -v sqlite3 >/dev/null 2>&1; then echo "$(sqlite3 -readonly "file:$DB?mode=ro" "PRAGMA integrity_check;" 2>&1 | head -1)|$(sqlite3 -readonly "file:$DB?mode=ro" "PRAGMA journal_mode;" 2>&1)|$(du -h "$DB" 2>/dev/null | cut -f1)"; else echo "no-sqlite3-or-db"; fi' 20
if ($dbline -and $dbline -ne '__WSL_TIMEOUT__' -and $dbline -ne 'no-sqlite3-or-db') {
  $p = $dbline -split '\|'
  Add-Row 'DB' $(if ($p[0] -eq 'ok') { 'PASS' } else { 'WARN' }) "integrity=$($p[0]) journal=$($p[1]) size=$($p[2])"
} else { Add-Row 'DB' 'WARN' 'sqlite3 or operon-cli.db not found' }

# 5. WSL disk
$disk = (Invoke-CSWsl 'df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9' 15)
$dg = 0; [void][int]::TryParse(("$disk").Trim(), [ref]$dg)
Add-Row 'WSL disk free' $(if ($dg -ge 10) { 'PASS' } else { 'WARN' }) "${dg}GB"

# 6. host RAM + top consumers (the freeze root cause)
$os = Get-CimInstance Win32_OperatingSystem
$ramGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$top = (Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 3 | ForEach-Object { "{0}({1}MB)" -f $_.ProcessName, [math]::Round($_.WorkingSet64 / 1MB) }) -join ', '
Add-Row 'Host RAM free' $(if ($ramGB -ge 3) { 'PASS' } else { 'WARN' }) "${ramGB}GB free; top: $top"

# 7. watchdog task + single-instance + heartbeat
$task = Get-ScheduledTask -TaskName 'ClaudeScienceWatchdog' -ErrorAction SilentlyContinue
$procs = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -EA SilentlyContinue | Where-Object { $_.CommandLine -like '*cs-watchdog*' })
Add-Row 'Watchdog registered' $(if ($task) { 'PASS' } else { 'FAIL' }) $(if ($task) { "state=$($task.State)" } else { 'not registered - run register-tasks.ps1' })
Add-Row 'Watchdog instances' $(if ($procs.Count -eq 1) { 'PASS' } elseif ($procs.Count -eq 0) { 'FAIL' } else { 'WARN' }) ("$($procs.Count) running" + $(if ($procs.Count -gt 1) { ' (DUPLICATE - dual-watchdog race)' } elseif ($procs.Count -eq 0) { ' (not running)' } else { '' }))
$beat = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.heartbeat'
if (Test-Path $beat) {
  $age = [math]::Round(((Get-Date) - (Get-Item $beat).LastWriteTime).TotalSeconds)
  Add-Row 'Watchdog heartbeat' $(if ($age -lt 90) { 'PASS' } else { 'FAIL' }) ("${age}s ago" + $(if ($age -ge 90) { ' (STALE - watchdog hung?)' } else { '' }))
} else { Add-Row 'Watchdog heartbeat' 'WARN' 'no heartbeat file (pre-hardening watchdog or never ran)' }

# 8. backup freshness
$bk = Invoke-CSWsl 'ls -t /mnt/d/Backups/claude-science/operon-*.db 2>/dev/null | head -1 | xargs -r stat -c %Y' 15
if ($bk -and $bk -match '^\d+$') {
  $ageH = [math]::Round(((Get-Date) - ([DateTimeOffset]::FromUnixTimeSeconds([int64]$bk)).LocalDateTime).TotalHours, 1)
  Add-Row 'Backup freshness' $(if ($ageH -lt 200) { 'PASS' } else { 'WARN' }) "newest ${ageH}h old"
} else { Add-Row 'Backup freshness' 'WARN' 'no backup found (D: mounted? cs-maintain run?)' }

# 9. tab-death regfix
Add-Row 'Tab-death regfix' $(if (Test-Path 'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions') { 'PASS' } else { 'WARN' }) $(if (Test-Path 'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions') { 'Chrome exceptions set' } else { 'not applied (install.ps1 sets it)' })

# render
"`n  Claude Science - doctor  ($(Get-Date -Format 's'))`n"
($script:rows | Format-Table -AutoSize @{L = ' '; E = { switch ($_.Status) { 'PASS' { '[+]' } 'FAIL' { '[X]' } 'WARN' { '[!]' } default { '[i]' } } } }, Check, Status, Detail | Out-String).TrimEnd()
$fail = @($script:rows | Where-Object Status -eq 'FAIL').Count
$warn = @($script:rows | Where-Object Status -eq 'WARN').Count
$pass = @($script:rows | Where-Object Status -eq 'PASS').Count
"`n  summary: $fail FAIL, $warn WARN, $pass PASS"
if ($fail) { "  -> try: cs fix    then re-run: cs doctor" }
