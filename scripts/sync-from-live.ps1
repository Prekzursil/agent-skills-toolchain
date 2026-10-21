<#
.SYNOPSIS
  Sync LIVE harness artifacts back INTO this repo. The missing half of the sync architecture.

.DESCRIPTION
  The repo already ships sync-rules.ps1 / sync-hooks.ps1 / sync-skills.ps1, which all push
  repo -> live. Nothing ever pushed live -> repo, so anything authored in ~/.claude was
  ARCHITECTURALLY ORPHANED: it could never reach version control no matter how disciplined
  the author was.

  Measured 2026-07-18, before this script existed:
      rules      83/83  files orphaned (100%)   incl. windows-shell.md and
                                                single-signal-verification.md, both referenced
                                                as non-negotiables by AGENTS.md
      agents     18/18  orphaned (100%)  -- the repo had NO agents/ directory at all
      commands   71/71  orphaned (100%)  -- the repo had NO commands/ directory at all
      hooks      56/164 orphaned
      skills    234/286 orphaned
      TOTAL     462 files / 2.73 MB of harness with no version control.

  This script closes that hole. It is deliberately ONE-WAY (live -> repo) so it cannot conflict
  with the existing repo -> live scripts: each direction has exactly one writer. Reconciling
  both directions automatically was considered and REJECTED -- a bad reconcile silently loses
  harness work, which is the exact damage this exists to prevent. Instead, -Drift reports
  divergence and a human decides.

  EXCLUSIONS ARE LOAD-BEARING, NOT COSMETIC. The skills tree is 357 MB raw but 14 MB clean:
  a vendored .venv under crypto-ctf/ alone accounts for most of the 334 MB difference. A naive
  copy would commit hundreds of MB of third-party dependencies into git permanently -- git does
  not forget, so this mistake is not cleanly reversible.

  SAFETY
    * NEVER writes to the live tree. Live is read-only here, in both directions of intent.
    * NEVER deletes from the repo unless -Prune is passed explicitly.
    * Refuses to run if the repo has staged changes, so its output is always reviewable as a
      clean, self-contained diff.

  ---------------------------------------------------------------------------------------
  HARDENING PASS 2026-07-18 (unit B7). Every item below was reproduced by a test in
  scripts/test_sync_from_live.py before it was fixed; the suite is the regression net.

    1. "NO DRIFT" WAS AN UNEARNED CLAIM. Run against the real trees, the script printed three
       "REPO-OWNED, not overwritten" lines and then "NO DRIFT: every shared file is
       byte-identical" seven lines later. A held file differs BY DEFINITION -- that is why it
       is held -- so the drift report was hiding precisely the divergence it exists to surface.
       Held files, loose files and case-only renames are now first-class drift rows.

    2. Test-Path GLOB-EXPANDS ITS ARGUMENT. Verified in isolation: for an existing file named
       'note[1].md', Test-Path returns False while Test-Path -LiteralPath returns True. Every
       Test-Path here took an untrusted path, so a filename containing [ ] ? or * silently
       inverted three separate decisions:
         -Prune  read a live file that EXISTS as absent, and DELETED the repo copy.  DATA LOSS.
         $dest   read an existing repo file as absent -> classified NEW -> bypassed both the
                 repo-owned hold list and the drift row -> a held file could be overwritten.
         .git    nested-repo detection failed under a bracketed directory -> a third-party
                 clone would be vendored in, the crypto-ctf/RsaCtfTool failure all over again.
       All path probes are now -LiteralPath. No such filename exists in the live tree today
       (measured: 0 of 18,628), so this was latent, not firing.

    3. TWO UNREADABLE FILES COMPARED EQUAL. Get-Hash returned $null on any failure and the
       comparison was `(Get-Hash live) -eq (Get-Hash repo)`, so $null -eq $null -> TRUE -> the
       pair was counted "same" and skipped. A locked or unreadable file is now UNREADABLE, a
       distinct status that can never be mistaken for "verified identical".

    4. LINE ENDINGS PRODUCED PHANTOM DRIFT. core.autocrlf=true is set at SYSTEM level on this
       box, so a fresh clone materialises text files CRLF while the live tree is mixed
       (measured: commands 71/71 LF, skills 1511/1605 CRLF, hooks 77/218 LF). The comparison
       is raw SHA256, which line endings change but git does not see. Measured blast radius:
       342 of 2,035 shared files (16.8%) would have reported CHANGED on a fresh clone with no
       content difference at all. Such pairs are now EOL-ONLY, are not copied, and do not
       raise a drift alarm. Files containing a NUL byte are never newline-normalised.

    5. THE DETECTOR NEVER PROVED IT COULD SEE. A missing live area printed a grey note and the
       run still concluded "NO DRIFT" having compared nothing -- the single-unvalidated-probe
       failure that rules/common/single-signal-verification.md exists to stop. Two fixes: a
       missing mapped area is now a hard failure, and before any CLEAN verdict the script
       plants known divergences in a scratch fixture and must detect all of them. That makes
       "prove your detector can find a known-present item" MECHANICAL rather than remembered.

    6. -Prune IGNORED THE HOLD LIST, so a live deletion destroyed the authoritative repo copy
       the hold list was created to protect.

    7. Copies are re-hashed after writing (windows-shell.md rule 1: always verify after a
       write, the empty-file state is otherwise silent), and reparse points are reported
       instead of being silently dereferenced by Copy-Item.
  ---------------------------------------------------------------------------------------

.PARAMETER WhatIf
  Report what would change. Writes nothing. Run this first, always.

.PARAMETER Drift
  Report files that diverge between live and repo. This is the early-warning signal that
  someone edited live and repo independently.

