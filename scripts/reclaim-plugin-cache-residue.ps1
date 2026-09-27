<#
.SYNOPSIS
  Reclaim orphaned plugin-cache build residue under ~/.claude/plugins/cache.

.DESCRIPTION
  Claude Code's plugin installer clones marketplace repos into throwaway staging
  directories named temp_git_<epochms>_<rand> and temp_subdir_<epochms>_<rand>.clone
  directly under ~/.claude/plugins/cache, then copies what it needs into the named
  marketplace dir and ABANDONS the staging dir. Nothing ever removes them.

  This script removes ONLY those staging dirs, and only when every safety gate passes.

  SAFETY GATES (all must pass per directory, else the dir is SKIPPED):
    G1 PATTERN  - basename matches ^temp_(git|subdir)_\d{13}_[a-z0-9]+(\.clone)?$
    G2 PARENT   - parent dir is EXACTLY the cache root (no recursion, no nesting)
    G3 AGE      - epoch embedded in the name is older than -MinAgeHours (default 6)
    G4 MTIME    - LastWriteTime is older than -MinAgeHours too
    G5 ORIGIN   - if it contains .git, `git remote get-url origin` must succeed
                  (an origin-less clone cannot be proven re-fetchable -> SKIP)
    G6 AUTHOR   - no commit reachable from HEAD but absent from all remotes may be
                  authored by the local git user.email (never destroy owner work)

  DRY RUN IS THE DEFAULT. Pass -Apply to actually delete.

.PARAMETER Apply
  Actually delete. Without this, the script only reports.

.PARAMETER MinAgeHours
  Minimum age (by both name-epoch and mtime) before a dir is eligible. Default 6.

.PARAMETER CacheRoot
  Override the cache root. Used by -SelfTest.

.PARAMETER SelfTest
  Run the both-states proof: build a temp fixture containing one dir that SHOULD be
  reclaimed and several that MUST be refused (bad pattern, too new, nested, no origin,
  owner-authored commit), assert the gates classify each correctly, exit non-zero on
  any misclassification.

.NOTES
  Never touches: named marketplace dirs, ~/.claude.json, installed_plugins.json,
  known_marketplaces.json, or anything outside the cache root.
