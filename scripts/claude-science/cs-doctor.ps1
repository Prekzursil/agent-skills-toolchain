# cs-doctor -- one read-only full-stack health report for Claude Science (local).
# Operationalizes the 2026-07-07 reliability audit into a repeatable PASS/WARN/FAIL table, and
# auto-detects the two gremlins that recur: a DUPLICATE watchdog and a STALE/hung watchdog.
#
# ------------------------------------------------------------------------------------------------
# FAIL-CLOSED CONTRACT (added 2026-08-12). A health check that CANNOT FIND OR REACH ITS INPUT must
# never render as PASS, and must never print a factual claim it did not measure. Measured before
# this change: `[!] DB WARN "sqlite3 or operon-cli.db not found"` was printed while BOTH sqlite3
# and the DB existed and the identical probe returned `ok|wal|2.9M` in 1293ms standalone -- the
# real cause was an Invoke-CSWsl timeout under host-RAM pressure. One branch collapsed three
# distinct causes (timeout / empty / genuinely absent) into the message for only the third.
# Directly below it, `[+] Backup freshness PASS` rendered green over an input from the same
# unreachable VM. That is the ci-hygiene no-op-gate class: a green row proving nothing.
#
# The contract now has FOUR states, and the summary counts all four so "0 FAIL, 0 WARN" can no
# longer hide unmeasured rows:
#   PASS        measured, and good
#   WARN        measured, and degraded
#   FAIL        measured, and bad  -- OR the input is genuinely absent (absence is a measurement)
#   NOT-CHECKED could not measure (probe timed out / empty) -- says so, asserts nothing else
# ------------------------------------------------------------------------------------------------
[CmdletBinding()]
param([switch]$Json)   # -Json: machine-readable rows + counts (used by the fail-closed test harness and `mon csmon`)
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'cs-lib.ps1')
$script:rows = @()
function Add-Row($name, $status, $detail) { $script:rows += [pscustomobject]@{ Check = $name; Status = $status; Detail = $detail } }
function Test-CSUnmeasured($v) { return ($null -eq $v -or "$v" -eq '' -or "$v" -eq '__WSL_TIMEOUT__') }

# 1. WSL reachable
$wsl = Invoke-CSWsl 'echo ok' 15 -Tag 'wsl'
Add-Row 'WSL reachable' $(if ($wsl -eq 'ok') { 'PASS' } elseif ($wsl -eq '__WSL_TIMEOUT__') { 'FAIL' } else { 'WARN' }) $(if ($wsl -eq '__WSL_TIMEOUT__') { 'wsl call timed out (VM wedged?)' } else { "distro=$script:CSDistro" })

# 2. CS daemon health + latency (the wedge signal)
$h = Test-CSHealth
Add-Row 'CS daemon' $(if ($h.State -eq 'HEALTHY') { 'PASS' } else { 'FAIL' }) ("state=$($h.State) http=$($h.Http) latency=$($h.Ms)ms" + $(if ($h.State -eq 'SLOW') { ' *** WEDGED ***' } else { '' }))

# 3. daemon detail
# FAIL-CLOSED: the `if` below had no `else`, so on a failed probe the row SILENTLY VANISHED from
# the table -- an absent row reads as "nothing to report" when it actually means "not measured".
$stat = Invoke-CSWsl 'claude-science status 2>/dev/null' 15 -Tag 'stat'
if (-not (Test-CSUnmeasured $stat)) {
  $dpid = ([regex]'"pid":\s*(\d+)').Match($stat).Groups[1].Value
  $ver = ([regex]'"version":\s*"([^"]+)"').Match($stat).Groups[1].Value
  $up = ([regex]'"uptime_ms":\s*(\d+)').Match($stat).Groups[1].Value
  $uph = if ($up) { [math]::Round(([int64]$up) / 3600000, 1) } else { '?' }
  Add-Row 'daemon detail' 'INFO' "pid=$dpid version=$ver uptime=${uph}h"
} else {
  Add-Row 'daemon detail' 'NOT-CHECKED' $(if ("$stat" -eq '__WSL_TIMEOUT__') { 'WSL probe timed out; daemon detail unmeasured' } else { 'daemon status probe returned nothing; detail unmeasured' })
}

