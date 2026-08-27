#!/usr/bin/env pwsh
#requires -Version 7.0
<#
.SYNOPSIS
  codex-invoke — the ONE canonical, Windows-safe, per-call-scoped Codex invoker.

.DESCRIPTION
  Builds a Windows-safe argv ARRAY (never a shell string) for `codex exec`, materializes
  the scope EXACTLY ONCE (single-materialization rule so --print-command and the launch
  can never diverge), routes the rail (any scoping request forces the exec rail), and
  wraps the run in the explicit SUCCESS:/FAILED: error contract.

  Never hand-roll `codex exec` argv anywhere — route through this script.

  Scoping mechanisms (from <name>.scope.json.mode):
    M0  static disable (known base, no live read)         — offline
    M1  difference-disable vs live base (default)          — 1 live read
    M2a full-seal / zero-MCP (--ignore-user-config)        — offline
    M2b sealed + explicit allowlist (harvested defs)       — 1 live read
    skills allowlist -> ephemeral CODEX_HOME + materialized config.toml

.NOTES
  Verified against codex-cli 0.144.1. Fail-open on internal errors (never blocks), but
  fail-CLOSED on a scope-assertion breach (a scoping mechanism that can't prove its
  scope must not run). Windows-shell.md non-negotiables observed: PS array argv, no
  Git-Bash for -C paths, no New-Item -Force on existing files.
#>
[CmdletBinding()]
param(
  [string]   $Model,
  [string]   $Effort,
  [string]   $Profile,
  [string[]] $Mcps,
  [string[]] $Skills,
  [hashtable]$Tools,
  [string]   $Sandbox,
  [string]   $Approval,
  [string]   $OutputSchema,
  [switch]   $Seal,
  [ValidateSet('M0','M1','M2')][string] $Mode,
  [ValidateSet('auto','exec','mcp')][string] $Rail = 'auto',
  [string]   $Cwd,
  [string]   $Prompt,
  [int]      $Timeout = 0,
  [string]   $Id,
  [switch]   $PrintCommand,
  [switch]   $Doctor,
  [string]   $ProfilesDir
)

$ErrorActionPreference = 'Stop'
if (-not $Id) { $Id = "codex-{0}" -f (Get-Random -Maximum 0x7fffffff) }

function Ok([string]$msg)   { Write-Output ("SUCCESS:{0}{1}" -f $Id, ($(if($msg){" $msg"}else{""}))); exit 0 }
function Fail([string]$why) { Write-Output ("FAILED:{0} {1}" -f $Id, $why); exit 1 }
function Warn([string]$w)   { Write-Output ("WARN:{0} {1}" -f $Id, $w) }

# ---- Canonical CODEX_HOME (never a possibly-ephemeral bare CODEX_HOME) -------------
function Get-CanonicalCodexHome {
  if ($env:HARNESS_LIVE_CODEX_HOME) { return $env:HARNESS_LIVE_CODEX_HOME }
  return (Join-Path $HOME '.codex')
}
$CodexHome = Get-CanonicalCodexHome

# ---- Doctor delegation -------------------------------------------------------------
if ($Doctor) {
  $doc = Join-Path $PSScriptRoot 'codex_doctor.ps1'
  if (-not (Test-Path $doc)) { Fail "doctor-missing $doc" }
  & $doc -ProfilesDir $ProfilesDir
  exit $LASTEXITCODE
}

# ---- Profile discovery -------------------------------------------------------------
function Resolve-ProfilesDir {
  if ($ProfilesDir -and (Test-Path $ProfilesDir)) { return (Resolve-Path $ProfilesDir).Path }
  # repo default: <repo>/tools/codex/profiles  (skill lives at <repo>/skills/codex-invoke/scripts)
  $repoGuess = Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'tools/codex/profiles'
  if (Test-Path $repoGuess) { return (Resolve-Path $repoGuess).Path }
  $live = Join-Path $CodexHome 'profiles'
  if (Test-Path $live) { return (Resolve-Path $live).Path }
  return $null
}

# Minimal scalar TOML reader: `key = "value"` / `key = 123` / `key = true`.
# Sufficient for profile scalar keys; nested tables are materialized verbatim by the
# doctor/deployer, not parsed here.
function Read-ScalarToml([string]$path) {
  $h = [ordered]@{}
  if (-not (Test-Path $path)) { return $h }
  foreach ($line in (Get-Content -LiteralPath $path)) {
    $t = $line.Trim()
    if ($t -eq '' -or $t.StartsWith('#') -or $t.StartsWith('[')) { continue }
    $eq = $t.IndexOf('=')
    if ($eq -lt 1) { continue }
    $k = $t.Substring(0,$eq).Trim()
    $v = $t.Substring($eq+1).Trim()
    if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Substring(1,$v.Length-2) }
    $h[$k] = $v
  }
  return $h
}

