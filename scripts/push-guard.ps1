<#
  push-guard - surface work that was done but never landed.

  The failure this exists for, in the owner's words: committed work "never
  get[s] to reddit, and just ... get[s] lost since nobody is actually
  remembering or checking if commited stuff is ever pushed and not abandoned".

  Mechanical root cause found 2026-09-23: git had no author identity on this
  machine, so every commit failed silently and work sat staged forever. This
  checks the whole chain, not just the last link:

      uncommitted -> committed-but-unpushed -> pushed-but-stale-branch

  Read-only. Never commits, never pushes, never force-anything. Exits non-zero
  only with -FailOnFindings, so it is safe to wire into a Stop hook.

  Usage:
      pwsh -File scripts/push-guard.ps1
      pwsh -File scripts/push-guard.ps1 -Roots C:\a,C:\b -FailOnFindings
#>
[CmdletBinding()]
param(
    [string[]]$Roots = @("$env:USERPROFILE\.agents", "$env:USERPROFILE\source"),
    [int]$StaleDays = 14,
    [switch]$FailOnFindings
)

$ErrorActionPreference = 'Continue'
$findings = @()

function Add-Finding($Repo, $Kind, $Detail) {
    $script:findings += [pscustomobject]@{ Repo = $Repo; Kind = $Kind; Detail = $Detail }
}

$repos = @()
foreach ($r in $Roots) {
    if (-not (Test-Path $r)) { continue }
    if (Test-Path (Join-Path $r '.git')) { $repos += $r; continue }
    $repos += Get-ChildItem $r -Directory -EA SilentlyContinue |
              Where-Object { Test-Path (Join-Path $_.FullName '.git') } |
              Select-Object -ExpandProperty FullName
}

foreach ($repo in $repos) {
    $name = Split-Path $repo -Leaf

    # 0. identity - the silent killer. No identity => every commit fails.
    $who = (git -C $repo config user.email 2>$null)
    if (-not $who) { Add-Finding $name 'no-identity' 'git user.email unset; commits fail silently' }

    # 1. uncommitted work
    $dirty = @(git -C $repo status --porcelain 2>$null)
    if ($dirty.Count -gt 0) {
        $tracked = @($dirty | Where-Object { $_ -notmatch '^\?\?' }).Count
        $untracked = @($dirty | Where-Object { $_ -match '^\?\?' }).Count
        Add-Finding $name 'uncommitted' "$tracked modified/deleted, $untracked untracked"
    }

    # 2. committed but never pushed - the abandonment case
    $branch = (git -C $repo rev-parse --abbrev-ref HEAD 2>$null)
    if ($branch -and $branch -ne 'HEAD') {
        $upstream = (git -C $repo rev-parse --abbrev-ref "$branch@{upstream}" 2>$null)
        if (-not $upstream) {
            Add-Finding $name 'no-upstream' "branch '$branch' tracks nothing; pushes go nowhere"
        } else {
            # ls-remote, not the cached remote ref: a fetch writes only FETCH_HEAD,
            # so origin/<branch> can be stale and report a false 'in sync'.
            $remoteSha = (git -C $repo ls-remote origin $branch 2>$null) -split "`t" | Select-Object -First 1
            $localSha  = (git -C $repo rev-parse HEAD 2>$null)
            if ($remoteSha -and $localSha -and $remoteSha -ne $localSha) {
                $ahead = (git -C $repo rev-list --count "$remoteSha..$localSha" 2>$null)
                if ($ahead -and [int]$ahead -gt 0) {
                    Add-Finding $name 'unpushed' "$ahead commit(s) on '$branch' not on the remote"
                }
            }
        }
    }

    # 3. stale local branches holding work nobody merged
    $stale = git -C $repo for-each-ref --format='%(refname:short)|%(committerdate:unix)' refs/heads 2>$null |
        ForEach-Object {
            $p = $_ -split '\|'
            if ($p.Count -eq 2 -and $p[1]) {
                $age = [int](([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [int]$p[1]) / 86400)
                if ($age -gt $StaleDays -and $p[0] -ne $branch) { "$($p[0]) ($age d)" }
            }
        }
    if ($stale) { Add-Finding $name 'stale-branch' (($stale | Select-Object -First 5) -join ', ') }
}

if ($findings.Count -eq 0) {
    Write-Host "SUCCESS:push-guard - $($repos.Count) repo(s) checked, nothing stranded"
    exit 0
}

Write-Host "push-guard: $($findings.Count) finding(s) across $($repos.Count) repo(s)"
$findings | Group-Object Repo | ForEach-Object {
    Write-Host "  $($_.Name)"
    $_.Group | ForEach-Object { Write-Host ("    {0,-13} {1}" -f $_.Kind, $_.Detail) }
}
if ($FailOnFindings) { Write-Host 'FAILED:push-guard'; exit 1 }
Write-Host 'SUCCESS:push-guard (advisory; nothing blocked)'
exit 0