# 4. DB integrity + journal_mode + size
# The DB is selected by NEWEST MTIME, not `find | head -1`: there are TWO org dirs on this box and
# find order is filesystem order, so the old probe could pronounce one org's DB healthy while
# cs-backup snapshotted the other. Kept inline (rather than calling cs-lib.sh's cs_find_db) on
# purpose -- a doctor has to work when the WSL-side deploy is exactly what is broken.
$dbline = Invoke-CSWsl 'DB=$(find $HOME/.claude-science/orgs -name operon-cli.db -printf "%T@\t%p\n" 2>/dev/null | sort -k1,1nr -k2,2 | head -1 | cut -f2-); if [ -z "$DB" ]; then echo "__NODB__"; elif ! command -v sqlite3 >/dev/null 2>&1; then echo "__NOSQLITE__"; else echo "$(sqlite3 -readonly "file:$DB?mode=ro" "PRAGMA integrity_check;" 2>&1 | head -1)|$(sqlite3 -readonly "file:$DB?mode=ro" "PRAGMA journal_mode;" 2>&1)|$(du -h "$DB" 2>/dev/null | cut -f1)"; fi' 20 -Tag 'db'
if (Test-CSUnmeasured $dbline) {
  Add-Row 'DB' 'NOT-CHECKED' $(if ("$dbline" -eq '__WSL_TIMEOUT__') { 'WSL probe timed out; DB integrity unmeasured (NOT a claim the DB is missing)' } else { 'DB probe returned nothing; integrity unmeasured' })
} elseif ($dbline -eq '__NODB__') {
  Add-Row 'DB' 'FAIL' 'operon-cli.db not found under ~/.claude-science/orgs (measured absent)'
} elseif ($dbline -eq '__NOSQLITE__') {
  Add-Row 'DB' 'FAIL' 'sqlite3 not on PATH in WSL - DB integrity cannot be checked at all'
} else {
  $p = $dbline -split '\|'
  Add-Row 'DB' $(if ($p[0] -eq 'ok') { 'PASS' } else { 'FAIL' }) "integrity=$($p[0]) journal=$($p[1]) size=$($p[2])"
}

# 5. WSL disk
$disk = (Invoke-CSWsl 'df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9' 15 -Tag 'disk')
if (Test-CSUnmeasured $disk) {
  Add-Row 'WSL disk free' 'NOT-CHECKED' 'WSL probe returned nothing; free disk unmeasured'
} else {
  $dg = 0; [void][int]::TryParse(("$disk").Trim(), [ref]$dg)
  Add-Row 'WSL disk free' $(if ($dg -ge $script:CSMinWslDiskGb) { 'PASS' } else { 'WARN' }) "${dg}GB (floor ${script:CSMinWslDiskGb}GB)"
}

# 6. host RAM + top consumers (the freeze root cause)
$os = Get-CimInstance Win32_OperatingSystem
$ramGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$top = (Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 3 | ForEach-Object { "{0}({1}MB)" -f $_.ProcessName, [math]::Round($_.WorkingSet64 / 1MB) }) -join ', '
Add-Row 'Host RAM free' $(if ($ramGB -ge $script:CSMinHostRamGb) { 'PASS' } else { 'WARN' }) "${ramGB}GB free; top: $top"

