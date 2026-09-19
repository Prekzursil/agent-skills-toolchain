[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\Prekzursil',
    [string]$PythonExe = ''
)

$ErrorActionPreference = 'Stop'

function Resolve-PythonExecutable {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "Requested Python executable does not exist: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source) {
        return $command.Source
    }

    # Clean non-interactive PowerShell sessions on this workstation do not
    # inherit the interactive Python shim. Prefer the machine-local CPython,
    # then the Reframe venv that already satisfies these stdlib-only scripts.
    $candidates = @(
        (Join-Path $env:SystemDrive 'Python314\python.exe'),
        (Join-Path $ProjectRoot 'Documents\GitHub\Reframe\sidecar\.venv\Scripts\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'Python 3 is required for shared-state sync. Pass -PythonExe with an absolute python.exe path.'
}

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Arguments = @()
    )

    # PowerShell 5 leaves LASTEXITCODE unset when a native child never started.
    # Seed it, retain the child output, and require the scripts' exact terminal
    # sentinel so a severed stream can never be laundered into success.
    $global:LASTEXITCODE = 0
    $stepOutput = @(& $Executable $ScriptPath @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $stepOutput | ForEach-Object { Write-Output $_ }
    if ($exitCode -ne 0) {
        throw "Python step failed (exit $exitCode): $ScriptPath"
    }
    if (-not ($stepOutput | Where-Object { $_.ToString().StartsWith('SUCCESS:') })) {
        throw "Python step produced no SUCCESS sentinel: $ScriptPath"
    }
}

$agentsDir = Join-Path $ProjectRoot '.agents'
$codexMergeScript = Join-Path $agentsDir 'scripts\merge_generated_codex_mcp.py'
$claudeMergeScript = Join-Path $agentsDir 'scripts\merge_generated_claude_mcp.py'
$cursorMergeScript = Join-Path $agentsDir 'scripts\merge_generated_cursor_mcp.py'
$zcodeMergeScript = Join-Path $agentsDir 'scripts\merge_generated_zcode_mcp.py'
$localBridgeSyncScript = Join-Path $agentsDir 'scripts\sync_local_bridge_mcp.py'
$validatorScript = Join-Path $agentsDir 'scripts\validate_mcp_control_plane.py'
$referenceViewsScript = Join-Path $agentsDir 'scripts\publish_reference_views.py'
$agentsConfig = Join-Path $agentsDir 'agents.json'
$liveCodex = Join-Path $ProjectRoot '.codex\config.toml'
$liveClaude = Join-Path $ProjectRoot '.claude.json'
$liveCursor = Join-Path $ProjectRoot '.cursor\mcp.json'
# Skills SSOT is the FULL vault at .agents\skills. Owner overrode the old
# Claude 2%-context daily subset (~329 of ~358). LEGAL layout:
#   .claude\skills  --junction/symlink-->  .claude\skills.daily  (HARD-STOP if real dir)
#   .claude\skills.daily  --junction-->  .agents\skills
#     OR a real dir that contains every vault skill (copy fallback if junction rename is locked).
# ILLEGAL: turning .claude\skills into a real directory.
$vaultSkills = Join-Path $ProjectRoot '.agents\skills'
$sharedSkillsTarget = Join-Path $ProjectRoot '.claude\skills.daily'
$skillsLink = Join-Path $ProjectRoot '.claude\skills'
$resolvedPython = Resolve-PythonExecutable -ExplicitPath $PythonExe
Write-Host "  Python OK -> $resolvedPython"

