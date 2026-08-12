# test-cs-doctor-failclosed -- the BOTH-STATES harness for cs-doctor's fail-closed contract.
#
# WHY THIS FILE EXISTS. cs doctor reads `0 FAIL, 0 WARN, N PASS` on a healthy box. Any claim that
# it "now fails closed", validated only against that box, is a probe that is silent in both states
# and therefore measures nothing. This harness reaches the BROKEN state on demand (via the
# CS_FORCE_WSL_* injection seam in cs-lib.ps1) and asserts the row goes FAIL or NOT-CHECKED --
# and, in the paired control, that the SAME row goes PASS when the input is fine. A test that only
# checks the broken direction cannot tell a fail-closed row from a row that is always red.
#
# It also pins the specific defects that motivated each rewrite:
#   * ROUND 1 -- on a probe TIMEOUT the DB row printed "sqlite3 or operon-cli.db not found", a
#     factual claim about a file it never looked at. S2 asserts that string cannot reappear.
#   * ROUND 2 / D1 -- /claude-science and /cs routed to a stale checkout, so every fix above was
#     unreachable through the command the owner types. S13-S16 drive the route row through missing,
#     nonexistent, STALE and unreadable, and S1's control asserts it goes PASS when they agree.
#   * ROUND 2 / D2 -- the CS_FORCE_* seam was unarmed and unmarked, so `CS_FORCE_WSL_DB=
#     'ok|wal|999M'` produced a fabricated "[+] DB PASS ... 0 FAIL ... exit 0". S18 asserts an
#     un-armed variable is REFUSED and its payload never reaches the report; every armed scenario
#     asserts the FAIL banner + [INJECTED] tags; S17 is the un-armed control that stops the banner
#     from being trivially always-on.
# NOT covered here (stated so it is not assumed): that the doctor does not WRITE into the backup
# root. That needs the real filesystem, so it lives in test-cs-backup-readonly.py.
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

