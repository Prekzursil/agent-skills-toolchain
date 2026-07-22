<#
================================================================================
 enable-linkedin-mcp.ps1  --  make the LinkedIn MCP visible + runnable, DISABLED
================================================================================
 WHY THIS EXISTS
   tools/mcp/linkedin-mcp/ was merged to origin/main in 469cf83 (PR #112) and its
   deps were bumped in 26b9869 (PR #119), but the local checkout is 14 commits
   BEHIND origin/main, so the directory does not exist on disk. That -- not a
   missing registration -- is why the server never appeared. Registering it
   without pulling would only produce a dead server pointing at a missing venv.

 WHAT IT DOES (idempotent; safe to re-run)
   1. Fast-forward-only pull of the toolchain checkout (refuses on divergence,
      and refuses if the incoming commits would clobber a dirty file).
   2. Builds the server venv via `uv sync`.
   3. Registers "linkedin" in ~/.mcp.json  -- the CANONICAL surface. It is NOT
      rewritten by a running Claude session (verified: mtime hours stale, while
      ~/.claude.json is rewritten every ~30s), so this edit survives.
   4. Adds "linkedin" to ~/.claude/.mcp-disabled-defaults.json so the
      enforce-mcp-defaults hook keeps it OFF in every project -- honouring the
      standing preference: "exposed but kept disabled rather than not visible".
   5. Verifies the server completes an MCP handshake and lists its 11 tools.

 WHAT IT DELIBERATELY DOES NOT DO
   * Never touches ~/.claude.json (clobbered every ~30s by the live session).
   * Never writes a token anywhere. Credentials stay in your OS environment.
   * Never runs `git add`/commit/push.

 USAGE
   pwsh -NoProfile -File enable-linkedin-mcp.ps1 -DryRun   # show the plan
   pwsh -NoProfile -File enable-linkedin-mcp.ps1           # apply

 EXIT CODES  0 = ok / dry-run ok ; 1 = aborted (guard or verify failed)
================================================================================
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [string]$Repo = "$env:USERPROFILE\source\agent-skills-toolchain"
)

$ErrorActionPreference = 'Stop'
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Say "ABORT: $m" Red; exit 1 }

$srvDir   = Join-Path $Repo 'tools\mcp\linkedin-mcp'
$mcpJson  = Join-Path $env:USERPROFILE '.mcp.json'
$disabled = Join-Path $env:USERPROFILE '.claude\.mcp-disabled-defaults.json'

Say "=== enable-linkedin-mcp ===" Cyan
Say "  repo     : $Repo"
Say "  ~/.mcp.json      : $mcpJson"
Say "  disabled-defaults: $disabled"
Say ""

# --- 0. Guards ------------------------------------------------------------------
if (-not (Test-Path $Repo))     { Die "repo not found: $Repo" }
if (-not (Test-Path $mcpJson))  { Die "$mcpJson not found (canonical MCP surface)." }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Die "'uv' not on PATH." }

$remote = (& git -C $Repo remote get-url origin) 2>$null
if ($remote -notmatch 'agent-skills-toolchain') { Die "wrong repo at $Repo (origin = $remote)" }

# --- 1. Fast-forward the checkout ------------------------------------------------
Say "[1/5] Fetching origin ..." Cyan
& git -C $Repo fetch origin --quiet
if ($LASTEXITCODE -ne 0) { Die "git fetch failed." }

$behind = (& git -C $Repo rev-list --count HEAD..origin/main).Trim()
$ahead  = (& git -C $Repo rev-list --count origin/main..HEAD).Trim()
Say "      local main is $behind behind / $ahead ahead of origin/main"

if ($ahead -ne '0') { Die "local main has $ahead unpushed commit(s) -- diverged. Resolve manually; this script only fast-forwards." }

if ($behind -ne '0') {
  # Refuse if an incoming commit would overwrite a locally-modified file.
  $incoming = @(& git -C $Repo diff --name-only HEAD origin/main)
  $dirty    = @(& git -C $Repo diff --name-only HEAD)
  $clash    = @($incoming | Where-Object { $dirty -contains $_ })
  if ($clash.Count -gt 0) { Die "these dirty files would be clobbered by the pull: $($clash -join ', '). Commit or stash them first." }

  if ($DryRun) { Say "      DRY RUN: would fast-forward $behind commit(s)." Yellow }
  else {
    & git -C $Repo merge --ff-only origin/main
    if ($LASTEXITCODE -ne 0) { Die "fast-forward merge failed." }
    Say "      fast-forwarded $behind commit(s)." Green
  }
} else { Say "      already up to date." Green }

# --- 2. Build the venv -----------------------------------------------------------
Say "[2/5] Building the server venv ..." Cyan
$py = Join-Path $srvDir '.venv\Scripts\python.exe'
if ($DryRun) { Say "      DRY RUN: would run 'uv sync' in $srvDir" Yellow }
else {
  if (-not (Test-Path $srvDir)) { Die "$srvDir still missing after the pull -- unexpected." }
  Push-Location $srvDir
  try { & uv sync; if ($LASTEXITCODE -ne 0) { Die "uv sync failed." } } finally { Pop-Location }
  if (-not (Test-Path $py)) { Die "venv python not found at $py" }
  Say "      venv ready: $py" Green
}

