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

  THIS IS THE LAST HOP BEFORE CODE EXECUTES. mon.cmd puts
  ~/.agents/skills/workflow-monitor on PYTHONPATH and runs `python -m monitorcore.monitors`,
  so whatever this script last deployed is what every registered monitor runs. No repo gate
  can see this hop: vendordrift compares committed copies by index OID, so a deploy lag is
  structurally invisible to CI. Measured 2026-08-17 (bug WF-5): the live monitorcore was 37
  modules against the repo's 38 because this script had not run since before 2026-08-12.

  THE SYNC IS DESTRUCTIVE PER SKILL. Each target directory is removed with
  Remove-Item -Recurse -Force and then re-copied, so any file that exists only in the
  live copy of a synced skill is deleted. That is correct for a deploy target, but it
  means the blast radius of a bulk run is every skill, not just the one you fixed. Use
  -Skill to scope the run when other agents or live monitors own the rest of the tree.

.PARAMETER IncludeClaudeOnly
  Also sync skills-claude-only/ (the Claude-specific skills).

.PARAMETER Skill
  Sync ONLY the named skill directories. Names are skill directory names (e.g.
  workflow-monitor), matched case-insensitively; every name must exist in the source
  set or the run throws before copying anything.

  This exists because of the destructive per-skill semantics above. Measured 2026-08-17
  against the real trees: a bulk run wipes+recopies 326 shared skill dirs and removes
  244 live-only files. When another agent, a live fleet, or a running monitor owns some
  of those skills, a scoped deploy is the only way to ship one skill's fix without
  touching them.

  Accepts either a comma-joined string or repeated values, because `pwsh -File` passes
  every argument as a LITERAL STRING and does NOT split an array parameter on commas the
  way an in-session call does.

  Cannot be combined with -Prune -- see the guard below for why.

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

.EXAMPLE
  # Ship one skill's fix while a live fleet owns the rest of the tree.
  pwsh -File scripts/sync-skills.ps1 -Skill workflow-monitor,monitor-launcher
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents/skills"),
    [switch]$IncludeClaudeOnly,
    [string[]]$Skill,
    [switch]$Prune,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# -Skill + -Prune is REFUSED, not quietly honoured. $synced below would hold only the
# filtered names, and the prune pass deletes every live skill dir whose name is missing
# from $synced -- i.e. every skill the filter was there to protect. Fail closed before
# anything is written rather than discover it after 300+ directories are gone.
if ($Skill -and $Prune) {
    throw "FAILED:sync-skills -Skill cannot be combined with -Prune (prune deletes every skill outside the filter)."
}

$sourceDirs = @((Join-Path $Root "skills"))
if ($IncludeClaudeOnly) {
    $sourceDirs += (Join-Path $Root "skills-claude-only")
}

if (-not (Test-Path $Dest)) {
    Write-Host "Creating live skills dir: $Dest"
    if (-not $WhatIf) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
}

# Collect every skill directory (a dir containing SKILL.md) across the source sets.
$skillDirs = @(foreach ($src in $sourceDirs) {
    if (Test-Path $src) {
        Get-ChildItem -Path $src -Directory | Where-Object {
            Test-Path (Join-Path $_.FullName "SKILL.md")
        }
    }
})

# Scope AFTER discovery so an unknown name is reported against the real source set, and so
# a typo can never degrade into a successful no-op run (an empty filtered set would print
# "Synced 0 skill(s)" and exit 0).
if ($Skill) {
    # `pwsh -File` hands arguments through as literal strings, so
    # `-Skill workflow-monitor,monitor-launcher` -- the form in .EXAMPLE above -- arrives as
    # ONE element and was rejected as an unknown skill. Measured 2026-08-17 by the test
    # suite, on the very example this file documents. Splitting here makes the -File and
    # in-session invocation styles agree. Safe because no skill directory contains a comma
    # (measured: 0 of 338 repo dirs, 0 of 330 live dirs).
    $names = @($Skill |
        ForEach-Object { $_ -split ',' } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ })
    if ($names.Count -eq 0) {
        throw "FAILED:sync-skills -Skill was supplied but resolved to no names."
    }

    $available = @($skillDirs | ForEach-Object { $_.Name })
    $unknown = @($names | Where-Object { $available -notcontains $_ })
    if ($unknown.Count -gt 0) {
        throw "FAILED:sync-skills unknown skill(s): $($unknown -join ', '). Nothing was copied."
    }

    $wanted = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($n in $names) { [void]$wanted.Add($n) }
    $skillDirs = @($skillDirs | Where-Object { $wanted.Contains($_.Name) })
    Write-Host "Scoped to $($skillDirs.Count) skill(s): $(($skillDirs | ForEach-Object { $_.Name }) -join ', ')"
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

# Derived-index freshness (rules/common/derived-index-freshness.md): a deployed skill
# the semantic router cannot see is deployed nowhere. Gate -> one rebuild attempt ->
# loud fail-open warning (same posture as the router itself).
if (-not $WhatIf) {
    Write-Host ""
    Write-Host "[semantic-router index freshness]"
    $gate = & pwsh -NoProfile -File (Join-Path $PSScriptRoot "check-index-freshness.ps1") 2>&1
    Write-Host ($gate | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        Write-Host "gate failed - attempting one index rebuild..."
        & python "$env:USERPROFILE\.claude\hooks\semantic-router\build_index.py" --quiet 2>&1 |
            Select-Object -Last 2 | Write-Host
        $gate2 = & pwsh -NoProfile -File (Join-Path $PSScriptRoot "check-index-freshness.ps1") 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARN:semantic-index-stale gate still failing after rebuild: $($gate2 | Out-String)"
            Write-Host "       (ollama up? nomic-embed-text pulled? source paths drifted?)"
            Write-Host "       deploy succeeded; semantic routing is degraded until the gate passes."
        } else {
            Write-Host ($gate2 | Out-String).Trim()
        }
    }
}