function Get-FirstLinkTarget {
    param([Parameter(Mandatory = $true)][string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.LinkType) { return $null }
    $target = $item.Target
    if ($target -is [System.Array]) {
        $target = $target[0]
    }
    return [string]$target
}

if (-not (Test-Path -LiteralPath $vaultSkills)) {
    Write-Error "STOP: skills vault missing: $vaultSkills"
    exit 1
}

if (-not (Test-Path -LiteralPath $sharedSkillsTarget)) {
    Write-Host "  .claude\skills.daily missing -> creating junction to vault"
    try {
        New-Item -ItemType Junction -Path $sharedSkillsTarget -Target $vaultSkills -Force | Out-Null
        Write-Host "  .claude\skills.daily junction created -> $vaultSkills"
    } catch {
        Write-Error "STOP: failed to create skills.daily junction to vault: $($_.Exception.Message)"
        exit 1
    }
} else {
    $dailyItem = Get-Item -LiteralPath $sharedSkillsTarget -Force
    if (-not $dailyItem.LinkType) {
        # LEGAL fallback (2026-08-26): rename-to-junction was ACCESS DENIED on skills.daily
        # (file lock). Owner still requires the FULL vault, so a real daily dir is allowed
        # only if every vault skill directory is present. Prefer a junction when the lock lifts.
        Write-Host "  WARN: .claude\skills.daily is a real directory (not a junction). Checking full-vault coverage..."
        $missingVaultSkills = New-Object System.Collections.Generic.List[string]
        Get-ChildItem -LiteralPath $vaultSkills -Directory | ForEach-Object {
            if ($_.Name.StartsWith('.')) { return }
            $present = Join-Path $sharedSkillsTarget $_.Name
            if (-not (Test-Path -LiteralPath $present)) {
                $missingVaultSkills.Add($_.Name)
            }
        }
        if ($missingVaultSkills.Count -gt 0) {
            Write-Error "STOP: .claude\skills.daily is a subset, missing $($missingVaultSkills.Count) vault skills. Junction to $vaultSkills (preferred) or copy the missing names. Missing: $($missingVaultSkills -join ', ')"
            exit 1
        }
        Write-Host "  .claude\skills.daily real-dir contains full vault (copy fallback; 2% subset OVERRIDE). Junction still preferred."
    } else {
        $dailyTarget = Get-FirstLinkTarget -Path $sharedSkillsTarget
        $dailyResolved = $dailyTarget
        if (Test-Path -LiteralPath $dailyTarget) {
            $dailyResolved = (Resolve-Path -LiteralPath $dailyTarget).Path
        }
        $vaultResolved = (Resolve-Path -LiteralPath $vaultSkills).Path
        if ($dailyResolved.TrimEnd('\') -ne $vaultResolved.TrimEnd('\')) {
            Write-Error "STOP: .claude\skills.daily links to '$dailyTarget', expected vault $vaultSkills"
            exit 1
        }
        Write-Host "  .claude\skills.daily link OK -> $dailyTarget"
    }
}

if (-not (Test-Path -LiteralPath $skillsLink)) {
    Write-Host "  .claude\skills missing -> recreating shared link to skills.daily"
    try {
        New-Item -ItemType SymbolicLink -Path $skillsLink -Target $sharedSkillsTarget -Force | Out-Null
        Write-Host "  .claude\skills symlink restored -> $sharedSkillsTarget"
    } catch {
        try {
            New-Item -ItemType Junction -Path $skillsLink -Target $sharedSkillsTarget -Force | Out-Null
            Write-Host "  .claude\skills junction restored -> $sharedSkillsTarget"
        } catch {
            Write-Error "STOP: failed to restore .claude\skills link: $($_.Exception.Message)"
            exit 1
        }
    }
} else {
    $item = Get-Item -LiteralPath $skillsLink -Force
    if (-not $item.LinkType) {
        Write-Error "STOP: .claude\skills exists but is a REAL DIRECTORY. Illegal. It must stay a junction/symlink to skills.daily. Investigate before syncing."
        exit 1
    }
    Write-Host "  .claude\skills link OK -> $($item.Target)"
}

Write-Host '==> harness integrity gate (H3, 2026-09-19)'
& $resolvedPython (Join-Path $agentsDir 'scripts\check_harness_integrity.py')
if ($LASTEXITCODE -ne 0) { Write-Warning 'INTEGRITY violation - fix surfaces or set INTEGRITY=warn' }

Write-Host '==> pin-drift gate (pin-all policy 2026-09-19)'
& $resolvedPython (Join-Path $agentsDir 'scripts\check_pin_drift.py')
if ($LASTEXITCODE -ne 0) { Write-Warning 'PIN DRIFT detected - pin or set PIN_DRIFT=warn' }

Write-Host '==> validate shared MCP registry and reference-only credentials'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $validatorScript -Arguments @('--agents-config', $agentsConfig)

Write-Host '==> publish reference-only provider views'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $referenceViewsScript -Arguments @('--agents-config', $agentsConfig)

# integrations.enabled is intentionally empty. Native agents sync would emit a
# second generated MCP surface and can interpolate local credential overrides.
Write-Host '==> native agents MCP materialization disabled; using atomic provider mergers'

Write-Host '==> merge agents-managed Codex MCP blocks into live .codex/config.toml'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $codexMergeScript -Arguments @('--live', $liveCodex, '--agents-config', $agentsConfig, '--write')

Write-Host '==> merge agents-managed Claude MCP into .claude.json'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $claudeMergeScript -Arguments @('--live', $liveClaude, '--agents-config', $agentsConfig, '--write')

Write-Host '==> merge agents-managed Cursor MCP into .cursor\mcp.json'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $cursorMergeScript -Arguments @('--live', $liveCursor, '--agents-config', $agentsConfig, '--write')

Write-Host '==> merge agents-managed ZCode MCP into .zcode\cli\config.json'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $zcodeMergeScript -Arguments @('--agents-config', $agentsConfig, '--write')

Write-Host '==> sync local Claude bridge MCP from agents definitions'
Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $localBridgeSyncScript

# Hermes Agent control-plane integration (2026-09-03):
#   1. MCP: deploy registry servers with target 'hermes' into Hermes config.yaml
#      mcp_servers (HTTP-hub-only transport policy, G-1). deploy_hermes_mcp.py is
#      idempotent and backs up config.yaml first.
#   2. Skills: materialize the shared skills vault into Hermes' skills dir
#      (copy, like the Claude materialized-target pattern).
$hermesMcpDeploy = Join-Path $agentsDir 'scripts\deploy_hermes_mcp.py'
$hermesSkillsSync = Join-Path $agentsDir 'scripts\sync_hermes_skills.ps1'
if (Test-Path $hermesMcpDeploy) {
    Write-Host '==> deploy Hermes MCP servers from agents.json (HTTP hubs only)'
    Invoke-CheckedPython -Executable $resolvedPython -ScriptPath $hermesMcpDeploy
} else {
    Write-Host '  WARN: deploy_hermes_mcp.py missing - skip Hermes MCP deploy'
}
if (Test-Path $hermesSkillsSync) {
    Write-Host '==> materialize shared skills into Hermes skills dir'
    & powershell -NoProfile -ExecutionPolicy Bypass -File $hermesSkillsSync
    if ($LASTEXITCODE -ne 0) { Write-Error 'STOP: Hermes skills sync failed' }
} else {
    Write-Host '  WARN: sync_hermes_skills.ps1 missing - skip Hermes skills sync'
}

Write-Host '==> materialize gemini MCP surface (D7 stage, added 2026-09-19; region repaired 2026-09-19 H3 — was string-swallowed since D12 splice)'
$geminiMerge = Join-Path $agentsDir 'scripts\merge_generated_gemini_mcp.py'
if (Test-Path $geminiMerge) {
    & $resolvedPython $geminiMerge --write
} else {
    Write-Warning "merge_generated_gemini_mcp.py not found"
}

Write-Host '==> materialize shared rules (D12 stage, added 2026-09-19)'
$rulesSync = Join-Path $agentsDir 'scripts\sync-rules.ps1'
if (Test-Path $rulesSync) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $rulesSync
} else {
    Write-Warning "sync-rules.ps1 not found at $rulesSync"
}

Write-Host 'SUCCESS:shared-state-sync'