.PARAMETER Prune
  Also delete repo files whose live counterpart is gone. Off by default: a live deletion is
  usually a local experiment, and losing repo history to it is a bad trade. Never prunes a
  file on the repo-owned hold list.

.PARAMETER Report
  'text' (default, human) or 'json'. In json mode stdout carries the machine-readable drift
  document and NOTHING else, so a hook can consume it without stripping banners. Schema is
  documented in scripts/DRIFT-REPORT-SCHEMA.md and versioned by the top-level "schema" field.

.PARAMETER ReportPath
  Also write the json document to this path. Independent of -Report, so a text run can leave
  a machine-readable artifact behind.

.PARAMETER LiveHome
  Root of the LIVE harness. Defaults to the real user profile; the test suite is the only
  caller that overrides it, pointing it at a synthetic fixture tree.

.OUTPUTS
  Exit code, for consumers that will not parse anything:
    0  CLEAN   -- no divergence, and the self-control proved the detector works
    3  DRIFT   -- divergence found (or, after a sync, divergence that a sync cannot resolve)
    1  FAILED  -- the run could not be trusted: self-control failed, a mapped live area is
                  missing, the walk hit errors, a copy failed verification, or the index
                  was dirty

.EXAMPLE
  pwsh -File scripts/sync-from-live.ps1 -WhatIf                  # always start here
  pwsh -File scripts/sync-from-live.ps1 -Drift                   # what diverged?
  pwsh -File scripts/sync-from-live.ps1 -Drift -Report json      # same, for a hook
  pwsh -File scripts/sync-from-live.ps1                          # do it
