<#
  Install the post-commit auto-push hook into every estate repo.

  Owner instruction 2026-09-24: commits must ALWAYS be pushed. Unpushed work on
  a branch nobody revisits is work that gets lost -- which is what happened to
  the cursor/* branches.

  Idempotent. Chains any EXISTING post-commit hook rather than clobbering it.
  Never installs into a repo with no origin remote.

      pwsh -File scripts/install-autopush.ps1
      pwsh -File scripts/install-autopush.ps1 -WhatIf
      pwsh -File scripts/install-autopush.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]]$Roots = @("$env:USERPROFILE\.agents", "$env:USERPROFILE\source"),
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
# git writes to stderr on ordinary 'not found' answers; with Stop that would
# abort the whole sweep on one broken repo. Probes below use try/catch.
$PSNativeCommandUseErrorActionPreference = $false
$Src = Join-Path $PSScriptRoot 'git-hooks\post-commit-autopush'
if (-not (Test-Path $Src)) { throw "FAILED:install - hook source missing at $Src" }
$MARK = 'AUTOPUSH-HOOK-MARKER'

# discover repos
$repos = @()
foreach ($r in $Roots) {
    if (-not (Test-Path $r)) { continue }
    if (Test-Path (Join-Path $r '.git')) { $repos += (Resolve-Path $r).Path }
    $repos += Get-ChildItem $r -Directory -EA SilentlyContinue |
              Where-Object { Test-Path (Join-Path $_.FullName '.git') } |
              Select-Object -ExpandProperty FullName
}
$repos = $repos | Select-Object -Unique

$installed = 0; $skipped = @()
foreach ($repo in $repos) {
    $name = Split-Path $repo -Leaf
    $gitdir = $null
    try { $gitdir = (git -C $repo rev-parse --git-dir 2>$null | Select-Object -First 1) } catch { $gitdir = $null }
    if (-not $gitdir) { $skipped += "$name (broken or absent .git - skipped)"; continue }
    if (-not [IO.Path]::IsPathRooted($gitdir)) { $gitdir = Join-Path $repo $gitdir }
    $hookDir = Join-Path $gitdir 'hooks'
    $dest = Join-Path $hookDir 'post-commit'

    if ($Uninstall) {
        if ((Test-Path $dest) -and ((Get-Content $dest -Raw) -match $MARK)) {
            if ($PSCmdlet.ShouldProcess($name, 'remove post-commit autopush')) {
                Remove-Item $dest -Force; $installed++
            }
        }
        continue
    }

    $origin = $null
    try { $origin = (git -C $repo remote get-url origin 2>$null | Select-Object -First 1) } catch { $origin = $null }
    if (-not $origin) {
        $skipped += "$name (no origin -- nothing to push to)"
        continue
    }
    New-Item -ItemType Directory -Path $hookDir -Force -EA SilentlyContinue | Out-Null

    $body = Get-Content $Src -Raw
    if (Test-Path $dest) {
        $cur = Get-Content $dest -Raw
        if ($cur -match $MARK) { $skipped += "$name (already installed)"; continue }
        # chain: preserve whatever was there, then auto-push
        $prev = Join-Path $hookDir 'post-commit.pre-autopush'
        if ($PSCmdlet.ShouldProcess($name, 'chain existing post-commit')) {
            Copy-Item $dest $prev -Force
        }
        $body = "#!/bin/sh`n# chained: the pre-existing post-commit runs first`n" +
                "`"`$(dirname `"`$0`")/post-commit.pre-autopush`" `"`$@`" || true`n`n" + $body
    }

    if ($PSCmdlet.ShouldProcess($name, 'install post-commit autopush')) {
        # LF endings: a CRLF shebang makes the hook silently unexecutable under MSYS
        $body = $body -replace "`r`n", "`n"
        [IO.File]::WriteAllText($dest, $body, (New-Object Text.UTF8Encoding $false))
        $installed++
    }
}

Write-Host ("  repos found     : {0}" -f $repos.Count)
Write-Host ("  hooks {0}: {1}" -f $(if($Uninstall){'removed  '}else{'installed'}), $installed)
foreach ($s in $skipped) { Write-Host "  skipped         : $s" }
if ($installed -gt 0 -or $skipped.Count -gt 0) { Write-Host 'SUCCESS:install-autopush' }
else { Write-Host 'FAILED:install-autopush - nothing processed' }
