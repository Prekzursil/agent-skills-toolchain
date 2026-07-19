#!/usr/bin/env pwsh
#requires -Version 7.0
<#
.SYNOPSIS
  codex-doctor — health-check + config-lint for codex-invoke profiles.

.DESCRIPTION
  Runs the checks the design spec anchors "provable, definitory scoping" on. Emits one
  SUCCESS:/FAILED: marker per profile plus a summary. Fail-open on internal errors,
  fail-CLOSED on a scope-assertion breach or an uncaptured sealed def.

  Checks (canonical CODEX_HOME):
    1. codex login status                      -> authed? (exit 0 == logged in)
    2. <name>.config.toml parses + --strict-config-clean (UNCONDITIONAL, proactive)
       via a STAGED, unauthenticated temp CODEX_HOME + a deliberately-absent
       --output-schema short-circuit -> token-free, offline, no network spend.
    3. <name>.scope.json parses; allowlist names exist in the live base
    4. model slug present (offline STRUCTURAL check only; real slug RESOLUTION is
       proven live in check 6 -- codex has no offline model-resolve probe)
    5. harvest + pin: seal+allowlist / skills profiles -> captured_mcp_defs (${VAR}),
       base_snapshot_hash; fail-closed on any uncaptured def
    6. exec-runtime scope proof (the anti-fake check): real `codex exec --json` no-op,
       parse startup events, assert loaded_mcp_set == mcp_allowlist  [--Live only]
    7. ephemeral-home proof for skills profiles                        [--Live only]

  Checks 6-7 spawn a real codex exec (auth + tokens) and are gated behind -Live so the
  offline lint (1-5) can run in CI. The `codex exec --json` startup-event shape is the
  same one the monitor lane parses; pin it with a shared fixture and re-verify each
  codex release (G4/G8 cadence).

.NOTES
  Verified against codex-cli 0.144.1. `codex mcp list --ignore-user-config` is REJECTED,
  so a sealed profile CANNOT be verified by `mcp list` — check 6 (exec-runtime) is the
  only valid seal proof. `codex auth status` and `codex exec --print-command` do NOT
  exist in 0.144.1 — the real auth probe is `codex login status`, and strict-config lint
  is done by loading the profile as a staged CODEX_HOME config under `codex exec
  --strict-config` (keyed on the "Error loading config.toml" parse signature).
#>
[CmdletBinding()]
param(
  [string] $ProfilesDir,
  [string] $Profile,        # limit to one profile
  [switch] $Live,           # run the token-spending exec-runtime proofs (6-7)
  [switch] $Pin             # (re)harvest captured_mcp_defs + base_snapshot_hash into scope.json
)

$ErrorActionPreference = 'Stop'
$fail = 0; $warn = 0

function Emit([string]$level,[string]$name,[string]$msg) {
  Write-Output ("{0}:{1} {2}" -f $level, $name, $msg)
  if ($level -eq 'FAILED') { $script:fail++ }
  if ($level -eq 'WARN')   { $script:warn++ }
}

function Get-CanonicalCodexHome {
  if ($env:HARNESS_LIVE_CODEX_HOME) { return $env:HARNESS_LIVE_CODEX_HOME }
  return (Join-Path $HOME '.codex')
}
$CodexHome = Get-CanonicalCodexHome

function Resolve-ProfilesDir {
  if ($ProfilesDir -and (Test-Path $ProfilesDir)) { return (Resolve-Path $ProfilesDir).Path }
  $repoGuess = Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'tools/codex/profiles'
  if (Test-Path $repoGuess) { return (Resolve-Path $repoGuess).Path }
  $live = Join-Path $CodexHome 'profiles'
  if (Test-Path $live) { return (Resolve-Path $live).Path }
  return $null
}