#>
[CmdletBinding()]
param(
    [switch]$WhatIf,
    [switch]$Drift,
    # P0 divergence-council fix (2026-10-01): writes require an EXPLICIT verb. Without
    # -Apply the script is dry-run-by-default (deploy-skills-daily.py precedent) --
    # '-Report json' alone must never write (it did: harness-vcs-hygiene.md documents
    # the -Report select-output-mode footgun that Copy-Item -Force'd live->repo).
    [switch]$Apply,
    [switch]$Prune,
    [string]$Root = (Split-Path $PSScriptRoot -Parent),
    [ValidateSet('text', 'json')][string]$Report = 'text',
    [string]$ReportPath,
    # Root of the LIVE harness. Defaults to the real user profile; the test suite is the
    # only caller that overrides it, pointing it at a synthetic fixture tree. Without this
    # the script cannot be tested at all -- every run would touch a running system.
    [string]$LiveHome = [Environment]::GetFolderPath('UserProfile')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$SchemaVersion = 'harness-drift/v1'
$UserProfile   = $LiveHome
$script:Quiet  = ($Report -eq 'json')

function Say {
    param([string]$Text = '', [string]$Color = 'Gray')
    if (-not $script:Quiet) { Write-Host $Text -ForegroundColor $Color }
}

# live source -> repo destination. Order is stable so output diffs cleanly run to run.
$Map = @(
    @{ Live = "$UserProfile\.claude\rules";    Repo = 'rules';          Label = 'rules' }
    @{ Live = "$UserProfile\.claude\agents";   Repo = 'agents';         Label = 'agents' }
    @{ Live = "$UserProfile\.claude\commands"; Repo = 'commands';       Label = 'commands' }
    @{ Live = "$UserProfile\.claude\hooks";    Repo = 'hooks';          Label = 'hooks' }
    @{ Live = "$UserProfile\.agents\skills";   Repo = '.agents/skills'; Label = 'skills' }
    # Root-level audit/decision docs (HARNESS-AUDIT_*.md, CONSOLIDATED-GEM-DECISIONS_*.md, ...)
    # live loose in ~\.agents. Five of them reached the repo only through MANUAL captures
    # before 2026-08-27; every future edit was orphaned -- the same architectural hole this
    # script exists to close, one level up. TopLevelOnly + Filter are load-bearing: without
    # them this entry would re-walk skills\ (its own mapping above) and sweep logs\, backups\
    # and secrets\. Only *.md sitting DIRECTLY in the root is captured. session-catalog.md is
    # excluded below (machine-generated, 378 KB) -- see $ExcludeFilePatterns.
    @{ Live = "$UserProfile\.agents";          Repo = '.agents';        Label = 'agents-root'
       TopLevelOnly = $true; Filter = '*.md' }
)

# Loose files that live outside any synced tree and were orphaned individually. These are
# compared through the SAME engine as the mapped trees -- before the B7 pass they had their
# own inline branch that never produced a drift row, so a divergent loose file printed a
# line and the run still summarised as "NO DRIFT".
$LooseFiles = @(
    @{ Live = "$UserProfile\.local\bin\codexmon.ps1"; Repo = 'tools/monitor/codexmon.ps1' }
)

# Anything matching these is third-party, generated, or machine-local. Committing it is a
# one-way mistake: git keeps the blob forever even after a later delete.
$ExcludeDirs = @('.venv', 'venv', 'node_modules', '__pycache__', '.git', '.pytest_cache',
                 'site-packages', 'dist', 'build', '.mypy_cache', '.ruff_cache', '.tox',
                 '.next', 'target', '.gradle',
                 # Hook runtime state dirs (recall-gate indices, per-session caches). These
                 # churn every session and must never enter version control or raise DRIFT.
                 'state')
$ExcludeFilePatterns = @('*.pyc', '*.pyo', '*.so', '*.dll', '*.exe', '*.egg-info',
                         '*.log', '*.tmp', '.DS_Store', 'Thumbs.db',
                         '*.sqlite', '*.sqlite3', '*.db',
                         # Packaging / export blobs dropped next to skills (not skill content).
                         '*.zip',
                         # Hook throttle / UI-reminder runtime markers (live-only; rewrite often).
                         '.last-run', '.shown-*',
                         # Machine-generated session catalog in ~\.agents root (378 KB, regenerated
                         # constantly; staging it crashed a daemon 2026-08-27). Also gitignored.
                         # The tracked .agents/session-catalog.POINTER.md records where it lives.
                         'session-catalog.md',
                         # Agent-generated backups. '*.bak' alone is NOT enough: the live tree
                         # carries suffixed forms like '.bak-fleet-20260713',
                         # '.bak-gembuild-agent-definitions-batch', and stacked ones such as
                         # 'manifest.json.20260712-193022.bak.bak-fleet-20260713'. The narrow
                         # pattern let 32 files / 192 KB of cruft into the first commit.
                         '*.bak', '*.bak-*', '*.bak.*', '*.orig', '*.rej', '*~', '*.old', '*.save')

# REPO-OWNED files: paths that exist in BOTH trees but whose repo copy is authoritative and
# must never be overwritten from live, and (since B7) never pruned either.
#   hooks/README.md  documents the REPO tree ("This tree is the canonical, version-controlled
#                    copy ... Deploy / restore: sync-hooks.ps1"). The live file of the same name
#                    is an unrelated doc. Overwriting would delete the repo's own deploy
#                    instructions -- caught 2026-07-18 by reading the diff after mtime
#                    mis-reported which side was newer.
#   multi-agent-quickstart/SKILL.md   repo-only "## Execution Choice" section, a governance
#                                     rule mirroring metaswarm CLAUDE.md. Re-measured 2026-07-18:
#                                     live is a strict SUBSET of repo (5 lines removed, 0 added),
#                                     so this is staleness in live, NOT bidirectional divergence.
#                                     Resolution is repo -> live via sync-skills.ps1; the hold
#                                     stays only until that deploy happens.
#   audit_quality_zero_platform.py    WAS held (bidirectional yaml-fallback divergence). The
#                                     scripts/merges/ reconciliation (yaml -> find_python_with_yaml
#                                     -> pwsh ConvertFrom-Yaml) was deployed to BOTH trees
#                                     2026-08-27, so per the rule below the entry was removed.
# Remove an entry from this list once its merge has been deployed to live.
$RepoOwnedFiles = @(
    'hooks/README.md',
    '.agents/skills/multi-agent-quickstart/SKILL.md'
)

function Test-RepoOwned {
    param([string]$RepoRel)
    $norm = $RepoRel -replace '\\', '/'
    foreach ($p in $RepoOwnedFiles) { if ($norm -ieq $p) { return $true } }
    return $false
}

# A directory holding its own .git is a SEPARATE REPOSITORY that happens to sit inside our tree.
# Copying its files in would vendor someone else's project into this repo -- their license, their
# history, their bloat, and no upgrade path. Caught 2026-07-18: crypto-ctf/RsaCtfTool is a full
# clone of github.com/RsaCtfTool/RsaCtfTool.git (10 MB, 193 files, own LICENSE.txt) that the
# generated-junk filters did not catch, because it is genuine source, not build output.
# Cached because this runs once per file over ~18,000 files.
# -LiteralPath is mandatory here: with plain Test-Path a bracketed directory name defeats the
# check entirely and the foreign repo gets committed.
$script:NestedRepoCache = @{}
function Test-InNestedRepo {
    param([string]$FullPath, [string]$Base)
    $dir = Split-Path $FullPath -Parent
    while ($dir -and $dir.Length -gt $Base.Length) {
        if ($script:NestedRepoCache.ContainsKey($dir)) {
            if ($script:NestedRepoCache[$dir]) { return $true }
        } else {
            $isRepo = Test-Path -LiteralPath (Join-Path $dir '.git')
            $script:NestedRepoCache[$dir] = $isRepo
            if ($isRepo) { return $true }
        }
        $dir = Split-Path $dir -Parent
    }
    return $false
}

function Test-Excluded {
    param([string]$FullPath, [string]$Base)
    $rel = $FullPath.Substring($Base.Length).TrimStart('\', '/')
    foreach ($seg in ($rel -split '[\\/]')) {
        if ($ExcludeDirs -contains $seg) { return $true }
    }
    $leaf = Split-Path $FullPath -Leaf
    foreach ($pat in $ExcludeFilePatterns) {
        if ($leaf -like $pat) { return $true }
    }
    if (Test-InNestedRepo -FullPath $FullPath -Base $Base) { return $true }
    return $false
}

# Raw SHA256 plus enough metadata to classify a mismatch. Ok=$false means the bytes could not
# be read at all -- the caller MUST NOT treat that as any kind of equality.
function Get-FileDigest {
    param([string]$Path)
    $d = [pscustomobject]@{ Ok = $false; Raw = $null; Binary = $false; Length = 0 }
    try { $bytes = [IO.File]::ReadAllBytes($Path) } catch { return $d }
    $d.Length = $bytes.Length
    # git's own heuristic: a NUL byte inside the first 8000 bytes means binary, and binary
    # content must never be newline-normalised or genuinely different blobs compare equal.
    $scan = [Math]::Min($bytes.Length, 8000)
    for ($i = 0; $i -lt $scan; $i++) { if ($bytes[$i] -eq 0) { $d.Binary = $true; break } }
    $d.Raw = [BitConverter]::ToString([Security.Cryptography.SHA256]::HashData($bytes)).Replace('-', '')
    $d.Ok = $true
    return $d
}

# Hash with every CR that immediately precedes an LF removed -- exactly the transform
# core.autocrlf undoes on commit. Computed ONLY when the raw hashes already disagree, so the
# common path stays a single native hash per file.
function Get-NormalizedHash {
    param([string]$Path)
    try { $bytes = [IO.File]::ReadAllBytes($Path) } catch { return $null }
    $out = [byte[]]::new($bytes.Length)
    $n = 0
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -eq 13 -and ($i + 1) -lt $bytes.Length -and $bytes[$i + 1] -eq 10) { continue }
        $out[$n] = $bytes[$i]; $n++
    }
    # HashData has no (byte[], offset, count) overload -- trim to the exact length first.
    if ($n -ne $out.Length) {
        $trimmed = [byte[]]::new($n)
        [Array]::Copy($out, $trimmed, $n)
        $out = $trimmed
    }
    return [BitConverter]::ToString([Security.Cryptography.SHA256]::HashData($out)).Replace('-', '')
}

