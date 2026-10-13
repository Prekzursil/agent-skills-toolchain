#!/usr/bin/env pwsh
<#
check-index-freshness — gate for derived semantic/manifest indexes (fail-closed).

Class: the semantic-router index (~/.claude/hooks/semantic-router/index/) is built
by a FAIL-SOFT builder (Ollama down => skip, keep old index). Measured 2026-09-30:
built_at was 2026-06-29 with 358 units while the tree held 422 skills — the router
silently lost 3 months of skills. This gate makes that state LOUD.

Checks (semantic router):
  1. index exists and meta.json parses
  2. skill-row count vs live skills tree (|tree| - |rows| <= $MaxSkillDrift, default 8)
  3. built_at is not older than the newest SKILL.md mtime
  4. mcp lane present when an mcp source file exists (source-path drift detector)

Exit 0 + "SUCCESS:index-freshness <detail>" or exit 1 + "FAILED:index-freshness <reason>".
Used by sync-skills.ps1 (warning context) and safe to run standalone / in CI.
#>
param(
    [int]$MaxSkillDrift = 8,
    [string]$MetaPath = "$env:USERPROFILE\.claude\hooks\semantic-router\index\meta.json",
    [string]$SkillsDir = "$env:USERPROFILE\.agents\skills"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $MetaPath)) {
    Write-Output "FAILED:index-freshness no index at $MetaPath (run build_index.py)"
    exit 1
}
try {
    $meta = Get-Content $MetaPath -Raw | ConvertFrom-Json
} catch {
    Write-Output "FAILED:index-freshness meta.json unparseable: $($_.Exception.Message)"
    exit 1
}

$treeCount = (Get-ChildItem -Path $SkillsDir -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName "SKILL.md") }).Count
if ($treeCount -eq 0) {
    Write-Output "FAILED:index-freshness skills tree unreadable at $SkillsDir"
    exit 1
}

$indexSkills = 0
if ($meta.by_kind -and $meta.by_kind.PSObject.Properties["skill"]) {
    $indexSkills = [int]$meta.by_kind.skill
}
$drift = $treeCount - $indexSkills
if ($drift -gt $MaxSkillDrift) {
    Write-Output "FAILED:index-freshness skill drift $drift (tree=$treeCount index=$indexSkills, max=$MaxSkillDrift); built_at=$($meta.built_at)"
    exit 1
}

$newest = (Get-ChildItem -Path $SkillsDir -Recurse -Filter "SKILL.md" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
if ($newest -and $meta.built_at) {
    $built = if ($meta.built_at -is [datetime]) { $meta.built_at }
    else { [datetime]::Parse([string]$meta.built_at, [Globalization.CultureInfo]::InvariantCulture) }
    if ($newest -gt $built.AddMinutes(2)) {
        Write-Output "FAILED:index-freshness built_at $($meta.built_at) predates newest SKILL.md $($newest.ToString('o'))"
        exit 1
    }
}

$mcpSource = @("$env:USERPROFILE\.mcp.json", "$env:USERPROFILE\.claude.json") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if ($mcpSource) {
    $indexMcp = 0
    if ($meta.by_kind -and $meta.by_kind.PSObject.Properties["mcp"]) { $indexMcp = [int]$meta.by_kind.mcp }
    if ($indexMcp -eq 0) {
        Write-Output "FAILED:index-freshness mcp lane empty while source exists ($mcpSource) - source-path drift?"
        exit 1
    }
}

Write-Output "SUCCESS:index-freshness units=$($meta.count) skills=$indexSkills/$treeCount mcp=$($meta.by_kind.mcp) built_at=$($meta.built_at)"
exit 0