$scalar = [ordered]@{}
$scope  = $null
if ($Profile) {
  $pdir = Resolve-ProfilesDir
  if (-not $pdir) { Fail "profiles-dir-missing (looked in -ProfilesDir, repo tools/codex/profiles, $CodexHome/profiles)" }
  $cfg = Join-Path $pdir "$Profile.config.toml"
  $scj = Join-Path $pdir "$Profile.scope.json"
  if (-not (Test-Path $cfg)) { Fail "profile-config-missing $cfg" }
  $scalar = Read-ScalarToml $cfg
  if (Test-Path $scj) {
    try { $scope = Get-Content -Raw -LiteralPath $scj | ConvertFrom-Json }
    catch { Fail "scope-json-parse $scj" }
  }
}

# Effective knobs (explicit params override profile scalars)
if (-not $Model    -and $scalar['model'])                  { $Model    = $scalar['model'] }
if (-not $Effort   -and $scalar['model_reasoning_effort']) { $Effort   = $scalar['model_reasoning_effort'] }
if (-not $Sandbox  -and $scalar['sandbox_mode'])           { $Sandbox  = $scalar['sandbox_mode'] }
if (-not $Approval -and $scalar['approval_policy'])        { $Approval = $scalar['approval_policy'] }
$scopeMode = if ($Mode) { $Mode } elseif ($scope -and $scope.mode) { $scope.mode } else { 'M1' }
$doSeal    = $Seal.IsPresent -or ($scope -and $scope.seal)
$allowlist = if ($PSBoundParameters.ContainsKey('Mcps')) { @($Mcps) } elseif ($scope -and $scope.mcp_allowlist) { @($scope.mcp_allowlist) } else { @() }
$skillList = if ($PSBoundParameters.ContainsKey('Skills')) { @($Skills) } elseif ($scope -and $scope.skills_allowlist) { @($scope.skills_allowlist) } else { @() }

$wantsScoping = $doSeal -or $allowlist.Count -gt 0 -or $skillList.Count -gt 0 -or `
                ($scope -and $scope.mode -and $scope.mode -ne 'M1') -or $Mode
$rail = $Rail
if ($rail -eq 'auto') { $rail = if ($wantsScoping) { 'exec' } else { 'exec' } }  # exec is the safe default; mcp only for trivial in-session
if ($rail -eq 'mcp' -and $wantsScoping) {
  Fail "rail-mismatch (scoping requested but rail=mcp cannot scope; use exec)"
}

# ---- Auth / quota preflight (clause 2) --------------------------------------------
# codex-cli 0.144.1: the auth probe is `codex login status` (exit 0 == "Logged in
# using ChatGPT"). `codex auth status` does NOT exist (it errors `unrecognized
# subcommand 'status'`, exit 2) — using it fail-closed EVERY authed launch.
function Test-Auth {
  try {
    $out = (& codex login status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
      # login status never reports a rate cap (you stay logged in when throttled),
      # but keep the quota signature as a defensive branch for future CLI output.
      if ($out -match '(?i)429|rate.?limit|quota|weekly|budget') { return @{ ok=$false; reason='quota' } }
      return @{ ok=$false; reason='auth' }
    }
    return @{ ok=$true; reason='' }
  } catch { return @{ ok=$false; reason='auth' } }
}