# 7. watchdog task + single-instance + heartbeat
$task = Get-ScheduledTask -TaskName 'ClaudeScienceWatchdog' -ErrorAction SilentlyContinue
$procs = Get-CSWatchdogProcess   # self-excluding, argument-shape matched (see cs-lib.ps1)
Add-Row 'Watchdog registered' $(if ($task) { 'PASS' } else { 'FAIL' }) $(if ($task) { "state=$($task.State)" } else { 'not registered - run register-tasks.ps1' })
# A logon-only trigger cannot restart a watchdog that exited: measured 2026-08-08..12, dead 3.3
# days with State=Ready and an empty NextRunTime. The repeating trigger IS the self-healing.
$rep = @($task.Triggers | ForEach-Object { $_.Repetition.Interval } | Where-Object { $_ })
Add-Row 'Watchdog re-launch trigger' $(if (-not $task) { 'FAIL' } elseif ($rep.Count) { 'PASS' } else { 'FAIL' }) $(if (-not $task) { 'no task' } elseif ($rep.Count) { "repetition=$($rep -join ',') (survives a silent exit)" } else { 'LOGON-ONLY: nothing restarts it after an exit - re-run register-tasks.ps1' })
Add-Row 'Watchdog instances' $(if ($procs.Count -eq 1) { 'PASS' } elseif ($procs.Count -eq 0) { 'FAIL' } else { 'WARN' }) ("$($procs.Count) running" + $(if ($procs.Count -gt 1) { ' (DUPLICATE - dual-watchdog race)' } elseif ($procs.Count -eq 0) { ' (not running)' } else { '' }))
$beat = Join-Path $env:LOCALAPPDATA 'claude-science-watchdog.heartbeat'
if (Test-Path $beat) {
  $age = [math]::Round(((Get-Date) - (Get-Item $beat).LastWriteTime).TotalSeconds)
  # AND-GATE, two mechanically independent signals. A stale beat ALONE is not proof of a hung
  # watchdog: measured 2026-08-12, a single probe took 66,396ms (the process is descheduled under
  # host-RAM pressure, which no in-process socket timeout can bound), so a healthy watchdog that
  # was correctly measuring a wedge reported "STALE - watchdog hung?". Stale beat + NO live
  # process = hung/dead (FAIL). Stale beat + a live process = slow, not hung (WARN).
  if ($age -lt $script:CSBeatStaleS) {
    Add-Row 'Watchdog heartbeat' 'PASS' "${age}s ago (stale at ${script:CSBeatStaleS}s)"
  } elseif ($procs.Count -ge 1) {
    Add-Row 'Watchdog heartbeat' 'WARN' "${age}s ago but process alive - beat is late, watchdog is not hung (probe can outrun its socket cap under RAM pressure)"
  } else {
    Add-Row 'Watchdog heartbeat' 'FAIL' "${age}s ago and NO watchdog process - hung or dead"
  }
} else { Add-Row 'Watchdog heartbeat' 'FAIL' 'no heartbeat file - the watchdog has never completed a probe' }

# 8. backup freshness + RESTORABILITY (one WSL round-trip serves both rows)
# "A backup you cannot restore is false safety" -- so EXISTENCE is not the check. This opens the
# newest snapshot and runs PRAGMA integrity_check on it.
$bkProbe = Invoke-CSWsl ("B=`$(ls -t '$script:CSBackupRoot'/operon-*.db 2>/dev/null | head -1); if [ -z `"`$B`" ]; then echo __NOBACKUP__; elif ! command -v sqlite3 >/dev/null 2>&1; then echo `"`$(stat -c %Y `"`$B`")|__NOSQLITE__|`"; else echo `"`$(stat -c %Y `"`$B`")|`$(sqlite3 -readonly `"file:`$B?mode=ro`" 'PRAGMA integrity_check;' 2>&1 | head -1)|`$(sqlite3 -readonly `"file:`$B?mode=ro`" `"SELECT count(*) FROM sqlite_master WHERE type='table';`" 2>&1 | head -1)`"; fi") 25 -Tag 'backup'

$bkParts = @()
if (-not (Test-CSUnmeasured $bkProbe) -and $bkProbe -ne '__NOBACKUP__') { $bkParts = "$bkProbe".Trim() -split '\|' }

if (Test-CSUnmeasured $bkProbe) {
  Add-Row 'Backup freshness' 'NOT-CHECKED' $(if ("$bkProbe" -eq '__WSL_TIMEOUT__') { 'WSL probe timed out; backup age unmeasured (NOT a claim there is no backup)' } else { 'backup probe returned nothing; age unmeasured' })
} elseif ($bkProbe -eq '__NOBACKUP__') {
  Add-Row 'Backup freshness' 'FAIL' "no operon-*.db under $script:CSBackupRoot (measured absent - D: mounted? cs-maintain run?)"
} elseif ($bkParts.Count -ge 1 -and $bkParts[0] -match '^\d+$') {
  $ageH = [math]::Round(((Get-Date) - ([DateTimeOffset]::FromUnixTimeSeconds([int64]$bkParts[0])).LocalDateTime).TotalHours, 1)
  $st = if ($ageH -ge $script:CSBackupFailH) { 'FAIL' } elseif ($ageH -ge $script:CSBackupWarnH) { 'WARN' } else { 'PASS' }
  Add-Row 'Backup freshness' $st "newest ${ageH}h old (warn ${script:CSBackupWarnH}h / fail ${script:CSBackupFailH}h)"
} else {
  Add-Row 'Backup freshness' 'NOT-CHECKED' "unparseable backup probe reply: $bkProbe"
}

