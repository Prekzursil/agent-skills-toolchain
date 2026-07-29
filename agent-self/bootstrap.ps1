#requires -version 5.1
<#
.SYNOPSIS  Deploy this agent-self bundle onto the current machine 1:1.
  Copies config/ -> ~/.claude, skills/ -> ~/.agents/skills, substitutes {{USER_HOME}}/{{USER}},
  and backs up any existing ~/.claude first. Non-destructive on ~/.claude.json (your projects/login).
.EXAMPLE  pwsh agent-self/bootstrap.ps1
#>
param([switch]$NoBackup)
$ErrorActionPreference = 'Stop'
$Self        = $PSScriptRoot
$HomePath    = $env:USERPROFILE
$HomeFwd     = $HomePath.Replace('\', '/')
$UserName    = $env:USERNAME
$ClaudeHome  = Join-Path $HomePath '.claude'
$AgentsSkills = Join-Path $HomePath '.agents\skills'

if (-not (Test-Path (Join-Path $Self 'config'))) { Write-Error "Run from the agent-self bundle (config/ not found)."; exit 1 }

# 1. back up existing ~/.claude
if ((Test-Path $ClaudeHome) -and -not $NoBackup) {
    $bak = "$ClaudeHome.backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Write-Host "Backing up existing ~/.claude -> $bak" -ForegroundColor Yellow
    Copy-Item $ClaudeHome $bak -Recurse -Force
}

# 2. deploy the repo-root hooks/ library -> ~/.claude/hooks (BASE layer)
# config/hooks/ holds only ~20 of the ~70 hook packages, but config/settings.json
# registers 17 commands that live ONLY in the repo-root hooks/ tree (measured:
# _dispatch/dispatch.py, per-edit-check, no-force-push, file-scope, open-loops,
# selection-events, ...), plus two cross-package imports config/hooks/ cannot
# satisfy on its own (inquisitiveness -> calibrated-silence, event-ledger ->
# _shared). Without this step every one of those resolves to a nonexistent path
# on a freshly bootstrapped machine and the hook silently never runs.
# Deployed BEFORE config/ on purpose: the two trees have diverged (measured: 2 of
# the 4 files present in both differ), and config/hooks/ is the curated snapshot
# of the live ~/.claude, so it must land LAST and win.
New-Item -ItemType Directory -Force $ClaudeHome | Out-Null
$RepoHooks = Join-Path (Split-Path $Self -Parent) 'hooks'
if (Test-Path $RepoHooks) {
    New-Item -ItemType Directory -Force (Join-Path $ClaudeHome 'hooks') | Out-Null
    Copy-Item (Join-Path $RepoHooks '*') (Join-Path $ClaudeHome 'hooks') -Recurse -Force
}

# 3. deploy config/ -> ~/.claude (merge over existing; wins over the base layer)
Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force

# 4. substitute templated tokens in deployed text files
$textExt = '.json', '.md', '.ps1', '.sh', '.py', '.toml', '.txt', ''
Get-ChildItem $ClaudeHome -Recurse -File | Where-Object { $textExt -contains $_.Extension.ToLower() } | ForEach-Object {
    $c = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $c) { return }
    $c = $c.Replace('{{USER_HOME}}', $HomeFwd).Replace('{{USER}}', $UserName)
    Set-Content $_.FullName $c -NoNewline -Encoding UTF8
}

# 5. skills -> ~/.agents/skills, and ensure ~/.claude/skills points at them
New-Item -ItemType Directory -Force $AgentsSkills | Out-Null
Copy-Item (Join-Path $Self 'skills\*') $AgentsSkills -Recurse -Force
$claudeSkills = Join-Path $ClaudeHome 'skills'
if (-not (Test-Path $claudeSkills)) {
    try { New-Item -ItemType SymbolicLink -Path $claudeSkills -Target $AgentsSkills -ErrorAction Stop | Out-Null }
    catch { New-Item -ItemType Directory -Force $claudeSkills | Out-Null; Copy-Item (Join-Path $Self 'skills\*') $claudeSkills -Recurse -Force }
}

# 6. MCP config (non-destructive: copy project file, leave ~/.claude.json alone)
$mcp = Join-Path $Self 'config\mcp'
if (Test-Path (Join-Path $mcp 'mcp.json')) { Copy-Item (Join-Path $mcp 'mcp.json') (Join-Path $HomePath '.mcp.json') -Force }

Write-Host "`nDEPLOYED." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Set secret env vars (see $Self\secrets.example.json): HACKTRICKS_API_KEY and the `${...}` MCP tokens."
Write-Host "     e.g.  [Environment]::SetEnvironmentVariable('HACKTRICKS_API_KEY','<value>','User')"
Write-Host "  2. Merge $mcp\user-claude.json -> ~/.claude.json 'mcpServers' if you want the MCP servers (left untouched here)."
Write-Host "  3. Run:  claude  ->  /login   (SessionStart hooks replay the ledger; MEMORY.md auto-loads)."