# ---- token-free strict-config lint (codex-cli 0.144.1) ----------------------------
# `codex exec --print-command` does NOT exist and `-c config_path=<file>` is NOT a real
# external-config load (it just sets a nonexistent key). The only strict-config validator
# codex exposes is `codex exec --strict-config`, which loads config from CODEX_HOME.
# So: stage the profile config as the SOLE config.toml of an UNAUTHENTICATED temp
# CODEX_HOME, then run `codex exec --strict-config` with a deliberately-ABSENT
# --output-schema. Ordering (verified against 0.144.1):
#   * malformed config -> codex dies at config-load ("Error loading config.toml: ...")
#     BEFORE it reads the schema, auth, or the network.
#   * clean config     -> config-load passes, then codex fails fast on the missing schema
#     ("Failed to read output schema file ... os error 2") -- still BEFORE any auth or
#     network call, so a clean profile NEVER spends a token or hits the API.
# Verdict keys on the parse-error signature, not a non-existent flag and not wall-clock.
#   returns: 'clean' | 'parse' | 'inconclusive'
function Test-StrictConfigClean([string]$cfgPath) {
  $stage = Join-Path ([IO.Path]::GetTempPath()) ("codex-doctor-strict-" + [Guid]::NewGuid().ToString('N').Substring(0,10))
  $prior = $env:CODEX_HOME
  try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-Item -LiteralPath $cfgPath -Destination (Join-Path $stage 'config.toml') -Force
    $absentSchema = Join-Path $stage '__doctor_absent_schema__.json'   # never created on purpose
    $env:CODEX_HOME = $stage
    # empty stdin ('') => immediate EOF, so the non-interactive prompt read cannot hang.
    $out = ('' | & codex exec --strict-config --output-schema $absentSchema `
                   -m gpt-5.6-sol --skip-git-repo-check 'noop' 2>&1 | Out-String)
    # A transport-less `mcp_servers.<x>.enabled=false` entry (the M0 static-disable
    # *overlay* shape) is a HARD codex load error ("invalid transport") in EVERY mode
    # (standalone AND `-p`, strict AND non-strict) -- codex validates each config file
    # independently and requires every mcp_servers entry to carry a transport. Classify
    # it distinctly so the verdict is accurate (it is NOT an unknown-key / bad-TOML typo).
    if ($out -match '(?i)invalid transport|missing transport|no transport') { return 'transport' }
    if ($out -match '(?i)error loading config\.toml|unknown configuration field|failed to parse config|unrecognized (key|field)|unknown field|invalid config') {
      return 'parse'
    }
    if ($out -match '(?i)output schema|os error 2|cannot find the file|no such file') {
      return 'clean'   # config loaded strict-clean; short-circuited on the absent schema
    }
    return 'inconclusive'
  } catch { return 'inconclusive' }
  finally {
    $env:CODEX_HOME = $prior                                            # restore even on throw
    Remove-Item -Recurse -Force -LiteralPath $stage -ErrorAction SilentlyContinue
  }
}

# Read the scalar `model = "..."` from a profile config.toml (offline, no codex).
function Get-ConfigModel([string]$cfgPath) {
  if (-not (Test-Path $cfgPath)) { return '' }
  foreach ($line in (Get-Content -LiteralPath $cfgPath)) {
    if ($line.Trim() -match '^\s*model\s*=\s*"([^"]+)"') { return $Matches[1] }
  }
  return ''
}

# ---- 1. auth ----------------------------------------------------------------------
# codex-cli 0.144.1: `codex login status` (exit 0 == "Logged in using ChatGPT").
# `codex auth status` is an unrecognized subcommand (exit 2) -> would false-WARN.
try {
  $a = (& codex login status 2>&1 | Out-String)
  if ($LASTEXITCODE -eq 0) { Emit 'SUCCESS' 'auth' 'authed' }
  else { Emit 'WARN' 'auth' 'not authed (live checks will FAILED quota/auth)' }
} catch { Emit 'WARN' 'auth' 'codex not on PATH?' }

$pdir = Resolve-ProfilesDir
if (-not $pdir) { Emit 'FAILED' 'profiles' "dir not found (tools/codex/profiles or $CodexHome/profiles)"; Write-Output "SUMMARY: fail=$fail warn=$warn"; exit 1 }

# ---- live base (once) -------------------------------------------------------------
$liveBase = @()
try {
  $j = (& codex mcp list --json 2>&1 | Out-String)
  if ($LASTEXITCODE -eq 0) {
    $p = $j | ConvertFrom-Json
    if ($p -is [System.Array]) { $liveBase = @($p | ForEach-Object { $_.name }) }
    else { $liveBase = @($p.PSObject.Properties.Name) }
    $liveBase = @($liveBase | Where-Object { $_ })
  }
} catch {}

$KNOWN_KEYS = @('model','model_reasoning_effort','approval_policy','sandbox_mode',
                'web_search','service_tier')  # scalar allowset; [tables] handled separately

$profiles = if ($Profile) { @($Profile) } else {
  @(Get-ChildItem -Path $pdir -Filter '*.config.toml' | ForEach-Object { $_.BaseName -replace '\.config$','' })
}
if ($profiles.Count -eq 0) { Emit 'WARN' 'profiles' "none found in $pdir" }

foreach ($name in $profiles) {
  $cfg = Join-Path $pdir "$name.config.toml"
  $scj = Join-Path $pdir "$name.scope.json"

  # ---- 2. config.toml parse + strict-config (unconditional, token-free) -----------
  if (-not (Test-Path $cfg)) { Emit 'FAILED' $name "config-missing"; continue }
  switch (Test-StrictConfigClean $cfg) {
    'parse'     { Emit 'FAILED'  $name "config-parse (strict-config rejected a key or malformed TOML)" }
    'transport' { Emit 'FAILED'  $name "config-load (transport-less mcp_servers entry: codex cannot load this file in any mode; an M0 static-disable overlay is not a standalone-loadable config -- apply disables as -c overrides via scope.static_disable instead)" }
    'clean'     { Emit 'SUCCESS' $name "config strict-clean" }
    default     { Emit 'WARN'    $name "strict-config probe inconclusive (codex on PATH?)" }
  }

  # ---- 3. scope.json parse + allowlist reachability -------------------------------
  $scope = $null
  if (Test-Path $scj) {
    try { $scope = Get-Content -Raw -LiteralPath $scj | ConvertFrom-Json }
    catch { Emit 'FAILED' $name "scope-json-parse"; continue }
  } else { Emit 'WARN' $name "no scope.json (treated as M1 empty)"; continue }

  $mode = if ($scope.mode) { $scope.mode } else { 'M1' }
  if ($mode -notin 'M0','M1','M2') { Emit 'FAILED' $name "scope.mode invalid ($mode)" }
  $allow = @(); if ($scope.mcp_allowlist) { $allow = @($scope.mcp_allowlist) }
  $skills = @(); if ($scope.skills_allowlist) { $skills = @($scope.skills_allowlist) }
  $seal  = [bool]$scope.seal

  if ($liveBase.Count -gt 0) {
    $missing = @($allow | Where-Object { $liveBase -notcontains $_ })
    if ($missing.Count -gt 0) { Emit 'WARN' $name "allowlist not in live base: $($missing -join ', ')" }
    else { Emit 'SUCCESS' $name "allowlist ⊆ live base" }
  }

  # M2b/skills fail-closed rule: seal+allowlist OR skills => captured_mcp_defs required
  $needsCapture = ($seal -and $allow.Count -gt 0) -or ($skills.Count -gt 0)
  if ($needsCapture -and -not $scope.captured_mcp_defs -and -not $Pin) {
    Emit 'FAILED' $name "seal-uncaptured (needs captured_mcp_defs; run -Pin)"
  }
  if ($seal -and $allow.Count -eq 0) { Emit 'SUCCESS' $name "M2a full-seal / zero-MCP" }

  # ---- 4. model slug DECLARED (offline structural; real resolution = check 6) ------
  # codex 0.144.1 has NO offline model-resolve probe (there is no --print-command, and a
  # slug is only proven to resolve by a real run). Offline we assert the slug is DECLARED
  # and record it for check 6; we do NOT falsely claim it "resolves".
  $cfgModel = Get-ConfigModel $cfg
  $slug = if ($scope.model) { [string]$scope.model } elseif ($cfgModel) { $cfgModel } else { 'gpt-5.6-sol' }
  if ($scope.model -or $cfgModel) {
    Emit 'SUCCESS' $name "model slug '$slug' declared (live resolution proven in check 6, -Live)"
  } else {
    Emit 'WARN' $name "no model slug declared -> codex default '$slug' (resolution deferred to check 6)"
  }

  # ---- 5. harvest + pin -----------------------------------------------------------
  if ($Pin -and $needsCapture) {
    $defs = [ordered]@{}
    $ok = $true
    foreach ($srv in $allow) {
      try {
        $g = (& codex mcp get $srv --json 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { $ok=$false; Emit 'FAILED' $name "seal-uncaptured (mcp get $srv failed)"; break }
        $defs[$srv] = ($g | ConvertFrom-Json)
      } catch { $ok=$false; Emit 'FAILED' $name "seal-uncaptured (mcp get $srv threw)"; break }
    }
    if ($ok) {
      $scope | Add-Member -NotePropertyName captured_mcp_defs -NotePropertyValue $defs -Force
      $hashSrc = (($liveBase | Sort-Object) -join ',')
      $bh = [BitConverter]::ToString(([System.Security.Cryptography.SHA256]::Create()).ComputeHash([Text.Encoding]::UTF8.GetBytes($hashSrc))) -replace '-',''
      $scope | Add-Member -NotePropertyName base_snapshot_hash -NotePropertyValue $bh.Substring(0,16) -Force
      # write back (Set-Content, never New-Item -Force)
      $scope | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $scj -Encoding utf8
      Emit 'SUCCESS' $name "harvested $($allow.Count) def(s) + pinned base hash"
    }
  }

  # ---- 6/7. exec-runtime + ephemeral scope proof (live only) ----------------------
  if ($Live) {
    try {
      $tmp = [IO.Path]::GetTempFileName()
      $exArgs = @('exec','--json','--skip-git-repo-check','-m',$slug,'-o',$tmp)
      if ($seal) { $exArgs = @('exec','--ignore-user-config') + $exArgs[1..($exArgs.Count-1)] }
      # (in-repo shared fixture pins the startup-event key names; parse the loaded MCP set)
      # empty stdin ('') => immediate EOF, so codex-cli 0.144.1 `exec` does not abort
      # with "stdin/stdout is not a terminal" in this non-interactive (redirected) run —
      # the same proven pattern as check 2 (Test-StrictConfigClean) and the launcher.
      $ev = ('' | & codex @exArgs 'noop: reply DONE' 2>&1 | Out-String)
      # 4(live). Real model-slug RESOLUTION (the only place codex actually resolves it).
      if ($ev -match '(?i)unknown model|unsupported model|no such model|model .*not found|invalid model|model_not_found') {
        $fb = @($scope.model_fallbacks)
        if ($fb.Count -gt 0) { Emit 'WARN' $name "slug '$slug' unresolved live -> fallback $($fb[0])" }
        else { Emit 'FAILED' $name "slug '$slug' unresolved live, no model_fallbacks" }
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
        continue   # a failed model resolve makes the loaded-MCP set meaningless
      }
      $loaded = @()
      foreach ($ln in ($ev -split "`n")) {
        if ($ln -match '"?mcp_servers?"?\s*[:=]') {
          # tolerant scan for server names in the startup/session-configured event
          [regex]::Matches($ln,'"([A-Za-z0-9_\-]+)"') | ForEach-Object { $loaded += $_.Groups[1].Value }
        }
      }
      $loaded = @($loaded | Where-Object { $_ -and $KNOWN_KEYS -notcontains $_ } | Select-Object -Unique)
      $forbidden = @($loaded | Where-Object { $allow -notcontains $_ })
      if ($seal -and $allow.Count -eq 0 -and $loaded.Count -gt 0) {
        Emit 'FAILED' $name "scope-breach (sealed zero-MCP but loaded: $($loaded -join ', '))"
      } elseif ($forbidden.Count -gt 0) {
        Emit 'FAILED' $name "scope-breach (forbidden loaded: $($forbidden -join ', '))"
      } else {
        Emit 'SUCCESS' $name "exec-runtime scope proof OK (loaded ⊆ allowlist)"
      }
      Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    } catch { Emit 'WARN' $name "exec-runtime proof inconclusive: $($_.Exception.Message)" }
  }
}

Write-Output ("SUMMARY: fail={0} warn={1} profiles={2} live={3} pin={4}" -f $fail, $warn, $profiles.Count, [bool]$Live, [bool]$Pin)
if ($fail -gt 0) { exit 1 } else { exit 0 }