# Windows is case-insensitive, git's index is not. Test-Path -LiteralPath happily resolves
# 'foo.md' to an on-disk 'FOO.md', so a case-only rename in live is invisible: hashes match,
# the pair is called identical, and the repo keeps the old spelling permanently. One cached
# directory enumeration per repo directory gives us the REAL on-disk spelling to compare.
# Scope: leaf names only. Case drift in an intermediate DIRECTORY segment is NOT detected --
# UNVERIFIED whether that occurs in practice; the experiment is to compare `git ls-files`
# casing against an on-disk walk.
$script:DirIndex = @{}
function Get-RealChildName {
    param([string]$Dir, [string]$Leaf)
    if (-not $script:DirIndex.ContainsKey($Dir)) {
        $idx = @{}
        try {
            foreach ($e in [IO.Directory]::EnumerateFileSystemEntries($Dir)) {
                $n = [IO.Path]::GetFileName($e)
                $idx[$n.ToLowerInvariant()] = $n
            }
        } catch { }
        $script:DirIndex[$Dir] = $idx
    }
    $map = $script:DirIndex[$Dir]
    $key = $Leaf.ToLowerInvariant()
    if ($map.ContainsKey($key)) { return $map[$key] }
    return $null
}

# ---------------------------------------------------------------------------------------
# The comparison engine. Classifies ONE live/repo pair. Shared by the real run and by the
# self-control, so the control exercises the same code path that produces the verdict.
#
# Status vocabulary (closed set -- a consumer may switch on these and nothing else):
#   SAME            bytes identical
#   EOL-ONLY        differ only by CR before LF; not copied, not drift
#   NEW             present in live, absent from repo
#   CHANGED         genuine content difference
#   HELD            differs, but the repo copy is authoritative (hold list) -- needs a merge
#   UNREADABLE      one or both sides could not be hashed; equality is UNKNOWN, never assumed
#   CASE-MISMATCH   same path case-insensitively, different on-disk spelling
#   REPARSE         symlink / junction; not followed and not dereferenced
# ---------------------------------------------------------------------------------------
function Compare-Pair {
    param(
        [string]$LivePath,
        [string]$RepoPath,
        [string]$RepoRel,
        [bool]$IsReparse
    )
    if ($IsReparse) { return @{ Status = 'REPARSE' } }

    if (-not (Test-Path -LiteralPath $RepoPath)) { return @{ Status = 'NEW' } }

    $expectedLeaf = Split-Path $RepoPath -Leaf
    $realLeaf = Get-RealChildName -Dir (Split-Path $RepoPath -Parent) -Leaf $expectedLeaf
    if ($realLeaf -and ($realLeaf -cne $expectedLeaf)) {
        return @{ Status = 'CASE-MISMATCH'; Detail = "repo spells it '$realLeaf', live spells it '$expectedLeaf'" }
    }

    $dLive = Get-FileDigest $LivePath
    $dRepo = Get-FileDigest $RepoPath
    if (-not $dLive.Ok -or -not $dRepo.Ok) {
        $which = if (-not $dLive.Ok -and -not $dRepo.Ok) { 'both sides' }
                 elseif (-not $dLive.Ok) { 'live side' } else { 'repo side' }
        return @{ Status = 'UNREADABLE'; Detail = "could not hash $which" }
    }
    if ($dLive.Raw -eq $dRepo.Raw) { return @{ Status = 'SAME' } }

    if (-not $dLive.Binary -and -not $dRepo.Binary) {
        $nLive = Get-NormalizedHash $LivePath
        $nRepo = Get-NormalizedHash $RepoPath
        if ($nLive -and $nRepo -and $nLive -eq $nRepo) {
            return @{ Status = 'EOL-ONLY'; Detail = 'identical after newline normalisation' }
        }
    }
    if (Test-RepoOwned $RepoRel) { return @{ Status = 'HELD'; Detail = 'repo copy is authoritative' } }
    return @{ Status = 'CHANGED' }
}

