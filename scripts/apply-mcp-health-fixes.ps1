<#
================================================================================
 apply-mcp-health-fixes.ps1
================================================================================
 PURPOSE
   Apply the 2026-07-20 mcp-health findings to USER scope
   (~/.claude.json -> top-level "mcpServers"):

     1. agent-mail  : url http://127.0.0.1:8812/mcp  ->  .../mcp/
                      MEASURED: GET /mcp returns 404, GET /mcp/ returns 200.
                      The slash-less URL is why agent-mail showed [unavailable]
                      while /api/health was returning {"status":"ok"}.

     2. fb-messenger: REGISTER (was absent from Claude entirely; it existed only
                      in ~/.grok/config.toml). MEASURED: stdio handshake OK,
                      serverInfo {"name":"fb-messenger","version":"1.27.2"},
                      33 tools.

 WHY A SCRIPT AND NOT A LIVE EDIT
   A running Claude Code session holds ~/.claude.json in memory and rewrites it
   roughly every 30s, CLOBBERING any external edit made while it is open.

       >>> CLOSE ALL CLAUDE CODE SESSIONS/WINDOWS BEFORE RUNNING THIS. <<<

 SAFETY
   * Timestamped backup of ~/.claude.json BEFORE writing; aborts if the backup
     is missing or zero-length.
   * Edits ONLY the two entries above inside the top-level "mcpServers" object.
     "projects", oauth, caches and "disabledMcpServers" are left untouched.
   * Re-parses the result and asserts both entries are correct and the projects
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
$AGENT_MAIL_URL = 'http://127.0.0.1:8812/mcp/'
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

$curAgentMail = $null
if ($null -ne $servers['agent-mail'] -and $null -ne $servers['agent-mail']['url']) {
    $curAgentMail = $servers['agent-mail']['url'].ToString()
}
$hasFb = ($null -ne $servers['fb-messenger'])

Say "PLAN" Cyan
Say ("  agent-mail   : {0}  ->  {1}" -f ($curAgentMail ?? '<absent>'), $AGENT_MAIL_URL)
Say ("  fb-messenger : {0}  ->  register (stdio)" -f $(if ($hasFb) { 'present' } else { '<absent>' }))
Say ("  projects entries to preserve: {0}" -f $projCountBefore)

if ($curAgentMail -eq $AGENT_MAIL_URL -and $hasFb) {
    Say "NO-OP: both fixes already applied." Green
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
$amJson = [pscustomobject]@{ type = 'http'; url = $AGENT_MAIL_URL } | ConvertTo-Json -Depth 5
$servers['agent-mail'] = [System.Text.Json.Nodes.JsonNode]::Parse($amJson)

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

$okAm = $check['mcpServers']['agent-mail']['url'].ToString() -eq $AGENT_MAIL_URL
$okFb = $check['mcpServers']['fb-messenger']['command'].ToString() -eq $FB_PYTHON
$okPr = $projCountAfter -eq $projCountBefore

if (-not ($okAm -and $okFb -and $okPr)) {
    Say "ABORT (verify failed): agent-mail=$okAm fb-messenger=$okFb projects=$okPr ($projCountBefore -> $projCountAfter)" Red
    Say "      Original untouched. Candidate left at $tmp for inspection." Yellow
    exit 1
}

Move-Item -LiteralPath $tmp -Destination $claudeJson -Force
Say "VERIFY OK: agent-mail url fixed, fb-messenger registered, projects intact ($projCountAfter)." Green
Say "DONE. Restart Claude Code, then confirm both servers report connected." Green
