# test-cs-doctor-failclosed -- the BOTH-STATES harness for cs-doctor's fail-closed contract.
#
# WHY THIS FILE EXISTS. cs doctor reads `0 FAIL, 0 WARN, N PASS` on a healthy box. Any claim that
# it "now fails closed", validated only against that box, is a probe that is silent in both states
# and therefore measures nothing. This harness reaches the BROKEN state on demand (via the
# CS_FORCE_WSL_* injection seam in cs-lib.ps1) and asserts the row goes FAIL or NOT-CHECKED --
# and, in the paired control, that the SAME row goes PASS when the input is fine. A test that only
# checks the broken direction cannot tell a fail-closed row from a row that is always red.
#
# It also pins the specific defect that motivated the rewrite: on a probe TIMEOUT the DB row used
# to print "sqlite3 or operon-cli.db not found" -- a factual claim about a file it never looked at.
# S2 asserts that string can no longer appear when the cause was a timeout.
#
# Run:   pwsh -NoProfile -File scripts/claude-science/test-cs-doctor-failclosed.ps1
# Exit:  0 = all assertions held (prints SUCCESS:cs-doctor-failclosed)
#        1 = at least one assertion failed (prints FAILED:cs-doctor-failclosed + the diffs)
#
# Fully hermetic: every WSL probe is stubbed, so it does NOT touch the VM, needs no daemon, and is
# safe to run while the box is wedged (which is exactly when you want it).
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$doctor = Join-Path $PSScriptRoot 'cs-doctor.ps1'

# --- scratch backup roots -----------------------------------------------------------------------
# CS_BACKUP_ROOT is stored in WSL form and cs-lib.ps1 derives the Windows form, so overriding it
# here ALSO exercises that derivation end-to-end (a scenario that silently fell back to the real
# D:\Backups would quietly stop testing anything).
function ConvertTo-WslPath([string]$win) {
  $d = $win.Substring(0, 1).ToLower()
  return "/mnt/$d" + ($win.Substring(2) -replace '\\', '/')
}
$stamp = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$emptyWin = Join-Path $env:TEMP "cs-test-empty-$stamp"
$badWin = Join-Path $env:TEMP "cs-test-badhdr-$stamp"
New-Item -ItemType Directory -Path $emptyWin -Force | Out-Null
New-Item -ItemType Directory -Path $badWin -Force | Out-Null
# A file that LOOKS like a snapshot and is not a SQLite database. This is what a truncated or
# half-written backup looks like on disk, and the old row would have called it fresh and fine.
[System.IO.File]::WriteAllBytes((Join-Path $badWin 'operon-20260812-000000.db'), [byte[]](1..64))

$nowU = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
function AgoH([int]$h) { return ($nowU - ($h * 3600)).ToString() }

$healthy = @{
  CS_FORCE_WSL_WSL    = 'ok'
  CS_FORCE_WSL_STAT   = '{"pid": 4242, "version": "9.9.9", "uptime_ms": 3600000}'
  CS_FORCE_WSL_DB     = 'ok|wal|2.9M'
  CS_FORCE_WSL_DISK   = '99'
  CS_FORCE_WSL_BACKUP = "$(AgoH 1)|ok|58"
}
function With([hashtable]$over) {
  $h = @{}
  foreach ($k in $healthy.Keys) { $h[$k] = $healthy[$k] }
  foreach ($k in $over.Keys) { $h[$k] = $over[$k] }
  return $h
}