# ---- Live-base enumeration (single live read; cached) ------------------------------
$script:__baseCache = $null
function Get-LiveBase {
  if ($null -ne $script:__baseCache) { return $script:__baseCache }
  try {
    $j = (& codex mcp list --json 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { $script:__baseCache = @(); return @() }
    $parsed = $j | ConvertFrom-Json
    # tolerate either an array of {name,...} or an object map keyed by name
    $names = @()
    if ($parsed -is [System.Array]) { $names = @($parsed | ForEach-Object { $_.name }) }
    else { $names = @($parsed.PSObject.Properties.Name) }
    $script:__baseCache = @($names | Where-Object { $_ })
  } catch { $script:__baseCache = @() }
  return $script:__baseCache
}

# ---- Single-materialization: compute the -c set EXACTLY ONCE -----------------------
function Build-ConfigOverrides {
  $ov = [System.Collections.Generic.List[string]]::new()
  # scalar keys from profile (already reflected in $Model/$Effort/etc. but also pass web_search / service_tier verbatim)
  foreach ($k in 'web_search','service_tier') {
    if ($scalar[$k]) { $ov.Add("$k=" + $scalar[$k]) }
  }
  if ($Effort)   { $ov.Add("model_reasoning_effort=$Effort") }

  switch ($scopeMode) {
    'M0' {
      # M0 = STATIC disable of (base − allowlist), pre-computed OFFLINE into
      # scope.static_disable and applied here as -c overrides. It is NOT carried as
      # transport-less `mcp_servers.<n>.enabled=false` lines in <name>.config.toml:
      # codex validates each config file independently and REJECTS a standalone
      # mcp_servers entry that has no transport ("invalid transport"), so such a file
      # cannot load — whereas a `-c mcp_servers.<n>.enabled=false` override rides on
      # top of the base server (which already carries a transport) and disables it.
      # FAIL-CLOSED when the disable set is empty: an M0 profile with no static_disable
      # would silently load the FULL user base (exa, kaggle, github, …) — a scope
      # breach. A scoped profile MUST enumerate its disables (the CI config-lint pins
      # static_disable == base − allowlist); if you genuinely want the full base, do
      # not use M0.
      $sd = @(); if ($scope -and $scope.static_disable) { $sd = @($scope.static_disable) }
      if ($sd.Count -eq 0) {
        $lbl = if ($Profile) { $Profile } else { '(no profile)' }
        Fail "m0-unscoped (${lbl}: mode M0 but scope.static_disable is empty; base - allowlist is NOT enforced -> would run UNSCOPED. Populate static_disable (base minus mcp_allowlist) or choose M1)"
      }
      foreach ($n in $sd) { $ov.Add("mcp_servers.$n.enabled=false") }
    }
    'M1' {
      $base = Get-LiveBase
      $disable = @($base | Where-Object { $allowlist -notcontains $_ })
      foreach ($n in $disable) { $ov.Add("mcp_servers.$n.enabled=false") }
    }
    'M2' {
      if ($doSeal -and $allowlist.Count -eq 0) {
        # M2a full-seal handled via --ignore-user-config in argv; no enable-block.
      } elseif ($doSeal) {
        # M2b: emit explicit enable block from captured_mcp_defs (fail-closed if missing).
        if (-not ($scope -and $scope.captured_mcp_defs)) { Fail "seal-uncaptured (no captured_mcp_defs for M2b)" }
        foreach ($n in $allowlist) {
          $def = $scope.captured_mcp_defs.$n
          if (-not $def) { Fail "seal-uncaptured ($n has no captured def)" }
          if ($def.command) { $ov.Add("mcp_servers.$n.command=" + $def.command) }
          if ($def.args)    { $ov.Add("mcp_servers.$n.args=" + (($def.args | ForEach-Object { '"' + $_ + '"' }) -join ',' | ForEach-Object { "[$_]" })) }
          if ($def.env) {
            $pairs = @($def.env.PSObject.Properties | ForEach-Object { $_.Name + '="' + $_.Value + '"' })
            $ov.Add("mcp_servers.$n.env={" + ($pairs -join ',') + "}")
          }
        }
      }
    }
  }
  # feature toggles (M3) are emitted as --enable/--disable in argv, not -c.
  return ,$ov.ToArray()
}

$overrides = Build-ConfigOverrides   # computed ONCE, reused for print + launch

# ---- Assemble the Windows-safe argv ARRAY -----------------------------------------
# ($argv, not the automatic $args) built as a String[] and splatted with @($argv) so
# every element reaches codex verbatim — no shell string, no MSYS path-conversion.
$argv = [System.Collections.Generic.List[string]]::new()
$argv.Add('exec')
if ($doSeal) { $argv.Add('--ignore-user-config') }
if ($Model)  { $argv.Add('-m'); $argv.Add($Model) }
if ($Sandbox){ $argv.Add('-s'); $argv.Add($Sandbox) }
if ($Approval) { $argv.Add('-c'); $argv.Add("approval_policy=$Approval") }
foreach ($o in $overrides) { $argv.Add('-c'); $argv.Add($o) }
if ($Tools) {
  foreach ($k in $Tools.Keys) {
    if ($Tools[$k]) { $argv.Add('--enable'); $argv.Add([string]$k) } else { $argv.Add('--disable'); $argv.Add([string]$k) }
  }
}
if ($OutputSchema) { $argv.Add('--output-schema'); $argv.Add($OutputSchema) }
if ($Cwd) { $argv.Add('-C'); $argv.Add($Cwd) }   # PS array => no MSYS path-conversion
$argv.Add('--skip-git-repo-check')
$argv.Add('--json')
if ($Prompt) { $argv.Add($Prompt) }

# ---- Skills ephemeral CODEX_HOME (child-scoped, try/finally restore) --------------
$ephemeralHome = $null
if ($skillList.Count -gt 0) {
  $hash = ([BitConverter]::ToString(([System.Security.Cryptography.MD5]::Create()).ComputeHash(
            [Text.Encoding]::UTF8.GetBytes(($Profile + ($skillList -join ',') + ($allowlist -join ','))))) -replace '-','').Substring(0,10).ToLower()
  $ephemeralHome = Join-Path ([IO.Path]::GetTempPath()) "codex-scope-$hash"
  # NOTE: full staging (auth.json copy + materialized config.toml with harvested MCP defs
  # + skills/ subset) is performed by codex_doctor.ps1 at deploy time and proven by the
  # ephemeral-home scope proof. This launcher points the child at it; if unstaged it
  # fails-closed rather than silently running with zero MCPs.
  if (-not $PrintCommand -and -not (Test-Path (Join-Path $ephemeralHome 'config.toml'))) {
    Fail "ephemeral-home-unstaged $ephemeralHome (run codex_doctor.ps1 to stage+prove)"
  }
}

# ---- DRY-RUN ----------------------------------------------------------------------
$argvPreview = @('codex') + @($argv.ToArray())
if ($PrintCommand) {
  Write-Output "# rail       : $rail"
  Write-Output "# mode       : $scopeMode  seal=$doSeal"
  Write-Output "# CODEX_HOME : $(if($ephemeralHome){$ephemeralHome + ' (ephemeral, child-scoped)'}else{$CodexHome})"
  Write-Output ("# offline    : {0}" -f ($(if($scopeMode -in 'M0' -or ($scopeMode -eq 'M2' -and $doSeal -and $allowlist.Count -eq 0)){'yes'}else{'no (1 live config read for materialization)'})))
  Write-Output "# allowlist  : $($allowlist -join ', ')"
  # argv-quoted preview
  $q = ($argvPreview | ForEach-Object { if ($_ -match '[\s"\[\]${}]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ } }) -join ' '
  Write-Output $q
  Ok "print-command"
}

# ---- Launch (error contract) ------------------------------------------------------
$auth = Test-Auth
if (-not $auth.ok) { Fail $auth.reason }

if ($scopeMode -eq 'M2' -and $doSeal -and $allowlist.Count -gt 0 -and -not ($scope -and $scope.captured_mcp_defs)) {
  Fail 'seal-uncaptured'
}

$prior = $env:CODEX_HOME
try {
  if ($ephemeralHome) { $env:CODEX_HOME = $ephemeralHome }   # child-scoped only
  # Feed empty stdin (immediate EOF) — codex-cli 0.144.1 `exec` ABORTS before doing
  # any work when stdin is a piped/inherited non-terminal ("Error: stdin is not a
  # terminal") or null with redirected stdout ("Error: stdout is not a terminal").
  # Every non-interactive launch (Workflow, subagent, longrun-with-redirect — the
  # sole stated use case) is non-TTY, so WITHOUT this the real scoped run never
  # launches. `'' | & codex` gives codex a piped-but-satisfied stdin and is the same
  # proven-correct pattern the doctor's strict-config lint (check 2) already uses.
  $out = '' | & codex @($argv.ToArray()) 2>&1 | Out-String
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    if ($out -match '(?i)failed to parse config|unrecognized key|unknown field|strict-config') {
      Write-Output $out
      Fail 'config-parse (route to codex-runtime-recovery)'
    }
    if ($out -match '(?i)429|rate.?limit|quota|weekly|budget') { Fail 'quota' }
    Write-Output $out
    Fail "exit-$code"
  }
  Write-Output $out
  Ok "rail=$rail mode=$scopeMode"
}
catch { Fail ("launch-exception " + $_.Exception.Message) }
finally { $env:CODEX_HOME = $prior }   # restore even on throw
