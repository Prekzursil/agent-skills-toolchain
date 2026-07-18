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

.PARAMETER WhatIf
  Report what would change. Writes nothing. Run this first, always.

.PARAMETER Drift
  Report only files that EXIST in both places but DIFFER, with which side is newer. This is the
  early-warning signal that someone edited live and repo independently.

.PARAMETER Prune
  Also delete repo files whose live counterpart is gone. Off by default: a live deletion is
  usually a local experiment, and losing repo history to it is a bad trade.

.EXAMPLE
  pwsh -File scripts/sync-from-live.ps1 -WhatIf     # always start here
  pwsh -File scripts/sync-from-live.ps1 -Drift      # what diverged?
  pwsh -File scripts/sync-from-live.ps1             # do it
#>
[CmdletBinding()]
param(
    [switch]$WhatIf,
    [switch]$Drift,
    [switch]$Prune,
    [string]$Root = (Split-Path $PSScriptRoot -Parent)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$UserProfile = [Environment]::GetFolderPath('UserProfile')

# live source -> repo destination. Order is stable so output diffs cleanly run to run.
$Map = @(
    @{ Live = "$UserProfile\.claude\rules";    Repo = 'rules';          Label = 'rules' }
    @{ Live = "$UserProfile\.claude\agents";   Repo = 'agents';         Label = 'agents' }
    @{ Live = "$UserProfile\.claude\commands"; Repo = 'commands';       Label = 'commands' }
    @{ Live = "$UserProfile\.claude\hooks";    Repo = 'hooks';          Label = 'hooks' }
    @{ Live = "$UserProfile\.agents\skills";   Repo = '.agents/skills'; Label = 'skills' }
)

# Loose files that live outside any synced tree and were orphaned individually.
$LooseFiles = @(
    @{ Live = "$UserProfile\.local\bin\codexmon.ps1"; Repo = 'tools/monitor/codexmon.ps1' }
)

# Anything matching these is third-party, generated, or machine-local. Committing it is a
# one-way mistake: git keeps the blob forever even after a later delete.
$ExcludeDirs = @('.venv', 'venv', 'node_modules', '__pycache__', '.git', '.pytest_cache',
                 'site-packages', 'dist', 'build', '.mypy_cache', '.ruff_cache', '.tox',
                 '.next', 'target', '.gradle')
$ExcludeFilePatterns = @('*.pyc', '*.pyo', '*.so', '*.dll', '*.exe', '*.egg-info',
                         '*.log', '*.tmp', '.DS_Store', 'Thumbs.db',
                         '*.sqlite', '*.sqlite3', '*.db',
                         # Agent-generated backups. '*.bak' alone is NOT enough: the live tree
                         # carries suffixed forms like '.bak-fleet-20260713',
                         # '.bak-gembuild-agent-definitions-batch', and stacked ones such as
                         # 'manifest.json.20260712-193022.bak.bak-fleet-20260713'. The narrow
                         # pattern let 32 files / 192 KB of cruft into the first commit.
                         '*.bak', '*.bak-*', '*.bak.*', '*.orig', '*.rej', '*~', '*.old', '*.save')

# REPO-OWNED files: paths that exist in BOTH trees but whose repo copy is authoritative and
# must never be overwritten from live. These are not drift -- they are different documents
# that happen to share a filename.
#   hooks/README.md  documents the REPO tree ("This tree is the canonical, version-controlled
#                    copy ... Deploy / restore: sync-hooks.ps1"). The live file of the same name
#                    is an unrelated doc. Overwriting would delete the repo's own deploy
#                    instructions -- caught 2026-07-18 by reading the diff after mtime
#                    mis-reported which side was newer.
#   The two skills entries below are TRUE BIDIRECTIONAL DIVERGENCE, not staleness: each side
#   holds content the other lacks, so neither overwrite direction is correct. Verified by diff
#   2026-07-18 (mtime said LIVE was newer for both, and both were SMALLER than repo -- the size
#   delta is what prompted the read):
#     multi-agent-quickstart/SKILL.md   repo-only "## Execution Choice" section, a governance
#                                       rule mirroring metaswarm CLAUDE.md ("do not silently
#                                       force one path after the plan is written")
#     audit_quality_zero_platform.py    repo-only find_python_with_yaml() interpreter fallback
#   Held until merged by hand. Remove from this list once reconciled.
$RepoOwnedFiles = @(
    'hooks/README.md',
    '.agents/skills/multi-agent-quickstart/SKILL.md',
    '.agents/skills/quality-zero-platform-control-plane/scripts/audit_quality_zero_platform.py'
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
$script:NestedRepoCache = @{}
function Test-InNestedRepo {
    param([string]$FullPath, [string]$Base)
    $dir = Split-Path $FullPath -Parent
    while ($dir -and $dir.Length -gt $Base.Length) {
        if ($script:NestedRepoCache.ContainsKey($dir)) {
            if ($script:NestedRepoCache[$dir]) { return $true }
        } else {
            $isRepo = Test-Path (Join-Path $dir '.git')
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

function Get-Hash {
    param([string]$Path)
    try { (Get-FileHash -Path $Path -Algorithm SHA256 -ErrorAction Stop).Hash }
    catch { $null }
}

# --- refuse to run on a dirty index, so the result is a reviewable diff -------
if (-not $WhatIf -and -not $Drift) {
    Push-Location $Root
    try {
        $staged = @(git diff --cached --name-only 2>$null)
        if ($staged.Count -gt 0) {
            Write-Host "FAILED: $($staged.Count) file(s) already staged in $Root." -ForegroundColor Red
            Write-Host "        Commit or reset them first -- this script's output must be reviewable on its own." -ForegroundColor Red
            exit 1
        }
    } finally { Pop-Location }
}

$mode = if ($Drift) { 'DRIFT REPORT' } elseif ($WhatIf) { 'WHATIF' } else { 'SYNC' }
Write-Host "`n=== sync-from-live [$mode]  live -> $Root ===`n" -ForegroundColor Cyan

$added = 0; $updated = 0; $same = 0; $skipped = 0; $pruned = 0
$driftRows = [System.Collections.Generic.List[object]]::new()

foreach ($m in $Map) {
    if (-not (Test-Path $m.Live)) {
        Write-Host ("  {0,-10} live path absent: {1}" -f $m.Label, $m.Live) -ForegroundColor DarkGray
        continue
    }
    $destRoot = Join-Path $Root $m.Repo
    $a = 0; $u = 0; $s = 0; $x = 0

    foreach ($f in (Get-ChildItem -Path $m.Live -Recurse -File -Force -ErrorAction SilentlyContinue)) {
        if (Test-Excluded -FullPath $f.FullName -Base $m.Live) { $x++; continue }

        $rel = $f.FullName.Substring($m.Live.Length).TrimStart('\', '/')
        $dest = Join-Path $destRoot $rel

        if (Test-Path $dest) {
            if ((Get-Hash $f.FullName) -eq (Get-Hash $dest)) { $s++; continue }
            $repoRel = ($m.Repo + '/' + $rel) -replace '\\', '/'
            if (Test-RepoOwned $repoRel) {
                Write-Host ("  {0,-10} REPO-OWNED, not overwritten: {1}" -f $m.Label, $rel) -ForegroundColor DarkYellow
                $x++; continue
            }
            # Both sides exist and differ. Under -Drift we only REPORT; a silent overwrite
            # here is precisely how harness work gets lost.
            #
            # MTIME IS NOT EVIDENCE OF WHICH SIDE IS AHEAD. Measured 2026-07-18: the repo copy
            # of _dispatch/manifest.json had the LATER mtime (a checkout touched it) while the
            # LIVE copy was a strict superset carrying a whole extra hook entry. Reporting
            # "Newer=REPO" there would have been exactly backwards. So we surface the size
            # delta alongside it and label the column honestly -- the human reads the diff.
            $destItem = Get-Item $dest
            $driftRows.Add([pscustomobject]@{
                Area = $m.Label; File = $rel
                LiveUtc = $f.LastWriteTimeUtc
                RepoUtc = $destItem.LastWriteTimeUtc
                MtimeSays = if ($f.LastWriteTimeUtc -gt $destItem.LastWriteTimeUtc) { 'LIVE' } else { 'REPO' }
                SizeDelta = '{0:+#;-#;0}' -f ($f.Length - $destItem.Length)
            })
            $u++
            if (-not $WhatIf -and -not $Drift) {
                New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
                Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
            }
        } else {
            $a++
            if (-not $WhatIf -and -not $Drift) {
                New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
                Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
            }
        }
    }

    if ($Prune -and (Test-Path $destRoot) -and -not $Drift) {
        foreach ($rf in (Get-ChildItem -Path $destRoot -Recurse -File -ErrorAction SilentlyContinue)) {
            if (Test-Excluded -FullPath $rf.FullName -Base $destRoot) { continue }
            $rel = $rf.FullName.Substring($destRoot.Length).TrimStart('\', '/')
            if (-not (Test-Path (Join-Path $m.Live $rel))) {
                $pruned++
                if (-not $WhatIf) { Remove-Item -LiteralPath $rf.FullName -Force }
            }
        }
    }

    Write-Host ("  {0,-10} +{1,-4} new   ~{2,-4} changed   ={3,-5} same   skip {4}" -f $m.Label, $a, $u, $s, $x)
    $added += $a; $updated += $u; $same += $s; $skipped += $x
}

foreach ($lf in $LooseFiles) {
    if (-not (Test-Path $lf.Live)) { continue }
    $dest = Join-Path $Root $lf.Repo
    $exists = Test-Path $dest
    if ($exists -and ((Get-Hash $lf.Live) -eq (Get-Hash $dest))) { $same++; continue }
    if ($exists) { $updated++ } else { $added++ }
    Write-Host ("  {0,-10} {1} -> {2}" -f 'loose', (Split-Path $lf.Live -Leaf), $lf.Repo)
    if (-not $WhatIf -and -not $Drift) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -LiteralPath $lf.Live -Destination $dest -Force
    }
}

Write-Host ""
if ($Drift) {
    if ($driftRows.Count -eq 0) {
        Write-Host "  NO DRIFT: every shared file is byte-identical." -ForegroundColor Green
    } else {
        Write-Host "  DRIFT: $($driftRows.Count) file(s) differ between live and repo" -ForegroundColor Yellow
        $driftRows | Sort-Object Area, File | Select-Object -First 40 |
            Format-Table Area, MtimeSays, SizeDelta, File -AutoSize
        if ($driftRows.Count -gt 40) { Write-Host "  ... and $($driftRows.Count - 40) more" }
        Write-Host "  MtimeSays is a HINT, NOT A VERDICT -- a checkout or copy updates mtime without" -ForegroundColor Yellow
        Write-Host "  changing content, and that has already produced a backwards reading here." -ForegroundColor Yellow
        Write-Host "  Diff anything that matters before syncing:" -ForegroundColor Yellow
        Write-Host "    diff `"<repo>/<area>/<file>`" `"<live>/<area>/<file>`"" -ForegroundColor Gray
    }
    exit 0
}

Write-Host ("  TOTAL  new {0}   changed {1}   unchanged {2}   excluded {3}   pruned {4}" -f
    $added, $updated, $same, $skipped, $pruned) -ForegroundColor Cyan

if ($WhatIf) {
    Write-Host "`n  [WhatIf] nothing written. Re-run without -WhatIf to apply.`n" -ForegroundColor Gray
} else {
    Write-Host "`n  Next: review, then commit with a SCOPED add (never 'git add -A'):" -ForegroundColor Gray
    Write-Host "    git -C `"$Root`" add rules agents commands hooks .agents/skills tools/monitor" -ForegroundColor Gray
    Write-Host "    git -C `"$Root`" diff --cached --stat        # verify nothing unexpected" -ForegroundColor Gray
    Write-Host ""
}