# ---------------------------------------------------------------------------------------
# Known-positive control, run before ANY clean verdict is allowed.
#
# rules/common/single-signal-verification.md rule 3: verify the detector before trusting the
# absence. INPUT-known-harness-defects.md D2 asks whether that can be made mechanical instead
# of depending on an agent remembering it. This is that mechanism: plant divergences of every
# class the engine claims to detect, run the real Compare-Pair over them, and refuse to print
# CLEAN unless all of them came back.
# ---------------------------------------------------------------------------------------
function Invoke-DetectorControl {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("sync-from-live-control-" + [guid]::NewGuid().ToString('N'))
    $live = Join-Path $tmp 'live'
    $repo = Join-Path $tmp 'repo'
    $result = [pscustomobject]@{ Ran = $false; Passed = $false; Planted = 0; Detected = 0; Failures = @() }
    try {
        New-Item -ItemType Directory -Force -Path $live, $repo | Out-Null
        # planted case -> expected status
        $cases = [ordered]@{
            'identical.md'    = @{ Live = "same`n";       Repo = "same`n";        Expect = 'SAME' }
            'changed.md'      = @{ Live = "alpha`n";      Repo = "beta`n";        Expect = 'CHANGED' }
            'newonly.md'      = @{ Live = "only live`n";  Repo = $null;           Expect = 'NEW' }
            'eol.md'          = @{ Live = "a`nb`n";       Repo = "a`r`nb`r`n";    Expect = 'EOL-ONLY' }
        }
        foreach ($name in $cases.Keys) {
            $c = $cases[$name]
            [IO.File]::WriteAllText((Join-Path $live $name), $c.Live)
            if ($null -ne $c.Repo) { [IO.File]::WriteAllText((Join-Path $repo $name), $c.Repo) }
        }
        # a case-only rename, planted separately because it needs two different spellings
        [IO.File]::WriteAllText((Join-Path $live 'casing.md'), "body`n")
        [IO.File]::WriteAllText((Join-Path $repo 'CASING.md'), "body`n")
        $cases['casing.md'] = @{ Expect = 'CASE-MISMATCH' }

        $script:DirIndex = @{}   # the control uses fresh directories; do not serve stale entries
        $planted = 0; $detected = 0; $failures = @()
        foreach ($name in $cases.Keys) {
            $expect = $cases[$name].Expect
            if ($expect -ne 'SAME') { $planted++ }
            $got = (Compare-Pair -LivePath (Join-Path $live $name) `
                                 -RepoPath (Join-Path $repo $name) `
                                 -RepoRel  $name -IsReparse $false).Status
            if ($got -eq $expect) {
                if ($expect -ne 'SAME') { $detected++ }
            } else {
                $failures += "planted $expect on '$name' but engine said $got"
            }
        }
        $result.Ran = $true
        $result.Planted = $planted
        $result.Detected = $detected
        $result.Failures = $failures
        # Fault injection for the test that proves the refusal path actually bites. Without a
        # test that BREAKS the control, the control could silently stop working and nothing
        # would notice -- which is the exact class of bug it was added to prevent.
        if ($env:SYNC_FROM_LIVE_BREAK_CONTROL -eq '1') {
            $result.Detected = 0
            $result.Failures = @('fault injected via SYNC_FROM_LIVE_BREAK_CONTROL')
        }
        $result.Passed = ($result.Failures.Count -eq 0 -and $result.Detected -eq $result.Planted -and $planted -gt 0)
    } catch {
        $result.Failures = @("control raised: $_")
        $result.Passed = $false
    } finally {
        $script:DirIndex = @{}
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $result
}

# =========================================================================== run

$findings = [System.Collections.Generic.List[object]]::new()
$errors   = [System.Collections.Generic.List[string]]::new()
$areas    = [System.Collections.Generic.List[object]]::new()

$T = [ordered]@{
    filesSeen = 0; new = 0; changed = 0; same = 0; excluded = 0; held = 0; pruned = 0
    unreadable = 0; reparse = 0; caseMismatch = 0; eolOnly = 0
    verifiedCopies = 0; torn = 0; enumerationErrors = 0; divergent = 0
}

function Add-Finding {
    param([string]$Area, [string]$Status, [string]$RepoRel, [string]$LivePath,
          [string]$Detail = '', $LiveItem = $null, $RepoItem = $null)
    $liveUtc = $null; $repoUtc = $null; $mtime = 'UNKNOWN'; $sizeDelta = $null
    if ($LiveItem -and $RepoItem) {
        $liveUtc = $LiveItem.LastWriteTimeUtc.ToString('o')
        $repoUtc = $RepoItem.LastWriteTimeUtc.ToString('o')
        # MTIME IS NOT EVIDENCE OF WHICH SIDE IS AHEAD. Measured 2026-07-18: the repo copy of
        # _dispatch/manifest.json had the LATER mtime (a checkout touched it) while the LIVE
        # copy was a strict superset carrying a whole extra hook entry. Reporting "Newer=REPO"
        # there would have been exactly backwards. So the size delta rides alongside it and the
        # column is labelled honestly -- the human reads the diff. An exact tie now says TIE
        # rather than silently defaulting to REPO.
        $mtime = if ($LiveItem.LastWriteTimeUtc -gt $RepoItem.LastWriteTimeUtc) { 'LIVE' }
                 elseif ($LiveItem.LastWriteTimeUtc -lt $RepoItem.LastWriteTimeUtc) { 'REPO' }
                 else { 'TIE' }
        $sizeDelta = $LiveItem.Length - $RepoItem.Length
    }
    $findings.Add([pscustomobject]@{
        area = $Area; status = $Status
        repoPath = ($RepoRel -replace '\\', '/')
        livePath = $LivePath
        mtimeSays = $mtime; liveUtc = $liveUtc; repoUtc = $repoUtc
        sizeDelta = $sizeDelta; detail = $Detail
    })
}

$writeAllowed = (-not $WhatIf -and -not $Drift -and $Apply)

# --- refuse to run on a dirty index, so the result is a reviewable diff -------
$dirtyIndex = $false
if ($writeAllowed) {
    Push-Location $Root
    try {
        $staged = @(git diff --cached --name-only 2>$null)
        if ($staged.Count -gt 0) {
            $dirtyIndex = $true
            $errors.Add("$($staged.Count) file(s) already staged in $Root; commit or reset them first -- this script's output must be reviewable on its own.")
        }
    } catch {
        $errors.Add("could not query the git index in ${Root}: $_")
    } finally { Pop-Location }
}

$control = Invoke-DetectorControl
if (-not $control.Passed) {
    foreach ($f in $control.Failures) { $errors.Add("detector self-control: $f") }
}

$mode = if ($Drift) { 'drift' } elseif ($WhatIf) { 'whatif' } else { 'sync' }
Say ""
Say "=== sync-from-live [$($mode.ToUpper())]  live -> $Root ===" 'Cyan'
Say ""

if (-not $dirtyIndex) {
  foreach ($m in $Map) {
    $A = [ordered]@{
        label = $m.Label; live = $m.Live; repo = $m.Repo; present = $true
        filesSeen = 0; new = 0; changed = 0; same = 0; excluded = 0; held = 0
        unreadable = 0; reparse = 0; caseMismatch = 0; eolOnly = 0; enumerationErrors = 0
    }

    if (-not (Test-Path -LiteralPath $m.Live)) {
        # Before B7 this printed a grey note and the run still concluded "NO DRIFT" having
        # compared nothing. A vanished source tree is indistinguishable from a typo or a
        # rename, and a backup that silently stops backing up must never look like success.
        $A.present = $false
        $areas.Add([pscustomobject]$A)
        Add-Finding -Area $m.Label -Status 'MISSING-LIVE-ROOT' -RepoRel $m.Repo -LivePath $m.Live `
                    -Detail 'mapped live area does not exist; edit $Map if this is intentional'
        $errors.Add("live area '$($m.Label)' is missing: $($m.Live)")
        Say ("  {0,-10} LIVE AREA MISSING: {1}" -f $m.Label, $m.Live) 'Red'
        continue
    }

    $destRoot = Join-Path $Root $m.Repo
    $walkErrors = @()
    # TopLevelOnly / Filter scope an entry to loose files directly under its live root.
    # Added for agents-root, whose live root CONTAINS the skills mapping's live root: an
    # unscoped recursive walk there would process ~18,000 skills files a second time and
    # pull logs\, backups\ and secrets\ trees toward a PUBLIC repo.
    $gci = @{ LiteralPath = $m.Live; File = $true; Force = $true }
    if (-not ($m.ContainsKey('TopLevelOnly') -and $m.TopLevelOnly)) { $gci.Recurse = $true }
    if ($m.ContainsKey('Filter')) { $gci.Filter = $m.Filter }
    $items = @(Get-ChildItem @gci -ErrorAction SilentlyContinue -ErrorVariable +walkErrors)
    # -ErrorAction SilentlyContinue on its own SWALLOWS the reason a subtree was skipped, so a
    # permissions failure or an unreadable directory produced a confident all-zeros report.
    # The errors are now captured and counted instead of discarded.
    $A.enumerationErrors = $walkErrors.Count
    foreach ($we in $walkErrors) { $errors.Add("walk error under $($m.Label): $we") }

    foreach ($f in $items) {
        $A.filesSeen++
        if (Test-Excluded -FullPath $f.FullName -Base $m.Live) { $A.excluded++; continue }

        $rel     = $f.FullName.Substring($m.Live.Length).TrimStart('\', '/')
        $dest    = Join-Path $destRoot $rel
        $repoRel = ($m.Repo + '/' + $rel) -replace '\\', '/'
        $isReparse = [bool]($f.Attributes -band [IO.FileAttributes]::ReparsePoint)

        $verdict = Compare-Pair -LivePath $f.FullName -RepoPath $dest -RepoRel $repoRel -IsReparse $isReparse
        $status  = $verdict.Status
        $detail  = if ($verdict.ContainsKey('Detail')) { $verdict.Detail } else { '' }

        # NOT a switch. In PowerShell `switch` is itself a looping construct, so `continue`
        # inside a switch case exits the SWITCH and execution falls straight through to the
        # code after it -- it does NOT continue the enclosing foreach. Written as a switch,
        # every terminal status (HELD, REPARSE, UNREADABLE, CASE-MISMATCH) fell through into
        # the copy block and a held file WAS overwritten. Caught by
        # test_held_file_is_never_overwritten_by_sync, which is the only test that runs a
        # real sync rather than a drift report.
        if ($status -eq 'SAME') { $A.same++; continue }

        if ($status -eq 'EOL-ONLY') {
            $A.eolOnly++
            Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName -Detail $detail
            continue
        }
        if ($status -eq 'REPARSE') {
            # Copy-Item would silently copy the TARGET's bytes, so a link pointing outside
            # the harness drags foreign content into the repo; and Get-ChildItem -Recurse
            # does not traverse directory links, so link-delivered content never reaches
            # the backup at all. Either way the operator gets told.
            $A.reparse++
            Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName `
                        -Detail 'reparse point: not followed, not dereferenced, NOT backed up'
            Say ("  {0,-10} REPARSE, skipped: {1}" -f $m.Label, $rel) 'DarkYellow'
            continue
        }
        if ($status -eq 'HELD') {
            $A.held++
            Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName `
                        -Detail $detail -LiveItem $f -RepoItem (Get-Item -LiteralPath $dest)
            Say ("  {0,-10} REPO-OWNED, not overwritten: {1}" -f $m.Label, $rel) 'DarkYellow'
            continue
        }
        if ($status -eq 'UNREADABLE') {
            $A.unreadable++
            Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName -Detail $detail
            Say ("  {0,-10} UNREADABLE ({1}): {2}" -f $m.Label, $detail, $rel) 'Red'
            continue
        }
        if ($status -eq 'CASE-MISMATCH') {
            $A.caseMismatch++
            Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName -Detail $detail
            Say ("  {0,-10} CASE MISMATCH: {1} ({2})" -f $m.Label, $rel, $detail) 'DarkYellow'
            continue
        }

        if ($status -eq 'NEW')     { $A.new++ }
        if ($status -eq 'CHANGED') { $A.changed++ }
        $repoItem = if ($status -eq 'CHANGED') { Get-Item -LiteralPath $dest } else { $null }
        Add-Finding -Area $m.Label -Status $status -RepoRel $repoRel -LivePath $f.FullName `
                    -Detail $detail -LiveItem $(if ($repoItem) { $f } else { $null }) -RepoItem $repoItem

        if ($writeAllowed) {
            New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
            # windows-shell.md rule 1: always verify after a write. A torn or truncated copy is
            # otherwise completely silent, and this script IS the backup.
            $srcD = Get-FileDigest $f.FullName
            $dstD = Get-FileDigest $dest
            if ($srcD.Ok -and $dstD.Ok -and $srcD.Raw -eq $dstD.Raw) {
                $T.verifiedCopies++
            } else {
                $T.torn++
                $errors.Add("copy verification FAILED for $repoRel (source changed mid-copy, or the write was truncated)")
                Say ("  {0,-10} COPY VERIFY FAILED: {1}" -f $m.Label, $rel) 'Red'
            }
        }
    }

    if ($Prune -and (Test-Path -LiteralPath $destRoot) -and -not $Drift) {
        # The prune walk must honor the same TopLevelOnly/Filter scope as the forward walk.
        # For agents-root, destRoot (.agents) CONTAINS the skills mapping's dest tree: an
        # unscoped recursive prune here would re-judge every skills file under a second area
        # and could delete repo files this entry never captures.
        $gciR = @{ LiteralPath = $destRoot; File = $true }
        if (-not ($m.ContainsKey('TopLevelOnly') -and $m.TopLevelOnly)) { $gciR.Recurse = $true }
        if ($m.ContainsKey('Filter')) { $gciR.Filter = $m.Filter }
        foreach ($rf in (Get-ChildItem @gciR -ErrorAction SilentlyContinue)) {
            if (Test-Excluded -FullPath $rf.FullName -Base $destRoot) { continue }
            $rel = $rf.FullName.Substring($destRoot.Length).TrimStart('\', '/')
            $repoRel = ($m.Repo + '/' + $rel) -replace '\\', '/'
            # The hold list exists because these repo copies are authoritative. Pruning one
            # because live no longer has it destroys the exact file the guard protects.
            if (Test-RepoOwned $repoRel) { continue }
            # -LiteralPath is load-bearing: with plain Test-Path a bracketed live filename reads
            # as absent and the repo copy is deleted while live still holds it. DATA LOSS.
            if (-not (Test-Path -LiteralPath (Join-Path $m.Live $rel))) {
                $T.pruned++
                Add-Finding -Area $m.Label -Status 'PRUNED' -RepoRel $repoRel -LivePath '' `
                            -Detail 'no live counterpart'
                if (-not $WhatIf) { Remove-Item -LiteralPath $rf.FullName -Force }
            }
        }
    }

    $areas.Add([pscustomobject]$A)
    foreach ($k in @('filesSeen','new','changed','same','excluded','held','unreadable','reparse','caseMismatch','eolOnly','enumerationErrors')) {
        $T[$k] += $A[$k]
    }
    Say ("  {0,-10} +{1,-4} new   ~{2,-4} changed   ={3,-5} same   skip {4}" -f $m.Label, $A.new, $A.changed, $A.same, $A.excluded)
  }

  # Loose files, through the SAME engine so they can produce drift rows like everything else.
  foreach ($lf in $LooseFiles) {
    if (-not (Test-Path -LiteralPath $lf.Live)) { continue }
    $T.filesSeen++
    $dest = Join-Path $Root $lf.Repo
    $item = Get-Item -LiteralPath $lf.Live
    $isReparse = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    $verdict = Compare-Pair -LivePath $lf.Live -RepoPath $dest -RepoRel $lf.Repo -IsReparse $isReparse
    $status = $verdict.Status
    $detail = if ($verdict.ContainsKey('Detail')) { $verdict.Detail } else { '' }
    switch ($status) {
        'SAME'          { $T.same++ }
        'EOL-ONLY'      { $T.eolOnly++ }
        'NEW'           { $T.new++ }
        'CHANGED'       { $T.changed++ }
        'HELD'          { $T.held++ }
        'UNREADABLE'    { $T.unreadable++ }
        'REPARSE'       { $T.reparse++ }
        'CASE-MISMATCH' { $T.caseMismatch++ }
    }
    if ($status -ne 'SAME') {
        $repoItem = if (Test-Path -LiteralPath $dest) { Get-Item -LiteralPath $dest } else { $null }
        Add-Finding -Area 'loose' -Status $status -RepoRel $lf.Repo -LivePath $lf.Live `
                    -Detail $detail -LiveItem $(if ($repoItem) { $item } else { $null }) -RepoItem $repoItem
        Say ("  {0,-10} {1,-13} {2} -> {3}" -f 'loose', $status, (Split-Path $lf.Live -Leaf), $lf.Repo)
    }
    if ($writeAllowed -and $status -in @('NEW', 'CHANGED')) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -LiteralPath $lf.Live -Destination $dest -Force
        $srcD = Get-FileDigest $lf.Live
        $dstD = Get-FileDigest $dest
        if ($srcD.Ok -and $dstD.Ok -and $srcD.Raw -eq $dstD.Raw) { $T.verifiedCopies++ }
        else { $T.torn++; $errors.Add("copy verification FAILED for $($lf.Repo)") }
    }
  }
}

# --------------------------------------------------------------------------- verdict
#
# divergent counts every class where live and repo disagree AT SCAN TIME. EOL-ONLY is
# deliberately excluded: it is a checkout artifact, not a difference git can even see, and
# counting it would have produced 342 phantom rows on a fresh clone.
$T.divergent = $T.new + $T.changed + $T.held + $T.unreadable + $T.caseMismatch + $T.reparse

# After a real sync, NEW and CHANGED have been resolved by copying; what remains are the
# classes a sync deliberately cannot fix.
$unresolved = if ($writeAllowed) { $T.held + $T.unreadable + $T.caseMismatch + $T.reparse }
              else { $T.divergent }

$failed = ($errors.Count -gt 0) -or (-not $control.Passed) -or ($T.torn -gt 0) -or $dirtyIndex
$verdict = if ($failed) { 'FAILED' } elseif ($unresolved -gt 0) { 'DRIFT' } else { 'CLEAN' }
$exitCode = switch ($verdict) { 'CLEAN' { 0 } 'DRIFT' { 3 } 'FAILED' { 1 } }

# NOT named $report: PowerShell variable names are CASE-INSENSITIVE, so a local $report
# silently overwrites the [ValidateSet]-constrained $Report parameter and the next read of
# it throws "OrderedDictionary is not a valid value for the Report variable". Caught by the
# test suite on the first green run.
$reportDoc = [ordered]@{
    schema       = $SchemaVersion
    generatedUtc = (Get-Date).ToUniversalTime().ToString('o')
    mode         = $mode
    repoRoot     = $Root
    liveHome     = $UserProfile
    ok           = ($verdict -eq 'CLEAN')
    verdict      = $verdict
    exitCode     = $exitCode
    detectorControl = [ordered]@{
        ran      = $control.Ran
        passed   = $control.Passed
        planted  = $control.Planted
        detected = $control.Detected
        failures = [string[]]@($control.Failures)
    }
    totals  = $T
    areas   = [object[]]@($areas)
    findings = [object[]]@($findings)
    errors  = [string[]]@($errors)
}

if ($ReportPath) {
    $dir = Split-Path $ReportPath -Parent
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($ReportPath, ($reportDoc | ConvertTo-Json -Depth 8))
}

if ($Report -eq 'json') {
    Write-Output ($reportDoc | ConvertTo-Json -Depth 8)
    exit $exitCode
}

# --------------------------------------------------------------------------- human output
Say ""
if (-not $control.Passed) {
    Say "  DETECTOR SELF-CONTROL FAILED -- this run's conclusions are NOT trustworthy." 'Red'
    foreach ($f in $control.Failures) { Say "    $f" 'Red' }
    Say "  Refusing to report a clean result from a detector that cannot see planted drift." 'Red'
    Say ""
} else {
    Say ("  detector self-control: {0}/{1} planted divergences detected" -f $control.Detected, $control.Planted) 'DarkGray'
}

foreach ($e in $errors) { Say "  ERROR: $e" 'Red' }

$driftRows = @($findings | Where-Object { $_.status -in @('NEW','CHANGED','HELD','UNREADABLE','CASE-MISMATCH','REPARSE') })

if ($Drift) {
    if ($driftRows.Count -eq 0 -and $verdict -eq 'CLEAN') {
        Say "  NO DRIFT: every shared file is byte-identical." 'Green'
        if ($T.eolOnly -gt 0) {
            Say ("  ({0} file(s) differ only in line endings -- a checkout artifact, not a change.)" -f $T.eolOnly) 'DarkGray'
        }
    } else {
        Say "  DRIFT: $($driftRows.Count) file(s) diverge between live and repo" 'Yellow'
        $driftRows | Sort-Object area, repoPath | Select-Object -First 40 |
            Format-Table @{L='Area';E={$_.area}}, @{L='Status';E={$_.status}},
                         @{L='MtimeSays';E={$_.mtimeSays}}, @{L='SizeDelta';E={if ($null -ne $_.sizeDelta) { '{0:+#;-#;0}' -f $_.sizeDelta } else { '' }}},
                         @{L='File';E={$_.repoPath}} -AutoSize
        if ($driftRows.Count -gt 40) { Say "  ... and $($driftRows.Count - 40) more" }
        Say "  MtimeSays is a HINT, NOT A VERDICT -- a checkout or copy updates mtime without" 'Yellow'
        Say "  changing content, and that has already produced a backwards reading here." 'Yellow'
        Say "  Diff anything that matters before syncing:" 'Yellow'
        Say "    diff `"<repo>/<area>/<file>`" `"<live>/<area>/<file>`""
    }
    Say ""
    exit $exitCode
}

Say ("  TOTAL  new {0}   changed {1}   unchanged {2}   excluded {3}   pruned {4}" -f
    $T.new, $T.changed, $T.same, $T.excluded, $T.pruned) 'Cyan'
if ($T.eolOnly -gt 0 -or $T.held -gt 0 -or $T.unreadable -gt 0 -or $T.caseMismatch -gt 0 -or $T.reparse -gt 0) {
    Say ("         eol-only {0}   held {1}   unreadable {2}   case-mismatch {3}   reparse {4}" -f
        $T.eolOnly, $T.held, $T.unreadable, $T.caseMismatch, $T.reparse) 'DarkYellow'
}

if ($WhatIf) {
    Say ""
    Say "  [WhatIf] nothing written. Re-run without -WhatIf to apply."
    Say ""
} elseif (-not $dirtyIndex) {
    Say ("         copies hash-verified: {0}" -f $T.verifiedCopies) 'DarkGray'
    Say ""
    Say "  Next: review, then commit with a SCOPED add (never 'git add -A'):"
    Say "    git -C `"$Root`" add rules agents commands hooks .agents/skills '.agents/*.md' tools/monitor"
    Say "    git -C `"$Root`" diff --cached --stat        # verify nothing unexpected"
    Say ""
}

exit $exitCode
