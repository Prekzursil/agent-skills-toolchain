<#
.SYNOPSIS
  Bulk-sync repo skills into the live ~/.agents/skills directory in one pass.

.DESCRIPTION
  Replaces the slow "copy skills one by one" workflow. Copies every skill directory
  under skills/ (and optionally skills-claude-only/) into the live agents skills dir,
  overwriting existing copies. Optionally prunes live skill dirs that no longer exist
  in the repo (e.g. consolidated or deleted skills such as the former codex-local-*
  and agent-lanes-codex-* lanes). Worth a -Prune pass after the 2026-08-09 Codex-lane
  retirement, which rewrote codex-consult into a redirect tombstone and rebased
  codex-orchestrate and multi-agent-quickstart onto the codex mcp-server rail.

  This is the imperative-copy bridge for the current ~/.agents/skills setup. The
  declarative alternative is the plugin marketplace shipped in .claude-plugin/ —
  see README "Quick Start" for the sparse Git-hosted install flow.

.PARAMETER IncludeClaudeOnly
  Also sync skills-claude-only/ (the Claude-specific skills).

.PARAMETER Prune
  Remove live skill dirs under Dest that are not present in the synced source set.
  Pruning only ever touches directories that contain a SKILL.md (so unrelated dirs
  and the .system folder are never deleted).

.PARAMETER WhatIf
  Show what would be copied/pruned without making changes.

.EXAMPLE
  pwsh -File scripts/sync-skills.ps1

.EXAMPLE
  pwsh -File scripts/sync-skills.ps1 -IncludeClaudeOnly -Prune
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents/skills"),
    [switch]$IncludeClaudeOnly,
    [switch]$Prune,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$sourceDirs = @((Join-Path $Root "skills"))
if ($IncludeClaudeOnly) {
    $sourceDirs += (Join-Path $Root "skills-claude-only")
}

if (-not (Test-Path $Dest)) {
    Write-Host "Creating live skills dir: $Dest"
    if (-not $WhatIf) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
}

# Collect every skill directory (a dir containing SKILL.md) across the source sets.
$skillDirs = foreach ($src in $sourceDirs) {
    if (Test-Path $src) {
        Get-ChildItem -Path $src -Directory | Where-Object {
            Test-Path (Join-Path $_.FullName "SKILL.md")
        }
    }
}

$synced = [System.Collections.Generic.HashSet[string]]::new()
$copied = 0
foreach ($dir in $skillDirs) {
    [void]$synced.Add($dir.Name)
    $target = Join-Path $Dest $dir.Name
    if ($WhatIf) {
        Write-Host "[whatif] copy $($dir.Name)"
    } else {
        if (Test-Path $target) { Remove-Item -Recurse -Force $target }
        Copy-Item -Recurse -Force -Path $dir.FullName -Destination $target
    }
    $copied++
}
Write-Host "Synced $copied skill(s) -> $Dest"

if ($Prune) {
    $orphans = Get-ChildItem -Path $Dest -Directory -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ne ".system" -and
        (Test-Path (Join-Path $_.FullName "SKILL.md")) -and
        (-not $synced.Contains($_.Name))
    }
    foreach ($orphan in $orphans) {
        if ($WhatIf) {
            Write-Host "[whatif] prune orphan $($orphan.Name)"
        } else {
            Write-Host "Pruning orphan (not in repo): $($orphan.Name)"
            Remove-Item -Recurse -Force $orphan.FullName
        }
    }
    if (-not $orphans) { Write-Host "No orphans to prune." }
}