# expect: row name -> expected status. '<ANY>' means "present, status unconstrained".
$scenarios = @(
  @{ name = 'S1  control: every input healthy'; env = (With @{}); expect = @{
      'DB' = 'PASS'; 'Backup freshness' = 'PASS'; 'Backup restorable' = 'PASS'; 'daemon detail' = 'INFO' } }

  @{ name = 'S2  global WSL timeout (the measured false-claim case)'; env = @{ CS_FORCE_WSL_TIMEOUT = '1' }; expect = @{
      'DB' = 'NOT-CHECKED'; 'Backup freshness' = 'NOT-CHECKED'; 'Backup restorable' = 'NOT-CHECKED'; 'daemon detail' = 'NOT-CHECKED' }
    forbidDetail = @{ 'DB' = 'not found' } }

  @{ name = 'S3  DB genuinely absent'; env = (With @{ CS_FORCE_WSL_DB = '__NODB__' }); expect = @{ 'DB' = 'FAIL' } }
  @{ name = 'S4  sqlite3 missing in WSL'; env = (With @{ CS_FORCE_WSL_DB = '__NOSQLITE__' }); expect = @{ 'DB' = 'FAIL' } }
  @{ name = 'S5  DB integrity NOT ok'; env = (With @{ CS_FORCE_WSL_DB = '*** in database main ***|wal|2.9M' }); expect = @{ 'DB' = 'FAIL' } }
  @{ name = 'S6  DB probe returns empty'; env = (With @{ CS_FORCE_WSL_DB = '__EMPTY__' }); expect = @{ 'DB' = 'NOT-CHECKED' } }

  @{ name = 'S7  no backup at all'; env = (With @{ CS_FORCE_WSL_BACKUP = '__NOBACKUP__'; CS_BACKUP_ROOT = (ConvertTo-WslPath $emptyWin) }); expect = @{
      'Backup freshness' = 'FAIL'; 'Backup restorable' = 'FAIL' } }
  @{ name = 'S8  backup stale past the FAIL threshold'; env = (With @{ CS_FORCE_WSL_BACKUP = "$(AgoH 400)|ok|58" }); expect = @{ 'Backup freshness' = 'FAIL' } }
  @{ name = 'S9  backup stale past the WARN threshold only'; env = (With @{ CS_FORCE_WSL_BACKUP = "$(AgoH 180)|ok|58" }); expect = @{ 'Backup freshness' = 'WARN' } }
  @{ name = 'S10 backup present but corrupt (integrity != ok)'; env = (With @{ CS_FORCE_WSL_BACKUP = "$(AgoH 1)|*** in database main ***|58" }); expect = @{ 'Backup restorable' = 'FAIL' } }
  @{ name = 'S11 backup header corrupt, WSL unreachable (Windows-only signal)'; env = (With @{ CS_FORCE_WSL_BACKUP = '__WSL_TIMEOUT__'; CS_BACKUP_ROOT = (ConvertTo-WslPath $badWin) }); expect = @{
      'Backup freshness' = 'NOT-CHECKED'; 'Backup restorable' = 'FAIL' } }
  @{ name = 'S12 daemon status probe returns empty'; env = (With @{ CS_FORCE_WSL_STAT = '__EMPTY__' }); expect = @{ 'daemon detail' = 'NOT-CHECKED' } }
)

$failures = @()
$checked = 0

