<#
.SYNOPSIS
  Sync the repo's canonical common rules into the live ~/.claude/rules/common.

.DESCRIPTION
  The rules/common/ tree in this repo holds versioned cross-tool rule files
  (e.g. ci-hygiene.md). The live ~/.claude/rules/common is the CANONICAL runtime
  location Claude Code reads; historically it had NO repo->live bridge (unlike
  scripts/sync-skills.ps1 and scripts/sync-hooks.ps1), so a repo-authored rule
  had to be hand-copied. This script closes that gap in the imperative-copy sync
  model (copy, not symlink).

  Non-destructive by design (like sync-hooks.ps1): the live rules dir is a
  SUPERSET of this repo's rules/common (it also holds rules this repo does not
  version -- windows-shell.md, static-analyzer.md, coding-style.md, ...). This
  script ONLY copies the *.md files present under repo rules/common, overwriting
  matching files in place, and NEVER deletes anything. There is deliberately NO
  prune mode -- a mirror/prune would wipe the unmanaged live rules and break the
  running harness.

  Fail-safe: a copy error on a single file is reported and skipped, never aborts.

.PARAMETER Root
  Repo root. Defaults to the parent of this script's directory.

.PARAMETER Dest
  Live common-rules directory. Defaults to ~/.claude/rules/common.

.PARAMETER WhatIf
  Show what would be copied without writing anything.

.EXAMPLE
  pwsh -File scripts/sync-rules.ps1
  # Sync repo rules/common/*.md -> ~/.claude/rules/common (overwrite managed files only).

.EXAMPLE
  pwsh -File scripts/sync-rules.ps1 -WhatIf
  # Dry-run: list every file that would be copied. No writes, no deletes.
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude/rules/common"),
    [switch]$WhatIf,
    [switch]$Provenance
)

$ErrorActionPreference = "Stop"

$srcRoot = Join-Path $Root "rules/common"
if (-not (Test-Path $srcRoot)) { throw "rules/common tree not found at $srcRoot" }

if (-not (Test-Path $Dest)) {
    Write-Host "Creating rules dir: $Dest"
    if (-not $WhatIf) { New-Item -ItemType Directory -Force -Path $Dest | Out-Null }
}

# Only *.md rule files are synced; editor backups and caches never are.
$files = Get-ChildItem -Path $srcRoot -File -Filter *.md | Where-Object {
    $_.Name -notlike '*.bak*'
}
$copied = 0
foreach ($f in $files) {
    $target = Join-Path $Dest $f.Name
    if ($WhatIf) {
        Write-Host "[whatif] $($f.Name)"
    } else {
        try {
            Copy-Item -Force -LiteralPath $f.FullName -Destination $target
            $copied++
        } catch {
            Write-Warning "skip $($f.Name) : $($_.Exception.Message)"
        }
    }
}

if ($WhatIf) {
    Write-Host "[whatif] would sync $($files.Count) rule file(s) from $srcRoot -> $Dest (non-destructive; no deletes)"
} else {
    Write-Host "Synced $copied rule file(s) -> $Dest (non-destructive; no deletes)"
}

# -Provenance (IMP-0033): record per-file provenance for the rules family into
# ~/.claude/deploy-provenance.json via tools/plugin/deploy_provenance.py::place_file
# (the single live writer). Control plane stays here; not a fourth sync tool.
if ($Provenance -and -not $WhatIf) {
    $engine = Join-Path $Root "tools/plugin/deploy_provenance.py"
    $home_ = [Environment]::GetFolderPath("UserProfile")
    & python3 $engine --kind rules --repo $Root --home $home_
    if ($LASTEXITCODE -ne 0) { throw "deploy_provenance.py --kind rules exited $LASTEXITCODE" }
}
