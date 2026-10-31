<#
================================================================================
 !!! DEPRECATED - DO NOT RUN - DEMOTED 2026-10-24 (SOTA sync-audit verdict) !!!
================================================================================
 VERDICT: NOT still correct post-profile-system. Dead primary AND hazardous if
 re-sourced. Retained for history only; the profile system supersedes it.

 WHY DEAD:
   * Declared source of truth ~/.mcp.json NO LONGER EXISTS -> the script
     aborts unconditionally at startup. It cannot do its job today.

 WHY HAZARDOUS IF NAIVELY RE-SOURCED (e.g. after recreating ~/.mcp.json):
   * Any full canonical set re-promoted into USER scope re-arms the offensive
     servers (hexstrike-ai, sliver, nuclei, breach-intel, osint, cve-mcp,
     frida-mcp, ghidra-mcp, ida-pro-mcp, jadx-mcp, binary-ninja-mcp,
     cheatengine, apktool-mcp, proxy-mcp) in profile-SHARED state that RAW
     unwrapped claude loads UNFILTERED. The claude profile is shielded
     (cc-cc.ps1 unconditionally passes --strict-mcp-config --mcp-config
     clean-mcp.json; claude.profile.json denies 28 incl. hexstrike-ai/sliver/
     sliver-full/nuclei/burp/cve-mcp/frida-mcp/osint) but raw sessions are not
     - the exact hexstrike-x150 / sliver-x74 refusal vector.
   * -PruneExtraUserServers would additionally strip zai-mcp-server /
     zai-lane-a / McpHub / web-search-prime, breaking glm sessions.

 SUPERSEDED BY:
   * cc-profiles control plane: cc-use / cc-glm / cc-cc (user scope = glm/raw
     default tier); clean tier derived to ~/.claude/profiles/clean-mcp.json;
     offensive servers belong ONLY to D:/opt/cyberstrike-mcp/mcp-ssot.json
     fronts and explicit --mcp-config payloads.

 Pre-existing safety machinery (DryRun default, claude-process guard,
 backup-then-atomic-replace, post-write verify) was correct and is preserved
 below UNCHANGED, byte-exact. Do not modernize; do not re-point; do not run.
================================================================================
#>

<#
================================================================================
 promote-mcp-userscope.ps1
================================================================================
 PURPOSE
   Promote the canonical MCP set (everything in ~/.mcp.json -> "mcpServers")
   into USER scope: the top-level "mcpServers" object of ~/.claude.json.
   USER scope is loaded by every NORMAL Claude Code session on EVERY drive/tree,
   so this makes the canonical set drive-independent and drift-proof (no reliance
   on per-tree .mcp.json walk-up, which can never reach C:\Users from D:\ etc.).

 WHY A SCRIPT (and not a live edit)
   A running Claude Code session holds ~/.claude.json in memory and rewrites it
   on exit, CLOBBERING any external edit made while it was open. Therefore:

       >>> CLOSE ALL CLAUDE CODE SESSIONS/WINDOWS BEFORE RUNNING THIS. <<<

 SAFETY / WHAT IT PRESERVES
   * Edits ONLY the top-level "mcpServers" key. Everything else in
     ~/.claude.json (projects, oauth, per-project disabledMcpServers curation,
     caches, etc.) is preserved byte-equivalently via a System.Text.Json DOM
     edit (case-distinct project keys are preserved; not a hashtable round-trip).
   * Takes a timestamped backup of ~/.claude.json BEFORE writing.
   * Self-verifies the result (re-parses, asserts all canonical servers present
     and the projects map is intact) and ABORTS without replacing the original
     if verification fails.
   * Does NOT touch ~/.mcp.json, the per-tree .mcp.json files, ~/.mcp.disabled.json,
     the per-project disabledMcpServers curation, or ralph's mcp-funnel setup.
   * Ralph sessions launch with --setting-sources project,local and IGNORE user
     scope, so this promotion is invisible to ralph (its project .mcp.json /
     mcp-funnel keeps working unchanged).

 USAGE
   # 1. Dry run (writes nothing, shows the plan):
   pwsh -NoProfile -File promote-mcp-userscope.ps1 -DryRun

   # 2. Apply (with Claude CLOSED):
   pwsh -NoProfile -File promote-mcp-userscope.ps1

   # Options:
   #   -DryRun                 Show the plan, write nothing.
   #   -Yes                    Skip the interactive confirmation prompt.
   #   -Force                  Proceed even if a 'claude' process is detected.
   #   -PruneExtraUserServers  Make user scope EXACTLY the canonical set, i.e.
   #                           remove any pre-existing user-scope mcpServers that
   #                           are NOT in ~/.mcp.json (e.g. a stray 'elevenlabs').
   #                           DEFAULT = OFF (non-destructive: extras are kept).

 EXIT CODES
   0 success / dry-run OK ; 1 aborted (guard, verify-fail, or user declined).
================================================================================
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$Force,
  [switch]$PruneExtraUserServers
)

$ErrorActionPreference = 'Stop'

function Say([string]$m, [string]$c='Gray') { Write-Host $m -ForegroundColor $c }

$claudeJson = Join-Path $env:USERPROFILE '.claude.json'
$canonJson  = Join-Path $env:USERPROFILE '.mcp.json'

if (-not (Test-Path $claudeJson)) { Say "ABORT: $claudeJson not found." Red; exit 1 }
if (-not (Test-Path $canonJson))  { Say "ABORT: $canonJson (canonical source of truth) not found." Red; exit 1 }

# --- Guard: refuse if Claude appears to be running (best-effort) -----------------
$running = @(Get-Process -Name 'claude' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $Force) {
  Say "ABORT: a 'claude' process is running (PID $($running.Id -join ',')). " Red
  Say "Close ALL Claude Code sessions, then re-run. (Override with -Force only if you are certain.)" Yellow
  exit 1
}
if ($running.Count -gt 0 -and $Force) { Say "WARNING: -Force set; proceeding despite a running 'claude' process." Yellow }

