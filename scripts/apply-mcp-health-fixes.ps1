<#
================================================================================
 apply-mcp-health-fixes.ps1
================================================================================
 PURPOSE
   Apply the 2026-07-20 mcp-health findings to USER scope
   (~/.claude.json -> top-level "mcpServers"):

     1. fb-messenger: REGISTER (was absent from Claude entirely; it existed only
                      in ~/.grok/config.toml). MEASURED: stdio handshake OK,
                      serverInfo {"name":"fb-messenger","version":"1.27.2"},
                      33 tools.

   NOT a fix here, deliberately -- agent-mail's URL.
   An earlier probe reported GET /mcp -> 404 and GET /mcp/ -> 200 and concluded
   a trailing slash was required. That was a MEASUREMENT ARTIFACT: curl defaults
   to GET, but the MCP streamable-HTTP transport is POST, and POST returns a
   valid handshake on BOTH paths. The registered URL is correct as-is; this
   script leaves it alone. agent-mail's unavailability is a client-side
   connection problem, not a bad pointer.

 WHY A SCRIPT AND NOT A LIVE EDIT
   A running Claude Code session holds ~/.claude.json in memory and rewrites it
   roughly every 30s, CLOBBERING any external edit made while it is open.

       >>> CLOSE ALL CLAUDE CODE SESSIONS/WINDOWS BEFORE RUNNING THIS. <<<

 SAFETY
   * Timestamped backup of ~/.claude.json BEFORE writing; aborts if the backup
     is missing or zero-length.
   * Edits ONLY the fb-messenger entry inside the top-level "mcpServers" object.
     "projects", oauth, caches and "disabledMcpServers" are left untouched.
   * Re-parses the result and asserts the entry is correct and the projects
     map still has the same entry count; ABORTS without replacing on failure.
   * Refuses to run while a claude process is alive (override with -Force).
   * Idempotent: re-running is a no-op once applied.

 USAGE
   pwsh -NoProfile -File scripts/apply-mcp-health-fixes.ps1 -DryRun   # show plan
   pwsh -NoProfile -File scripts/apply-mcp-health-fixes.ps1           # apply
================================================================================
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }

$claudeJson = Join-Path $env:USERPROFILE '.claude.json'
if (-not (Test-Path $claudeJson)) { Say "ABORT: $claudeJson not found." Red; exit 1 }

# --- Guard: Claude must be closed -----------------------------------------------
$live = @(Get-Process -Name 'claude' -ErrorAction SilentlyContinue)
if ($live.Count -eq 0) {
    $live = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'claude.*cli\.js' })
}
if ($live.Count -gt 0 -and -not $Force) {
    Say "ABORT: $($live.Count) live Claude process(es) detected." Red
    Say "       Close all Claude Code sessions first, or pass -Force if you are certain." Yellow
    exit 1
}

# --- Desired state ---------------------------------------------------------------
$FB_BASE        = 'C:\Users\Prekzursil\source\repos\fb-messenger-mcp'
$FB_PYTHON      = Join-Path $FB_BASE '.venv\Scripts\python.exe'
$FB_SERVER      = Join-Path $FB_BASE 'server.py'

foreach ($p in @($FB_PYTHON, $FB_SERVER)) {
    if (-not (Test-Path $p)) { Say "ABORT: fb-messenger path missing: $p" Red; exit 1 }
}

# --- Load -------------------------------------------------------------------------
# NOTE: ConvertFrom-Json CANNOT be used here. ~/.claude.json contains case-distinct
# project keys (e.g. .../Documents/github/Reframe and .../Documents/GitHub/Reframe)
# and ConvertFrom-Json collapses them and throws. Use a System.Text.Json DOM edit,
# same as hooks/mcp-userscope-sync/promote-mcp-userscope.ps1.
$raw  = Get-Content -LiteralPath $claudeJson -Raw -Encoding UTF8
$root = [System.Text.Json.Nodes.JsonNode]::Parse($raw)
if ($null -eq $root['mcpServers']) { Say "ABORT: ~/.claude.json has no top-level 'mcpServers'." Red; exit 1 }

$servers = $root['mcpServers'].AsObject()

$projCountBefore = 0
if ($null -ne $root['projects']) { $projCountBefore = @($root['projects'].AsObject()).Count }

$hasFb = ($null -ne $servers['fb-messenger'])

Say "PLAN" Cyan
Say ("  fb-messenger : {0}  ->  register (stdio)" -f $(if ($hasFb) { 'present' } else { '<absent>' }))
Say ("  projects entries to preserve: {0}" -f $projCountBefore)

if ($hasFb) {
    Say "NO-OP: fb-messenger already registered." Green
    exit 0
}

if ($DryRun) { Say "DryRun: nothing written." Yellow; exit 0 }

# --- Backup ------------------------------------------------------------------------
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$claudeJson.bak-mcp-health-$stamp"
Copy-Item -LiteralPath $claudeJson -Destination $backup -Force
if (-not (Test-Path $backup) -or (Get-Item $backup).Length -eq 0) {
    Say "ABORT: backup missing or empty at $backup" Red; exit 1
}
Say ("BACKUP: {0} ({1} bytes)" -f $backup, (Get-Item $backup).Length) Green

# --- Mutate (DOM edit; everything else preserved) -------------------------------------
$fbJson = [pscustomobject]@{ command = $FB_PYTHON; args = @($FB_SERVER) } | ConvertTo-Json -Depth 5
$servers['fb-messenger'] = [System.Text.Json.Nodes.JsonNode]::Parse($fbJson)

# --- Write to temp, verify, then swap ----------------------------------------------------
$opts = [System.Text.Json.JsonSerializerOptions]::new()
$opts.WriteIndented = $true
$outText = $root.ToJsonString($opts)

$tmp = "$claudeJson.new-$stamp"
Set-Content -LiteralPath $tmp -Value $outText -Encoding UTF8

$check = [System.Text.Json.Nodes.JsonNode]::Parse((Get-Content -LiteralPath $tmp -Raw -Encoding UTF8))
$projCountAfter = 0
if ($null -ne $check['projects']) { $projCountAfter = @($check['projects'].AsObject()).Count }

$okFb = $check['mcpServers']['fb-messenger']['command'].ToString() -eq $FB_PYTHON
$okPr = $projCountAfter -eq $projCountBefore

if (-not ($okFb -and $okPr)) {
    Say "ABORT (verify failed): fb-messenger=$okFb projects=$okPr ($projCountBefore -> $projCountAfter)" Red
    Say "      Original untouched. Candidate left at $tmp for inspection." Yellow
    exit 1
}

Move-Item -LiteralPath $tmp -Destination $claudeJson -Force
Say "VERIFY OK: fb-messenger registered, projects intact ($projCountAfter)." Green
Say "DONE. Restart Claude Code, then confirm fb-messenger reports connected." Green
