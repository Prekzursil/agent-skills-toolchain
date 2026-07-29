#requires -version 5.1
<#
.SYNOPSIS
  Snapshot the live ~/.claude harness into this repo as a portable, templatized bundle.
  Pairs with bootstrap.ps1 (which deploys the bundle onto a fresh machine).

  Run from anywhere:  pwsh tools/workspace-config/sync-config.ps1
  What it captures:  settings(.local).json, hooks/, commands/, rules/, harness-meta/,
                     AGENTS.md, CLAUDE.md,
                     keybindings.json, statusline*.sh, the workspace docs, MEMORY + memories,
                     and the user-scope MCP servers (from ~/.claude.json) + ~/.mcp.json.
  What it does NOT capture:  .credentials.json (per-machine login), conversation history /
                     projects, *.bak*, __pycache__, node_modules, big corpora.

  NOTE ON harness-meta: this script WIPES $BundleRoot before re-populating it, so any tree
  NOT copied below is DELETED from the repo on the next run. ~/.claude/harness-meta held the
  stage-0 plan linter (plan_lint_stage0.py) with no version control at all until it was added
  here, so it must be captured or the sync would silently un-version it again. It is captured
  via an explicit FILE ALLOWLIST ($HarnessMetaFiles) rather than Copy-Tree -- see the comment
  at that variable for the measured reason. Its CI gate is ci/tests/test_plan_lint_stage0.py,
  which asserts the allowlist still names it.
  Paths to your home are rewritten to {{USER_HOME}} / {{USER}} so the bundle is machine-agnostic.
  Any value that still looks like a secret is listed in SECRETS-REVIEW.txt (review before commit).
#>
param(
    [string]$ClaudeHome = (Join-Path $env:USERPROFILE '.claude'),
    [string]$BundleRoot = (Join-Path $PSScriptRoot 'config')
)
$ErrorActionPreference = 'Stop'
$HomePath = $env:USERPROFILE
$UserName = $env:USERNAME

# --- reset bundle ---
if (Test-Path $BundleRoot) { Remove-Item -Recurse -Force $BundleRoot }
New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null

$ExcludeDir  = @('__pycache__', 'node_modules', '.pytest_cache', '.ruff_cache')
$ExcludeFile = @('*.bak', '*.bak-*', '*.pyc', '*.log')