# --- Load canonical set (source of truth = ~/.mcp.json) -------------------------
$canonRoot = [System.Text.Json.Nodes.JsonNode]::Parse((Get-Content -Raw -LiteralPath $canonJson))
$canonObj  = $canonRoot['mcpServers']
if ($null -eq $canonObj) { Say "ABORT: ~/.mcp.json has no 'mcpServers' key." Red; exit 1 }
$canonNames = @(); foreach ($kv in $canonObj.AsObject()) { $canonNames += $kv.Key }
Say "Canonical set (~/.mcp.json): $($canonNames.Count) servers." Cyan

# --- Load ~/.claude.json as a mutable DOM (preserves case-distinct keys) ---------
$raw  = Get-Content -Raw -LiteralPath $claudeJson
$root = [System.Text.Json.Nodes.JsonNode]::Parse($raw)

$origProjCount = 0
if ($root['projects']) { $origProjCount = $root['projects'].AsObject().Count }

if ($null -eq $root['mcpServers']) { $root['mcpServers'] = [System.Text.Json.Nodes.JsonObject]::new() }
$userObj = $root['mcpServers']
$existingUserNames = @(); foreach ($kv in $userObj.AsObject()) { $existingUserNames += $kv.Key }

# --- Compute plan ----------------------------------------------------------------
$toAdd    = @($canonNames | Where-Object { $existingUserNames -notcontains $_ })
$toUpdate = @($canonNames | Where-Object { $existingUserNames -contains $_ })
$extras   = @($existingUserNames | Where-Object { $canonNames -notcontains $_ })

Say ""
Say "PLAN" White
Say "  Backup            : $claudeJson.bak-mcp-userscope-<timestamp>"
Say "  user mcpServers   : $($existingUserNames.Count) currently -> $($canonNames.Count + ($(if($PruneExtraUserServers){0}else{$extras.Count}))) after"
Say "  + Add (new)       : $($toAdd.Count)  $([string]::Join(', ', $toAdd))"
Say "  ~ Update (refresh): $($toUpdate.Count)"
if ($extras.Count -gt 0) {
  if ($PruneExtraUserServers) { Say "  - Prune extras    : $($extras.Count)  $([string]::Join(', ', $extras))  (removed: -PruneExtraUserServers)" Yellow }
  else { Say "  = Keep extras     : $($extras.Count)  $([string]::Join(', ', $extras))  (kept; use -PruneExtraUserServers to remove)" }
}
Say "  projects map      : $origProjCount entries (PRESERVED, untouched)"
Say ""

# --- Apply to the in-memory DOM (re-parse each def so it has no parent) -----------
foreach ($name in $canonNames) {
  $defJson = $canonObj[$name].ToJsonString()
  $userObj[$name] = [System.Text.Json.Nodes.JsonNode]::Parse($defJson)
}
if ($PruneExtraUserServers) {
  foreach ($name in $extras) { [void]$userObj.AsObject().Remove($name) }
}

# --- Serialize (indented, env placeholders ${VAR} kept literal) ------------------
$opts = [System.Text.Json.JsonSerializerOptions]::new()
$opts.WriteIndented = $true
$opts.Encoder = [System.Text.Encodings.Web.JavaScriptEncoder]::UnsafeRelaxedJsonEscaping
$outText = $root.ToJsonString($opts)

# --- Self-verify the candidate output BEFORE touching the original ---------------
$verify = [System.Text.Json.Nodes.JsonNode]::Parse($outText)   # throws if invalid JSON
$vNames = @(); foreach ($kv in $verify['mcpServers'].AsObject()) { $vNames += $kv.Key }
$missing = @($canonNames | Where-Object { $vNames -notcontains $_ })
$vProj = 0; if ($verify['projects']) { $vProj = $verify['projects'].AsObject().Count }
if ($missing.Count -gt 0) { Say "ABORT (verify): canonical servers missing from output: $($missing -join ', ')" Red; exit 1 }
if ($vProj -ne $origProjCount) { Say "ABORT (verify): projects count changed ($origProjCount -> $vProj). NOT writing." Red; exit 1 }
Say "VERIFY OK: all $($canonNames.Count) canonical servers present in user scope; projects map intact ($vProj entries)." Green

if ($DryRun) {
  $preview = Join-Path $env:TEMP ("claude.json.userscope-preview-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
  [System.IO.File]::WriteAllText($preview, $outText, [System.Text.UTF8Encoding]::new($false))
  Say ""
  Say "DRY RUN: no changes written to ~/.claude.json." Yellow
  Say "Full candidate written for inspection: $preview" Yellow
  exit 0
}

# --- Confirm ---------------------------------------------------------------------
if (-not $Yes) {
  Say ""
  $ans = Read-Host "Proceed to write ~/.claude.json (a backup will be taken first)? Type YES"
  if ($ans -ne 'YES') { Say "Declined. Nothing written." Yellow; exit 1 }
}

# --- Backup, then atomic-ish replace ---------------------------------------------
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$claudeJson.bak-mcp-userscope-$stamp"
Copy-Item -LiteralPath $claudeJson -Destination $backup -Force
Say "Backup written: $backup" Green

$tmp = "$claudeJson.tmp-$stamp"
[System.IO.File]::WriteAllText($tmp, $outText, [System.Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $tmp -Destination $claudeJson -Force
Say "DONE: canonical set promoted to USER scope in ~/.claude.json." Green
Say "Start a NEW Claude Code session in ANY tree (any drive) to confirm the full set loads." Cyan
exit 0
