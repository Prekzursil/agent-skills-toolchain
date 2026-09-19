#Requires -Version 5.1
<#
.SYNOPSIS
  Materialize the shared skills vault (.agents\skills) into the Hermes Agent
  skills directory (copy-based materialization, G-3 decision 2026-09-03).
.DESCRIPTION
  Mirrors the deploy-skills pattern: robocopy /MIR the vault into the Hermes
  skills dir, then remove file attributes for compatibility. Hermes skills dir
  is a materialized SYNC TARGET (like ~\.claude\skills) - only this script
  writes there (G-97/G-98 analogue).
  Idempotent; exits 0 on success. Backup-first: existing dir is not backed up
  wholesale (it is regenerable from the vault), but deletions are logged.
#>
$ErrorActionPreference = 'Stop'

$vault      = 'C:\Users\Prekzursil\.agents\skills'
$hermesHome = Join-Path $env:LOCALAPPDATA 'hermes'
$target     = Join-Path $hermesHome 'skills'

if (-not (Test-Path $vault)) { Write-Error "STOP: skills vault missing: $vault" }

# Herds category dirs (apple, creative, ...) - mirror the whole vault.
if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }

# /MIR = purge extras so the target converges to the vault (true materialization)
robocopy $vault $target /MIR /R:2 /W:1 /NFL /NDL /NP /NJH | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Error "STOP: robocopy failed (exit $LASTEXITCODE)" }

# Clear read-only attributes robocopy may have carried over
attrib -R "$target\*" /S /D 2>$null

$count = (Get-ChildItem $target -Recurse -Filter 'SKILL.md' -ErrorAction SilentlyContinue).Count
Write-Host "  Hermes skills materialized: $count SKILL.md files -> $target"
exit 0