# --- scratch slash-command dirs (for the route-parity row) ---------------------------------------
# cs-doctor reads claude-science.md / cs.md out of CS_COMMANDS_DIR and asserts they route to code
# byte-identical to the doctor that is running. Pointing that at scratch dirs keeps the harness
# hermetic AND lets the D1 defect itself be reproduced on demand: a command file that names a
# stale dispatcher must turn the row red.
$cmdGood = Join-Path $env:TEMP "cs-test-cmd-good-$stamp"
$cmdMissing = Join-Path $env:TEMP "cs-test-cmd-missing-$stamp"
$cmdGhost = Join-Path $env:TEMP "cs-test-cmd-ghost-$stamp"
$cmdStale = Join-Path $env:TEMP "cs-test-cmd-stale-$stamp"
$staleTree = Join-Path $env:TEMP "cs-test-staletree-$stamp"
foreach ($d in @($cmdGood, $cmdMissing, $cmdGhost, $cmdStale, $staleTree)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
# A second dispatcher whose cs-doctor.ps1 is NOT this one -- exactly the round-1 shape, where the
# command files named a checkout holding a 5,590 B doctor while a 13,852 B doctor was deployed.
Set-Content -LiteralPath (Join-Path $staleTree 'cs.ps1') -Value '# stale dispatcher' -NoNewline
Set-Content -LiteralPath (Join-Path $staleTree 'cs-doctor.ps1') -Value '# stale doctor, different bytes' -NoNewline
function CmdFixture([string]$dir, [string]$name, [string]$dispatcher) {
  Set-Content -LiteralPath (Join-Path $dir $name) -Value @"
---
description: scratch fixture
---
``````
pwsh -NoProfile -File $dispatcher `$ARGUMENTS
``````
"@
}
$realDispatcher = Join-Path $PSScriptRoot 'cs.ps1'
CmdFixture $cmdGood 'claude-science.md' $realDispatcher
CmdFixture $cmdGood 'cs.md' $realDispatcher
CmdFixture $cmdMissing 'claude-science.md' $realDispatcher          # cs.md deliberately absent
CmdFixture $cmdGhost 'claude-science.md' (Join-Path $env:TEMP "cs-nope-$stamp/cs.ps1")
CmdFixture $cmdGhost 'cs.md' (Join-Path $env:TEMP "cs-nope-$stamp/cs.ps1")
CmdFixture $cmdStale 'claude-science.md' (Join-Path $staleTree 'cs.ps1')
CmdFixture $cmdStale 'cs.md' (Join-Path $staleTree 'cs.ps1')

# Applied to EVERY scenario, then overridden per scenario; `envRemove` drops a key entirely.
# CS_FAULT_INJECTION=1 is what ARMS the CS_FORCE_* seam -- round 1 honoured those variables with no
# arming and no marker at all, which is defect D2.
$baseEnv = @{ CS_FAULT_INJECTION = '1'; CS_COMMANDS_DIR = $cmdGood }
# A distro that cannot exist: wsl.exe errors immediately, so the two un-armed scenarios below stay
# fast and hermetic (no live VM, no injection) instead of waiting on real probes.
$deadDistro = "__cs_no_such_distro_$stamp"

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
      'DB' = 'PASS'; 'Backup freshness' = 'PASS'; 'Backup restorable' = 'PASS'; 'daemon detail' = 'INFO'
      'WSL disk free' = 'PASS' } }

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

  # --- D1: the slash command must run THIS code -------------------------------------------------
  # Round 1 declared the rename "works" from a command LISTING while both files still routed to a
  # stale checkout. These four drive the row through every route state it can reach.
  @{ name = 'S13 route: /cs missing from the commands dir'; env = (With @{ CS_COMMANDS_DIR = $cmdMissing }); expect = @{ 'Slash-command route' = 'FAIL' } }
  @{ name = 'S14 route: dispatcher named does not exist'; env = (With @{ CS_COMMANDS_DIR = $cmdGhost }); expect = @{ 'Slash-command route' = 'FAIL' } }
  @{ name = 'S15 route: dispatcher exists but is STALE (the D1 shape)'; env = (With @{ CS_COMMANDS_DIR = $cmdStale }); expect = @{ 'Slash-command route' = 'FAIL' }
    requireDetail = @{ 'Slash-command route' = 'STALE code' } }
  @{ name = 'S16 route: commands dir absent entirely'; env = (With @{ CS_COMMANDS_DIR = (Join-Path $env:TEMP "cs-no-such-dir-$stamp") }); expect = @{ 'Slash-command route' = 'NOT-CHECKED' } }

  # --- D2: an injected run must never be able to look clean -------------------------------------
  # S17/S18 are the ONLY scenarios that run un-armed, so they are also the control proving the
  # banner is not simply always-on. They use a nonexistent distro so no live VM is touched.
  @{ name = 'S17 control: NO injection at all -> no banner, no [INJECTED]'; env = @{ CS_DISTRO = $deadDistro }; envRemove = @('CS_FAULT_INJECTION'); expect = @{} }
  @{ name = 'S18 CS_FORCE_* set WITHOUT arming -> REFUSED, not obeyed'; env = @{ CS_DISTRO = $deadDistro; CS_FORCE_WSL_DB = 'ok|wal|999M' }; envRemove = @('CS_FAULT_INJECTION'); expect = @{}
    forbidAnyDetail = @('999M') }

  # --- R3/R4: a row must not INVENT a number or leak a raw error string ---------------------------
  # ROUND 2 shipped `$dg = 0; [void][int]::TryParse(...)` -- the parse result was DISCARDED, so an
  # unparseable df reply left the initialiser in place and the row printed a confident
  # "WSL disk free WARN 0GB (floor 10GB)". Same fail-open class as the DB row's collapsed branches;
  # the fabricated value just happened to be a default rather than a sentence. S1 is the control
  # (a parseable 99 must still read PASS), so these cannot be satisfied by an always-NOT-CHECKED row.
  @{ name = 'S19 disk probe unparseable (wsl.exe error text)'; env = (With @{ CS_FORCE_WSL_DISK = 'There is no distribution with the supplied name.' }); expect = @{ 'WSL disk free' = 'NOT-CHECKED' }
    forbidDetail = @{ 'WSL disk free' = '0GB (floor' } }
  @{ name = 'S20 disk probe empty'; env = (With @{ CS_FORCE_WSL_DISK = '__EMPTY__' }); expect = @{ 'WSL disk free' = 'NOT-CHECKED' } }
  @{ name = 'S21 DB reply unparseable (not the 3-field shape)'; env = (With @{ CS_FORCE_WSL_DB = 'Error: 0x8007019e The Windows Subsystem for Linux has no installed distributions.' }); expect = @{ 'DB' = 'NOT-CHECKED' }
    forbidDetail = @{ 'DB' = 'integrity=Error' } }
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

# --- UNIT: Get-CSWatchdogActionVerdict + Format-CSProbeReply --------------------------------------
# These two are exercised directly rather than through a doctor run, for a reason worth stating:
# driving them end-to-end would need either a real edit to ClaudeScienceWatchdog (mutating a live
# always-on task from a test) or a THIRD CS_FORCE_* injection seam. Every injection seam is one
# more way to order the tool to print a green, which is defect D2 -- so the rule here is to make the
# judgement a pure function and test the function.
#
# WHAT THEY EXIST FOR (measured 2026-08-12):
#   * the watchdog task launched cs-watchdog.ps1 out of a LINKED GIT WORKTREE while three separate
#     doctor rows (registered / trigger / instances) all read PASS, because not one of them looks
#     at $task.Actions;
#   * a wsl.exe error reached the DB row as UTF-16-decoded-as-ANSI spaced text.
# Each block carries its CONTROL: the durable-clone case must NOT be flagged ephemeral, the
# matching-content case must PASS, and a clean short reply must pass through the sanitizer byte for
# byte. Without those, an always-FAIL row and an always-mangling sanitizer would both score green.
. (Join-Path $PSScriptRoot 'cs-lib.ps1')
$wtRoot = Join-Path $env:TEMP "cs-test-wt-$stamp"          # fake LINKED worktree (.git is a FILE)
$cloneRoot = Join-Path $env:TEMP "cs-test-clone-$stamp"    # fake ordinary clone (.git is a DIR)
New-Item -ItemType Directory -Path $wtRoot -Force | Out-Null
New-Item -ItemType Directory -Path $cloneRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $cloneRoot '.git') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $wtRoot '.git') -Value 'gitdir: C:/Users/x/source/repo/.git/worktrees/scratch' -NoNewline
$wtScript = Join-Path $wtRoot 'cs-watchdog.ps1'
$refScript = Join-Path $cloneRoot 'cs-watchdog.ps1'
$staleScript = Join-Path $cloneRoot 'cs-watchdog-stale.ps1'
Set-Content -LiteralPath $wtScript -Value '# watchdog' -NoNewline
Set-Content -LiteralPath $refScript -Value '# watchdog' -NoNewline
Set-Content -LiteralPath $staleScript -Value '# watchdog, older bytes' -NoNewline
function FakeTask([string]$arguments) {
  if ($null -eq $arguments) { return [pscustomobject]@{ Actions = @() } }
  return [pscustomobject]@{ Actions = @([pscustomobject]@{ Execute = 'powershell.exe'; Arguments = $arguments }) }
}
$argShape = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"'
# DEFERRED, NOT EAGER. Each case is a scriptblock invoked inside try/catch, because a unit that
# THROWS must still say which case threw. Measured while mutation-testing this very file: deleting
# the "does the target exist" guard made Get-FileHash throw on a missing path, which (under
# $ErrorActionPreference='Stop') killed the whole harness -- exit 1 with ZERO assertion lines. That
# is a detection, but a useless one: it names no defect, and an eagerly-built @( ... ) array cannot
# even reach the later cases. A crash is now an assertion failure with the case name attached.
$unit = @(
  @{ n = 'W1 no task at all'; call = { Get-CSWatchdogActionVerdict -Task $null -ReferenceScript $refScript }; want = 'FAIL' }
  @{ n = 'W2 task with no action'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask $null) -ReferenceScript $refScript }; want = 'NOT-CHECKED' }
  @{ n = 'W3 action names no -File script'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask '-Command Start-Sleep') -ReferenceScript $refScript }; want = 'NOT-CHECKED' }
  @{ n = 'W4 launches a path that does not exist'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask ($argShape -f (Join-Path $env:TEMP "cs-gone-$stamp\cs-watchdog.ps1"))) -ReferenceScript $refScript }; want = 'FAIL'; need = 'DOES NOT EXIST' }
  @{ n = 'W5 launches out of an EPHEMERAL worktree (the live defect)'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask ($argShape -f $wtScript)) -ReferenceScript $refScript }; want = 'FAIL'; need = 'EPHEMERAL' }
  @{ n = 'W6 durable path but STALE bytes'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask ($argShape -f $staleScript)) -ReferenceScript $refScript }; want = 'FAIL'; need = 'STALE' }
  @{ n = 'W7 CONTROL durable + matching bytes'; call = { Get-CSWatchdogActionVerdict -Task (FakeTask ($argShape -f $refScript)) -ReferenceScript $refScript }; want = 'PASS' }
)
foreach ($u in $unit) {
  $checked++
  $got = $null
  try { $got = & $u.call } catch { $failures += "unit $($u.n): THREW instead of returning a verdict - $($_.Exception.Message)"; continue }
  if ($got.Status -ne $u.want) { $failures += "unit $($u.n): expected $($u.want), got $($got.Status)  [detail: $($got.Detail)]" }
  elseif ($u.need -and $got.Detail -notlike "*$($u.need)*") { $failures += "unit $($u.n): detail should name '$($u.need)' so the operator can act. detail=$($got.Detail)" }
}
# CONTROL for the worktree detector itself: an ordinary clone must come back $null, or W5 would be
# proving nothing more than "this function always says ephemeral".
$checked++
if ($null -ne (Test-CSEphemeralWorktree $refScript)) { $failures += "unit W8 CONTROL: an ordinary clone (.git DIRECTORY) was reported as an ephemeral worktree - the detector is always-on" }
$checked++
if ($null -eq (Test-CSEphemeralWorktree $wtScript)) { $failures += 'unit W9: a linked worktree (.git FILE with gitdir:.../worktrees/) was NOT detected' }

$nulText = "T`0h`0e`0r`0e`0 `0i`0s`0 `0n`0o`0"      # UTF-16LE ASCII read as single-byte = NUL-interleaved
$sanCases = @(
  @{ n = 'F1 NUL-interleaved wsl.exe error'; call = { Format-CSProbeReply $nulText }; want = 'There is no' }
  @{ n = 'F2 control chars and newlines collapsed'; call = { Format-CSProbeReply "a`r`nb`tc" }; want = 'a b c' }
  @{ n = 'F3 CONTROL a clean reply is unchanged'; call = { Format-CSProbeReply 'ok|wal|2.9M' }; want = 'ok|wal|2.9M' }
)
foreach ($c in $sanCases) {
  $checked++
  $g = $null
  try { $g = & $c.call } catch { $failures += "unit $($c.n): THREW - $($_.Exception.Message)"; continue }
  if ($g -ne $c.want) { $failures += "unit $($c.n): expected '$($c.want)', got '$g'" }
}
$checked++
$long = Format-CSProbeReply ('x' * 500)
if ($long.Length -gt 160 -or $long -notlike '*truncated*') { $failures += "unit F4: a 500-char reply was not bounded (len=$($long.Length)) - one bad probe pushes the table off-screen" }
$checked++
if ((Format-CSProbeReply $nulText) -match "`0") { $failures += 'unit F5: NUL survived the sanitizer' }
"unit checks: 9 watchdog-action + 5 sanitizer, each with its control"

foreach ($s in $scenarios) {
  $envSet = @{}
  foreach ($k in $baseEnv.Keys) { $envSet[$k] = $baseEnv[$k] }
  foreach ($k in @($s.env.Keys)) { $envSet[$k] = $s.env[$k] }
  # @($null) is a ONE-element array holding $null, so an absent optional field must be filtered,
  # not just wrapped -- otherwise Remove($null) throws and a bare -like "**" matches every row.
  foreach ($k in @($s.envRemove | Where-Object { $_ })) { [void]$envSet.Remove($k) }
  foreach ($k in @($envSet.Keys)) { Set-Item -Path "Env:\$k" -Value $envSet[$k] }
  # The banner expectation is DERIVED from the environment actually set, not hand-written per
  # scenario, so it cannot drift out of step with the scenario it describes.
  $anyForce = @($envSet.Keys | Where-Object { $_ -like 'CS_FORCE_*' }).Count -gt 0
  $armed = ($envSet['CS_FAULT_INJECTION'] -eq '1')
  $wantBanner = if ($anyForce -and $armed) { 'used' } elseif ($anyForce) { 'refused' } else { 'none' }
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
    if ($s.requireDetail) {
      foreach ($rowName in $s.requireDetail.Keys) {
        $checked++
        $need = $s.requireDetail[$rowName]
        if (-not ($byName.ContainsKey($rowName) -and $byName[$rowName].Detail -like "*$need*")) {
          $failures += "$($s.name): row '$rowName' should name '$need' so the operator can act on it. detail=$($byName[$rowName].Detail)"
        }
      }
    }
    foreach ($bad in @($s.forbidAnyDetail | Where-Object { $_ })) {
      $checked++
      $hit = @($obj.rows | Where-Object { "$($_.Detail)" -like "*$bad*" })
      if ($hit.Count) { $failures += "$($s.name): '$bad' reached the report from a REFUSED injection - row '$($hit[0].Check)': $($hit[0].Detail)" }
    }

    # --- FAULT-INJECTION DISCLOSURE (D2) ----------------------------------------------------------
    # Round 1's seam obeyed CS_FORCE_* with no arming and no marker, so an auditor got a fabricated
    # "[+] DB PASS ... size=999M / 0 FAIL / exit 0". Three things are asserted here, and S17/S18 are
    # the un-armed control that stops these from being trivially satisfiable by an always-on banner.
    $checked++
    $banner = @($obj.rows | Where-Object Check -eq 'Fault injection')
    $tagged = @($obj.rows | Where-Object { "$($_.Detail)" -like '`[INJECTED`]*' })
    switch ($wantBanner) {
      'used' {
        if ($banner.Count -ne 1) { $failures += "$($s.name): injected run has no 'Fault injection' banner row - the report reads as a real measurement" }
        elseif ($banner[0].Status -ne 'FAIL') { $failures += "$($s.name): 'Fault injection' banner is $($banner[0].Status), must be FAIL so an injected run cannot exit 0" }
        elseif ($banner[0].Detail -notlike '*SIMULATED*') { $failures += "$($s.name): banner does not say SIMULATED. detail=$($banner[0].Detail)" }
        if (-not $tagged.Count) { $failures += "$($s.name): injection was used but no row carries the [INJECTED] tag" }
        if (-not @($obj.injection.used).Count) { $failures += "$($s.name): JSON injection.used is empty on an injected run" }
      }
      'refused' {
        if ($banner.Count -ne 1) { $failures += "$($s.name): CS_FORCE_* was set without arming and nothing reported it" }
        elseif ($banner[0].Status -ne 'FAIL' -or $banner[0].Detail -notlike '*REFUSED*') { $failures += "$($s.name): un-armed injection must render FAIL/REFUSED, got $($banner[0].Status): $($banner[0].Detail)" }
        if ($tagged.Count) { $failures += "$($s.name): a REFUSED injection still tagged $($tagged.Count) row(s) [INJECTED] - it was obeyed after all" }
      }
      'none' {
        if ($banner.Count) { $failures += "$($s.name): a clean run grew a 'Fault injection' row - the banner is always-on and therefore measures nothing" }
        if ($tagged.Count) { $failures += "$($s.name): a clean run tagged $($tagged.Count) row(s) [INJECTED]" }
        if (@($obj.injection.used).Count) { $failures += "$($s.name): JSON injection.used non-empty on a clean run" }
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
    foreach ($k in @($envSet.Keys)) { Remove-Item -Path "Env:\$k" -ErrorAction SilentlyContinue }
  }
}

Remove-Item $emptyWin, $badWin, $cmdGood, $cmdMissing, $cmdGhost, $cmdStale, $staleTree, $wtRoot, $cloneRoot -Recurse -Force -ErrorAction SilentlyContinue

""
if ($failures.Count) {
  "ASSERTION FAILURES ($($failures.Count) of $checked):"
  $failures | ForEach-Object { "  - $_" }
  "FAILED:cs-doctor-failclosed $($failures.Count)/$checked assertions failed"
  exit 1
}
"FAILED-state coverage: $($scenarios.Count - 2) broken scenarios + 2 controls (S1 healthy inputs, S17 no injection); $checked assertions."
"SUCCESS:cs-doctor-failclosed all $checked assertions held"
exit 0
