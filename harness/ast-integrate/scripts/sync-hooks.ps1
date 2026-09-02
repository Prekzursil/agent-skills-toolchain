<#
.SYNOPSIS
  Sync the repo's canonical agentic-perfection hooks into the live ~/.claude/hooks.

.DESCRIPTION
  The hooks/ tree in this repo is the CANONICAL copy of the session-built
  agentic-perfection hook set (dispatcher + durability spine + anti-slop +
  wildcard gems + infra). This script copies it back into the live hooks dir.
  It mirrors the proven scripts/sync-skills.ps1 pattern, with one deliberate
  difference: it is COPY (not symlink), idempotent, and strictly NON-DESTRUCTIVE.

  Why non-destructive (and why there is NO prune mode):
    The live ~/.claude/hooks is intentionally a SUPERSET of this repo's hooks/.
    It also holds pre-existing B1/legacy hooks (anti-degen, event-ledger,
    goal-reinject, beads, ...) that this repo does not manage, AND inside
    capability-catalog/ it holds files this repo deliberately does not version
    (inject.py, catalog.json). A mirror/prune would DELETE those live files and
    break the running harness. So this script only ever copies the files the
    repo manages, overwriting matching files in place, and never deletes anything.

  Fail-safe: a copy error on a single file is reported and skipped, never aborts.

.PARAMETER Root
  Repo root. Defaults to the parent of this script's directory.

.PARAMETER Dest
  Live hooks directory. Defaults to ~/.claude/hooks.

.PARAMETER WhatIf
  Show what would be copied without writing anything.

.EXAMPLE
  pwsh -File scripts/sync-hooks.ps1
  # Sync repo hooks/ -> ~/.claude/hooks (overwrite managed files only).

.EXAMPLE
  pwsh -File scripts/sync-hooks.ps1 -WhatIf
  # Dry-run: list every file that would be copied. No writes, no deletes.

.EXAMPLE
  pwsh -File scripts/sync-hooks.ps1 -Dest "$env:TEMP\hooks-roundtrip-test"
  # Sync into a throwaway dir (used by the round-trip fidelity test).
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude/hooks"),
    [switch]$WhatIf,
    [switch]$Provenance
)

$ErrorActionPreference = "Stop"

$srcRoot = Join-Path $Root "hooks"
if (-not (Test-Path $srcRoot)) { throw "hooks/ tree not found at $srcRoot" }

if (-not (Test-Path $Dest)) {
    Write-Host "Creating hooks dir: $Dest"
    if (-not $WhatIf) { New-Item -ItemType Directory -Force -Path $Dest | Out-Null }
}

# Generated caches / editor backups are never synced (belt-and-suspenders; the
# repo tree should not contain them, but a stray one must never reach the live dir).
$excludeRe = '[\\/](__pycache__|\.pytest_cache|\.ruff_cache)[\\/]'

# Only subdirectories of hooks/ are hook packages. Top-level files (README.md,
# CHANGELOG pointers) are repo docs and are intentionally not synced into the live dir.
$hookDirs = Get-ChildItem -Path $srcRoot -Directory
$copied = 0
$dirCount = 0
foreach ($hd in $hookDirs) {
    $dirCount++
    $files = Get-ChildItem -Path $hd.FullName -Recurse -File | Where-Object {
        $_.FullName -notmatch $excludeRe -and $_.Name -notlike '*.bak*'
    }
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($hd.FullName.Length + 1)
        $target = Join-Path (Join-Path $Dest $hd.Name) $rel
        if ($WhatIf) {
            Write-Host "[whatif] $($hd.Name)/$rel"
        } else {
            try {
                $targetDir = Split-Path $target
                if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Force -Path $targetDir | Out-Null }
                Copy-Item -Force -LiteralPath $f.FullName -Destination $target
                $copied++
            } catch {
                Write-Warning "skip $($hd.Name)/$rel : $($_.Exception.Message)"
            }
        }
    }
}

if ($WhatIf) {
    Write-Host "[whatif] would sync $dirCount hook dir(s) from $srcRoot -> $Dest (non-destructive; no deletes)"
} else {
    Write-Host "Synced $copied file(s) across $dirCount hook dir(s) -> $Dest (non-destructive; no deletes)"
}

# -Provenance (IMP-0033): record per-file provenance for the hooks family into
# ~/.claude/deploy-provenance.json via tools/plugin/deploy_provenance.py::place_file
# (the single live writer). Control plane stays here; not a fourth sync tool.
if ($Provenance -and -not $WhatIf) {
    $engine = Join-Path $Root "tools/plugin/deploy_provenance.py"
    $home_ = [Environment]::GetFolderPath("UserProfile")
    & python3 $engine --kind hooks --repo $Root --home $home_
    if ($LASTEXITCODE -ne 0) { throw "deploy_provenance.py --kind hooks exited $LASTEXITCODE" }
}