# Restorability. TWO mechanically independent signals, because either can be unavailable:
#   (a) Windows-side, needs no WSL at all -- the snapshot lives on a real NTFS path, so the SQLite
#       magic header is readable even when the VM is wedged.
#   (b) WSL-side PRAGMA integrity_check -- the real proof, when sqlite3 is reachable.
$hdrOk = $null; $hdrDetail = 'backup root not derivable from CS_BACKUP_ROOT'
if ($script:CSBackupRootWin) {
  $newest = Get-ChildItem -LiteralPath $script:CSBackupRootWin -Filter 'operon-*.db' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $newest) { $hdrOk = $false; $hdrDetail = "no operon-*.db under $script:CSBackupRootWin" }
  else {
    $magic = [byte[]]::new(16)
    try {
      $fs = [System.IO.File]::OpenRead($newest.FullName)
      try { [void]$fs.Read($magic, 0, 16) } finally { $fs.Dispose() }
      $hdrOk = ([System.Text.Encoding]::ASCII.GetString($magic) -eq "SQLite format 3`0")
      $hdrDetail = "$($newest.Name) $($newest.Length)B header=$(if ($hdrOk) { 'ok' } else { 'CORRUPT' })"
    } catch { $hdrOk = $null; $hdrDetail = "cannot read $($newest.Name): $($_.Exception.Message)" }
  }
}
$integ = if ($bkParts.Count -ge 2) { $bkParts[1] } else { $null }
$ntab = if ($bkParts.Count -ge 3) { $bkParts[2] } else { $null }
if ($hdrOk -eq $false) {
  Add-Row 'Backup restorable' 'FAIL' $hdrDetail
} elseif ($integ -eq 'ok') {
  Add-Row 'Backup restorable' 'PASS' "$hdrDetail; integrity=ok tables=$ntab"
} elseif ($integ -and $integ -ne '__NOSQLITE__') {
  Add-Row 'Backup restorable' 'FAIL' "$hdrDetail; integrity=$integ - the snapshot does NOT open cleanly"
} else {
  Add-Row 'Backup restorable' 'NOT-CHECKED' "$hdrDetail; integrity unmeasured (WSL/sqlite3 unreachable) - header alone is not proof of restorability"
}

# 9. tab-death regfix
Add-Row 'Tab-death regfix' $(if (Test-Path 'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions') { 'PASS' } else { 'WARN' }) $(if (Test-Path 'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions') { 'Chrome exceptions set' } else { 'not applied (install.ps1 sets it)' })

# render
$fail = @($script:rows | Where-Object Status -eq 'FAIL').Count
$warn = @($script:rows | Where-Object Status -eq 'WARN').Count
$pass = @($script:rows | Where-Object Status -eq 'PASS').Count
$nc = @($script:rows | Where-Object Status -eq 'NOT-CHECKED').Count
if ($Json) {
  [pscustomobject]@{
    at    = (Get-Date -Format 's')
    fail  = $fail; warn = $warn; not_checked = $nc; pass = $pass
    rows  = @($script:rows)
  } | ConvertTo-Json -Depth 4 -Compress
  if ($fail -or $nc) { exit 1 } else { exit 0 }
}
"`n  Claude Science - doctor  ($(Get-Date -Format 's'))`n"
($script:rows | Format-Table -AutoSize @{L = ' '; E = { switch ($_.Status) { 'PASS' { '[+]' } 'FAIL' { '[X]' } 'WARN' { '[!]' } 'NOT-CHECKED' { '[?]' } default { '[i]' } } } }, Check, Status, Detail | Out-String).TrimEnd()
# NOT-CHECKED is counted separately and deliberately: folding it into PASS is the exact bug this
# file was rewritten to remove, and folding it into WARN would hide that nothing was measured.
"`n  summary: $fail FAIL, $warn WARN, $nc NOT-CHECKED, $pass PASS"
if ($fail) { "  -> try: cs fix    then re-run: cs doctor" }
if ($nc) { "  -> NOT-CHECKED rows were NOT measured (usually a wedged VM). Re-run after: cs fix" }
# Non-zero exit on FAIL so `cs doctor` is usable as a gate by other tooling. NOT-CHECKED also
# exits non-zero: an unmeasured health check must not read as success to a caller.
if ($fail -or $nc) { exit 1 } else { exit 0 }