# --- CONFIG PARITY -------------------------------------------------------------------------------
# cs.conf is the SSOT, but BOTH libs also carry hard defaults so a missing/unreadable cs.conf
# degrades to the shipped values instead of to empty strings. That is deliberate -- and it is also
# a duplication, which is exactly the kind of thing that drifts silently and is then discovered by
# a production surprise. This asserts all three agree, so the fallback can never disagree with the
# file it is a fallback for.
$confPath = Join-Path $PSScriptRoot 'cs.conf'
$libPs = Get-Content -Raw (Join-Path $PSScriptRoot 'cs-lib.ps1')
$libSh = Get-Content -Raw (Join-Path $PSScriptRoot 'cs-lib.sh')
$conf = @{}
foreach ($l in (Get-Content $confPath)) {
  $t = $l.Trim(); if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $conf[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
}
if ($conf.Count -lt 10) { $failures += "config parity: cs.conf parsed only $($conf.Count) keys - the parser or the file is wrong" }
foreach ($k in $conf.Keys) {
  $want = $conf[$k]
  $checked++
  # cs-lib.ps1:  Get-CSSetting[Int] 'KEY' <default>       (quoted for strings, bare for ints)
  $mPs = [regex]::Match($libPs, "Get-CSSetting(?:Int)?\s+'$([regex]::Escape($k))'\s+'?([^'\r\n]+?)'?\s*(?:#|\r?\n)")
  if (-not $mPs.Success) {
    # Not every key is consumed by the PowerShell half (the shell-only ones are fine).
    if ($libPs -match [regex]::Escape($k)) { $failures += "config parity: '$k' appears in cs-lib.ps1 but not as a Get-CSSetting default" }
  } elseif ($mPs.Groups[1].Value.Trim() -ne $want) {
    $failures += "config parity: '$k' = '$want' in cs.conf but cs-lib.ps1 defaults to '$($mPs.Groups[1].Value.Trim())'"
  }
  # cs-lib.sh:   : "${KEY:=default}"
  $mSh = [regex]::Match($libSh, ':\s*"\$\{' + [regex]::Escape($k) + ':=([^}]*)\}"')
  if ($mSh.Success -and $mSh.Groups[1].Value -ne $want) {
    $failures += "config parity: '$k' = '$want' in cs.conf but cs-lib.sh defaults to '$($mSh.Groups[1].Value)'"
  }
}
"config parity: {0} keys in cs.conf cross-checked against cs-lib.ps1 and cs-lib.sh defaults" -f $conf.Count

foreach ($s in $scenarios) {
  foreach ($k in @($s.env.Keys)) { Set-Item -Path "Env:\$k" -Value $s.env[$k] }
  try {
    $raw = & $doctor -Json 2>&1 | Out-String
    $code = $LASTEXITCODE
    $obj = $null
    try { $obj = $raw.Trim() | ConvertFrom-Json } catch { $obj = $null }
    if (-not $obj) { $failures += "$($s.name): doctor did not emit parseable JSON. raw=$($raw.Trim() -replace '\s+', ' ')"; continue }
    $byName = @{}
    foreach ($r in $obj.rows) { $byName[$r.Check] = $r }

    foreach ($rowName in $s.expect.Keys) {
      $checked++
      $want = $s.expect[$rowName]
      if (-not $byName.ContainsKey($rowName)) { $failures += "$($s.name): row '$rowName' MISSING from the report (a vanished row is the fail-open shape)"; continue }
      $got = $byName[$rowName].Status
      if ($want -ne '<ANY>' -and $got -ne $want) { $failures += "$($s.name): row '$rowName' expected $want, got $got  [detail: $($byName[$rowName].Detail)]" }
      # Universal invariant, independent of the per-scenario expectation: outside the control
      # scenario, a row under test must never render PASS.
      if ($s.name -notlike 'S1 *' -and $got -eq 'PASS') { $failures += "$($s.name): row '$rowName' rendered PASS in a BROKEN state - fail-OPEN" }
    }
    if ($s.forbidDetail) {
      foreach ($rowName in $s.forbidDetail.Keys) {
        $checked++
        $bad = $s.forbidDetail[$rowName]
        if ($byName.ContainsKey($rowName) -and $byName[$rowName].Detail -like "*$bad*") {
          $failures += "$($s.name): row '$rowName' still asserts '$bad' when the probe never measured it. detail=$($byName[$rowName].Detail)"
        }
      }
    }
    # Exit-code contract: any FAIL or NOT-CHECKED must make the doctor exit non-zero.
    $checked++
    $expectNonZero = ($obj.fail -gt 0 -or $obj.not_checked -gt 0)
    if ($expectNonZero -and $code -eq 0) { $failures += "$($s.name): fail=$($obj.fail) not_checked=$($obj.not_checked) but exit code was 0" }
    if (-not $expectNonZero -and $code -ne 0) { $failures += "$($s.name): all rows measured-and-ok but exit code was $code" }

    $tag = if ($failures.Count) { '' } else { '' }
    "{0,-62} fail={1} warn={2} nc={3} pass={4} exit={5}{6}" -f $s.name, $obj.fail, $obj.warn, $obj.not_checked, $obj.pass, $code, $tag
  } finally {
    foreach ($k in @($s.env.Keys)) { Remove-Item -Path "Env:\$k" -ErrorAction SilentlyContinue }
  }
}

Remove-Item $emptyWin, $badWin -Recurse -Force -ErrorAction SilentlyContinue

""
if ($failures.Count) {
  "ASSERTION FAILURES ($($failures.Count) of $checked):"
  $failures | ForEach-Object { "  - $_" }
  "FAILED:cs-doctor-failclosed $($failures.Count)/$checked assertions failed"
  exit 1
}
"FAILED-state coverage: $($scenarios.Count - 1) broken scenarios + 1 healthy control; $checked assertions."
"SUCCESS:cs-doctor-failclosed all $checked assertions held"
exit 0