#>
[CmdletBinding()]
param(
  [switch]$Apply,
  [double]$MinAgeHours = 6,
  [string]$CacheRoot = "$env:USERPROFILE\.claude\plugins\cache",
  [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# The ONLY name shape this script will ever delete.
$RESIDUE_RX = '^temp_(git|subdir)_(\d{13})_[a-z0-9]+(\.clone)?$'

function Get-LocalGitEmail {
  try { $e = (& git config --global --get user.email 2>$null); if ($e) { return ($e -join '').Trim() } } catch {}
  return ''
}

<#
 Classify one directory. Returns an object with Eligible + Reason.
 This is the single decision point; both the reclaim run and the self-test call it.
#>
function Test-ResidueDir {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][double]$MinAgeHours,
    [string]$OwnerEmail = ''
  )
  $leaf = [System.IO.Path]::GetFileName($Path)
  $res  = [pscustomobject]@{ Path=$Path; Name=$leaf; Eligible=$false; Reason=''; Bytes=0L; Files=0 }

  # G1 PATTERN
  if ($leaf -notmatch $RESIDUE_RX) { $res.Reason = 'G1-PATTERN: name is not a residue staging dir'; return $res }
  $epochMs = [long]$Matches[2]

  # G2 PARENT - must sit directly in the cache root
  $parent = [System.IO.Path]::GetFullPath([System.IO.Path]::GetDirectoryName($Path)).TrimEnd('\')
  $rootN  = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
  if ($parent -ne $rootN) { $res.Reason = "G2-PARENT: parent '$parent' is not the cache root"; return $res }

  # G3 AGE by embedded epoch
  $nameTime = [DateTimeOffset]::FromUnixTimeMilliseconds($epochMs).ToLocalTime().DateTime
  $ageName  = ((Get-Date) - $nameTime).TotalHours
  if ($ageName -lt $MinAgeHours) {
    $res.Reason = ("G3-AGE: name-epoch age {0:N2}h < {1}h (may be in flight)" -f $ageName, $MinAgeHours); return $res
  }

  # G4 AGE by mtime
  $ageMt = ((Get-Date) - (Get-Item -LiteralPath $Path -Force).LastWriteTime).TotalHours
  if ($ageMt -lt $MinAgeHours) {
    $res.Reason = ("G4-MTIME: mtime age {0:N2}h < {1}h (may be in flight)" -f $ageMt, $MinAgeHours); return $res
  }

  # G5/G6 only apply when it is a git clone
  if (Test-Path -LiteralPath (Join-Path $Path '.git')) {
    $origin = ''
    try { $origin = ((& git -C $Path remote get-url origin 2>$null) -join '').Trim() } catch {}
    if (-not $origin) { $res.Reason = 'G5-ORIGIN: git dir with no origin - cannot prove re-fetchable'; return $res }

    # G6 - any commit reachable from HEAD but on no remote, authored by the owner?
    if ($OwnerEmail) {
      $mine = ''
      try { $mine = ((& git -C $Path log --format='%ae' HEAD --not --remotes 2>$null) -join "`n") } catch {}
      if ($mine -and ($mine -split "`n" | Where-Object { $_.Trim() -eq $OwnerEmail })) {
        $res.Reason = "G6-AUTHOR: has local commit(s) authored by $OwnerEmail - owner work, never delete"; return $res
      }
    }
  }

  $res.Eligible = $true
  $res.Reason   = 'OK: all gates passed'
  return $res
}

function Measure-Dir {
  param([string]$Path)
  $opt = New-Object System.IO.EnumerationOptions
  $opt.RecurseSubdirectories = $true
  $opt.IgnoreInaccessible = $true
  $opt.AttributesToSkip = [System.IO.FileAttributes]::ReparsePoint
  $b = 0L; $n = 0
  try {
    $di = New-Object System.IO.DirectoryInfo $Path
    foreach ($f in $di.EnumerateFiles('*', $opt)) { $b += $f.Length; $n++ }
  } catch {}
  return @($b, $n)
}

# ----------------------------------------------------------------------------- self-test
if ($SelfTest) {
  $fail = 0
  $fx = Join-Path ([System.IO.Path]::GetTempPath()) ("residue_selftest_" + [guid]::NewGuid().ToString('N').Substring(0,8))
  New-Item -ItemType Directory -Force -Path $fx | Out-Null
  $owner = Get-LocalGitEmail
  if (-not $owner) { $owner = 'selftest-owner@example.invalid' }
  $oldMs = [DateTimeOffset]::UtcNow.AddDays(-5).ToUnixTimeMilliseconds()
  $newMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

  function New-Fx { param($n) $p = Join-Path $fx $n; New-Item -ItemType Directory -Force -Path $p | Out-Null; return $p }

  # --- cases that MUST be eligible (the GOOD state) ---
  $good = @()
  $good += ,@('plain old residue, no git', (New-Fx "temp_git_${oldMs}_aaa111"))
  $good += ,@('old .clone subdir',         (New-Fx "temp_subdir_${oldMs}_bbb222.clone"))
  # an old clone WITH a legit origin and only upstream-authored local commits
  $gitOk = New-Fx "temp_git_${oldMs}_ccc333"
  & git -C $gitOk init -q 2>$null
  & git -C $gitOk remote add origin https://github.com/example/upstream.git 2>$null
  'x' | Set-Content (Join-Path $gitOk 'f.txt')
  & git -C $gitOk add -A 2>$null
  & git -C $gitOk -c user.name=Up -c user.email=upstream@example.invalid commit -q -m up 2>$null
  $good += ,@('clone w/ origin, upstream-authored commit', $gitOk)

  # --- cases that MUST be refused (the BROKEN state) ---
  $bad = @()
  $bad += ,@('G1 wrong name',        (New-Fx 'claude-plugins-official'),            'G1-PATTERN')
  $bad += ,@('G1 no epoch',          (New-Fx 'temp_git_notanepoch_xx'),             'G1-PATTERN')
  $bad += ,@('G3 too new',           (New-Fx "temp_git_${newMs}_ddd444"),           'G3-AGE')
  $gitNoOrigin = New-Fx "temp_git_${oldMs}_eee555"
  & git -C $gitNoOrigin init -q 2>$null
  $bad += ,@('G5 git w/o origin',    $gitNoOrigin,                                   'G5-ORIGIN')
  $gitMine = New-Fx "temp_git_${oldMs}_fff666"
  & git -C $gitMine init -q 2>$null
  & git -C $gitMine remote add origin https://github.com/example/upstream.git 2>$null
  'y' | Set-Content (Join-Path $gitMine 'f.txt')
  & git -C $gitMine add -A 2>$null
  & git -C $gitMine -c user.name=Me -c "user.email=$owner" commit -q -m mine 2>$null
  $bad += ,@('G6 owner-authored',    $gitMine,                                       'G6-AUTHOR')
  # nested: right name, wrong parent
  $nestHost = New-Fx 'nesting_host'
  $nested = Join-Path $nestHost "temp_git_${oldMs}_ggg777"
  New-Item -ItemType Directory -Force -Path $nested | Out-Null
  $bad += ,@('G2 nested one level down', $nested,                                    'G2-PARENT')

  # backdate mtimes so G4 cannot mask G3/G5/G6
  foreach ($c in ($good + $bad)) {
    $p = $c[1]
    if ((Split-Path $p -Leaf) -ne "temp_git_${newMs}_ddd444") {
      try { (Get-Item -LiteralPath $p -Force).LastWriteTime = (Get-Date).AddDays(-5) } catch {}
    }
  }

  Write-Output '=== SELF-TEST: GOOD state (each MUST be Eligible) ==='
  foreach ($c in $good) {
    $r = Test-ResidueDir -Path $c[1] -Root $fx -MinAgeHours $MinAgeHours -OwnerEmail $owner
    $ok = $r.Eligible
    if (-not $ok) { $fail++ }
    Write-Output ("  [{0}] {1,-42} -> Eligible={2}  {3}" -f $(if($ok){'PASS'}else{'FAIL'}), $c[0], $r.Eligible, $r.Reason)
  }

  Write-Output '=== SELF-TEST: BROKEN state (each MUST be refused by the named gate) ==='
  foreach ($c in $bad) {
    $r = Test-ResidueDir -Path $c[1] -Root $fx -MinAgeHours $MinAgeHours -OwnerEmail $owner
    $ok = ((-not $r.Eligible) -and $r.Reason.StartsWith($c[2]))
    if (-not $ok) { $fail++ }
    Write-Output ("  [{0}] {1,-42} -> Eligible={2}  {3}" -f $(if($ok){'PASS'}else{'FAIL'}), $c[0], $r.Eligible, $r.Reason)
  }

  Remove-Item -LiteralPath $fx -Recurse -Force -ErrorAction SilentlyContinue
  if ($fail -gt 0) { Write-Output "FAILED:reclaim-selftest $fail misclassification(s)"; exit 1 }
  Write-Output 'SUCCESS:reclaim-selftest all gates fire on broken input and pass on good input'
  exit 0
}

# ----------------------------------------------------------------------------- main
if (-not (Test-Path -LiteralPath $CacheRoot)) { Write-Output "FAILED:reclaim cache root not found: $CacheRoot"; exit 1 }
$owner = Get-LocalGitEmail
Write-Output ("cache_root   = " + $CacheRoot)
Write-Output ("min_age_hours= " + $MinAgeHours)
Write-Output ("owner_email  = " + $(if($owner){$owner}else{'<unset>'}))
Write-Output ("mode         = " + $(if($Apply){'APPLY'}else{'DRY-RUN'}))
Write-Output ''

$elig = New-Object System.Collections.Generic.List[object]
$skip = New-Object System.Collections.Generic.List[object]

foreach ($d in [System.IO.Directory]::EnumerateDirectories($CacheRoot)) {
  $r = Test-ResidueDir -Path $d -Root $CacheRoot -MinAgeHours $MinAgeHours -OwnerEmail $owner
  if ($r.Eligible) {
    $m = Measure-Dir $d
    $r.Bytes = $m[0]; $r.Files = $m[1]
    $elig.Add($r)
  } else { $skip.Add($r) }
}

$tb = ($elig | Measure-Object -Sum Bytes).Sum; if (-not $tb) { $tb = 0 }
$tf = ($elig | Measure-Object -Sum Files).Sum; if (-not $tf) { $tf = 0 }

Write-Output ("ELIGIBLE dirs = {0}   files = {1}   bytes = {2}   MB = {3}" -f $elig.Count, $tf, $tb, [math]::Round($tb/1MB,2))
Write-Output ("SKIPPED  dirs = {0}" -f $skip.Count)
Write-Output '=== skip reasons (grouped) ==='
$skip | Group-Object { ($_.Reason -split ':')[0] } | Sort-Object Count -Desc |
  ForEach-Object { Write-Output ("  {0,-14} {1}" -f $_.Name, $_.Count) }

if (-not $Apply) {
  Write-Output ''
  Write-Output 'DRY-RUN: nothing removed. Re-run with -Apply to reclaim.'
  Write-Output 'SUCCESS:reclaim-dryrun'
  exit 0
}

Write-Output ''
$removed = 0; $failed = 0; $freed = 0L
foreach ($r in $elig) {
  # re-assert the gates immediately before the destructive call
  $recheck = Test-ResidueDir -Path $r.Path -Root $CacheRoot -MinAgeHours $MinAgeHours -OwnerEmail $owner
  if (-not $recheck.Eligible) { Write-Output ("RECHECK-REFUSED " + $r.Name + " :: " + $recheck.Reason); $failed++; continue }
  try {
    Remove-Item -LiteralPath $r.Path -Recurse -Force -ErrorAction Stop
    $removed++; $freed += $r.Bytes
  } catch {
    Write-Output ("REMOVE-FAILED " + $r.Name + " :: " + $_.Exception.Message); $failed++
  }
}
Write-Output ("removed_dirs = {0}  failed = {1}  freed_bytes = {2}  freed_MB = {3}" -f $removed, $failed, $freed, [math]::Round($freed/1MB,2))
if ($failed -gt 0) { Write-Output "FAILED:reclaim $failed dir(s) not removed"; exit 1 }
Write-Output 'SUCCESS:reclaim'
exit 0