function Copy-Tree($Name) {
    $src = Join-Path $ClaudeHome $Name
    if (-not (Test-Path $src)) { return }
    $dst = Join-Path $BundleRoot $Name
    Get-ChildItem $src -Recurse -File -Force | Where-Object {
        $full = $_.FullName; $skip = $false
        foreach ($d in $ExcludeDir)  { if ($full -like "*\$d\*") { $skip = $true } }
        foreach ($f in $ExcludeFile) { if ($_.Name -like $f)     { $skip = $true } }
        -not $skip
    } | ForEach-Object {
        $rel = $_.FullName.Substring($src.Length).TrimStart('\')
        $target = Join-Path $dst $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
        Copy-Item $_.FullName $target -Force
    }
}

function Copy-File($Name) {
    $src = Join-Path $ClaudeHome $Name
    if (Test-Path $src) { Copy-Item $src (Join-Path $BundleRoot $Name) -Force }
}

# --- core harness ---
'hooks','commands','rules' | ForEach-Object { Copy-Tree $_ }

# --- harness-meta: ALLOWLIST, not the whole tree (see the note in the header) ---
# ~/.claude/harness-meta holds 19 stdlib tools of which only the listed ones are versioned
# + CI-gated. It is an allowlist because a blind Copy-Tree of that directory would (a) sweep
# in 800 KB of logs/ runtime state and three data corpora, and (b) turn CI RED: measured
# 2026-07-29 with the pinned ruff 0.15.17, the unlisted siblings carry 14 `ruff check` errors
# and 18 of 19 files fail `ruff format --check`, and quality.yml lints the whole repo.
# To add one: fix its lint/format, write a suite, name that suite in quality.yml, THEN list it.
$HarnessMetaFiles = @('plan_lint_stage0.py')
$hmSrc = Join-Path $ClaudeHome 'harness-meta'
if (Test-Path $hmSrc) {
    $hmDst = Join-Path $BundleRoot 'harness-meta'
    New-Item -ItemType Directory -Force -Path $hmDst | Out-Null
    foreach ($name in $HarnessMetaFiles) {
        $f = Join-Path $hmSrc $name
        if (Test-Path $f) { Copy-Item $f (Join-Path $hmDst $name) -Force }
        else { "WARN: harness-meta/$name is on the sync allowlist but missing from $hmSrc" | Out-Host }
    }
}
'settings.json','settings.local.json','AGENTS.md','CLAUDE.md','keybindings.json',
'statusline-command.sh','statusline.sh','statusline-debug.sh' | ForEach-Object { Copy-File $_ }

# --- workspace docs ---
$docDst = Join-Path $BundleRoot 'docs'; New-Item -ItemType Directory -Force $docDst | Out-Null
Get-ChildItem $ClaudeHome -File -Filter *.md -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(?i)ARCHITECTURE|CALIBRATION|CURATION|CAPABILITY' } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $docDst $_.Name) -Force }

# --- memory (MEMORY.md + per-project memory notes) ---
$memSrc = Get-ChildItem (Join-Path $ClaudeHome 'projects') -Recurse -Directory -Filter 'memory' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($memSrc) {
    $memDst = Join-Path $BundleRoot 'memory'; New-Item -ItemType Directory -Force $memDst | Out-Null
    Get-ChildItem $memSrc.FullName -File -Filter *.md | ForEach-Object { Copy-Item $_.FullName (Join-Path $memDst $_.Name) -Force }
}

# --- MCP servers (user-scope) from ~/.claude.json + ~/.mcp.json (NOT projects/history) ---
$mcpDst = Join-Path $BundleRoot 'mcp'; New-Item -ItemType Directory -Force $mcpDst | Out-Null
$claudeJson = Join-Path $env:USERPROFILE '.claude.json'
if (Test-Path $claudeJson) {
    try {
        $cj = Get-Content $claudeJson -Raw | ConvertFrom-Json
        $extract = [ordered]@{}
        foreach ($k in 'mcpServers','enabledMcpjsonServers','disabledMcpjsonServers') {
            if ($cj.PSObject.Properties.Name -contains $k) { $extract[$k] = $cj.$k }
        }
        ($extract | ConvertTo-Json -Depth 12) | Set-Content (Join-Path $mcpDst 'user-claude.json') -Encoding UTF8
    } catch { "WARN: could not parse ~/.claude.json: $_" | Out-Host }
}
foreach ($f in '.mcp.json','.mcp-disabled-defaults') {
    $p = Join-Path $env:USERPROFILE $f
    if (Test-Path $p) { Copy-Item $p (Join-Path $mcpDst ($f.TrimStart('.'))) -Force }
}

# --- templatize home path + username in every text file ---
$textExt = '.json','.md','.ps1','.sh','.py','.toml','.txt','.js','.mjs',''
$variants = @(
    @{ from = $HomePath; to = '{{USER_HOME}}' },
    @{ from = ($HomePath -replace '\\','/'); to = '{{USER_HOME}}' },
    @{ from = ('/c/' + $HomePath.Substring(3) -replace '\\','/'); to = '{{USER_HOME}}' },
    @{ from = ('/mnt/c/' + $HomePath.Substring(3) -replace '\\','/'); to = '{{USER_HOME}}' },
    @{ from = $UserName; to = '{{USER}}' }
)
$secretHits = @()
Get-ChildItem $BundleRoot -Recurse -File | Where-Object { $textExt -contains $_.Extension.ToLower() } | ForEach-Object {
    $c = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $c) { return }
    foreach ($v in $variants) { $c = $c.Replace($v.from, $v.to) }
    Set-Content $_.FullName $c -NoNewline -Encoding UTF8
    # secret heuristics: long hex/base64 tokens, sk-/htk_/ghp_ prefixes, "...KEY": "value"
    foreach ($m in [regex]::Matches($c, '(?i)(sk-[A-Za-z0-9]{20,}|htk_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"[^"]*(?:api[_-]?key|token|secret|password)[^"]*"\s*:\s*"[^"{][^"]{8,}")')) {
        $secretHits += "$($_.Name): $($m.Value.Substring(0,[Math]::Min(70,$m.Value.Length)))"
    }
}

# --- manifest + secrets review ---
$counts = [ordered]@{
    hooks    = (Get-ChildItem (Join-Path $BundleRoot 'hooks') -Recurse -File -EA SilentlyContinue | Measure-Object).Count
    commands = (Get-ChildItem (Join-Path $BundleRoot 'commands') -File -EA SilentlyContinue | Measure-Object).Count
    rules    = (Get-ChildItem (Join-Path $BundleRoot 'rules') -Recurse -File -EA SilentlyContinue | Measure-Object).Count
    docs     = (Get-ChildItem $docDst -File -EA SilentlyContinue | Measure-Object).Count
    memory   = (Get-ChildItem (Join-Path $BundleRoot 'memory') -File -EA SilentlyContinue | Measure-Object).Count
}
($counts | ConvertTo-Json) | Set-Content (Join-Path $BundleRoot 'MANIFEST.json') -Encoding UTF8
if ($secretHits.Count) {
    $secretHits | Set-Content (Join-Path $PSScriptRoot 'SECRETS-REVIEW.txt') -Encoding UTF8
    Write-Host "WARNING: $($secretHits.Count) potential secret(s) found — see SECRETS-REVIEW.txt; move them to secrets.local.json before commit." -ForegroundColor Yellow
} else {
    Remove-Item (Join-Path $PSScriptRoot 'SECRETS-REVIEW.txt') -ErrorAction SilentlyContinue
    Write-Host "No raw secrets detected in the bundle." -ForegroundColor Green
}
"synced -> $BundleRoot"
$counts | Format-Table -AutoSize