# --- 3. Register in ~/.mcp.json (canonical, NOT clobbered) -----------------------
Say "[3/5] Registering 'linkedin' in ~/.mcp.json ..." Cyan
$entry = [ordered]@{
  type    = 'stdio'
  command = $py
  args    = @((Join-Path $srvDir 'server.py'))
  env     = [ordered]@{
    LINKEDIN_ACCESS_TOKEN = '${LINKEDIN_ACCESS_TOKEN}'
    LINKEDIN_CLIENT_ID    = '${LINKEDIN_CLIENT_ID}'
    LINKEDIN_CLIENT_SECRET= '${LINKEDIN_CLIENT_SECRET}'
    LINKEDIN_REDIRECT_URI = '${LINKEDIN_REDIRECT_URI}'
  }
}
$cfg = Get-Content -Raw -LiteralPath $mcpJson | ConvertFrom-Json
if ($null -eq $cfg.mcpServers) { Die "~/.mcp.json has no 'mcpServers' key." }
$already = [bool]($cfg.mcpServers.PSObject.Properties.Name -contains 'linkedin')
Say "      currently $(@($cfg.mcpServers.PSObject.Properties).Count) servers; 'linkedin' present: $already"

if ($DryRun) { Say "      DRY RUN: would add/refresh the 'linkedin' entry." Yellow }
else {
  Copy-Item $mcpJson "$mcpJson.bak-linkedin-$(Get-Date -Format yyyyMMdd-HHmmss)" -Force
  $cfg.mcpServers | Add-Member -NotePropertyName 'linkedin' -NotePropertyValue $entry -Force
  $out = $cfg | ConvertTo-Json -Depth 20
  [System.IO.File]::WriteAllText($mcpJson, $out, [System.Text.UTF8Encoding]::new($false))
  # re-parse to prove we did not corrupt it
  $null = Get-Content -Raw -LiteralPath $mcpJson | ConvertFrom-Json
  Say "      registered (backup taken)." Green
}

# --- 4. Keep it DISABLED by default ----------------------------------------------
Say "[4/5] Adding 'linkedin' to the disabled-by-default list ..." Cyan
if (-not (Test-Path $disabled)) { Say "      NOTE: $disabled not found -- skipping (server will be ENABLED)." Yellow }
else {
  $dj = Get-Content -Raw -LiteralPath $disabled | ConvertFrom-Json
  if ($dj.disabledMcpServers -contains 'linkedin') { Say "      already listed." Green }
  elseif ($DryRun) { Say "      DRY RUN: would append 'linkedin'." Yellow }
  else {
    Copy-Item $disabled "$disabled.bak-linkedin-$(Get-Date -Format yyyyMMdd-HHmmss)" -Force
    $dj.disabledMcpServers = @($dj.disabledMcpServers) + 'linkedin' | Sort-Object -Unique
    [System.IO.File]::WriteAllText($disabled, ($dj | ConvertTo-Json -Depth 20), [System.Text.UTF8Encoding]::new($false))
    Say "      added -- exposed in the roster, OFF until you enable it." Green
  }
}

# --- 5. Verify the handshake ------------------------------------------------------
Say "[5/5] Verifying the MCP handshake (no token needed) ..." Cyan
if ($DryRun) { Say "      DRY RUN: skipped." Yellow; Say ""; Say "DRY RUN COMPLETE - nothing written." Yellow; exit 0 }

$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
$note = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
$list = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
$tmpIn = Join-Path $env:TEMP "li-probe-$PID.jsonl"
Set-Content -LiteralPath $tmpIn -Value ($init, $note, $list) -Encoding utf8
try {
  $resp = (Get-Content -Raw $tmpIn | & $py (Join-Path $srvDir 'server.py') 2>$null)
  $tools = ([regex]::Matches($resp, '"name"\s*:\s*"(linkedin_[a-z_]+)"') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  if ($tools.Count -ge 11) { Say "      HANDSHAKE OK - $($tools.Count) tools: $($tools -join ', ')" Green }
  elseif ($tools.Count -gt 0) { Say "      PARTIAL - only $($tools.Count) tools listed: $($tools -join ', ')" Yellow }
  else { Say "      VERIFY FAILED - no tools listed. Run manually: $py $srvDir\server.py" Red; exit 1 }
} finally { Remove-Item $tmpIn -ErrorAction SilentlyContinue }

Say ""
Say "DONE." Green
Say "  * 'linkedin' is now in ~/.mcp.json and DISABLED by default." Cyan
Say "  * To use it: set `$env:LINKEDIN_ACCESS_TOKEN (see tools/mcp/linkedin-mcp/SETUP.md)," Cyan
Say "    remove 'linkedin' from that project's disabledMcpServers in ~/.claude.json," Cyan
Say "    and restart Claude Code. Then call linkedin_auth_status." Cyan
exit 0
