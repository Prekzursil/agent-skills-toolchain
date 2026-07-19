<#
.SYNOPSIS
  Read-only survey of every local git repository: branch, ahead/behind, dirty count,
  upstream, ownership class, and a recommended action per repo.

.DESCRIPTION
  The companion to hooks/git-hygiene/check.py. The hook is the cheap session-end nudge that
  names only what is at risk; this is the on-demand full picture you run when you want to
  clean up.

  WHY OWNERSHIP CLASSIFICATION IS THE WHOLE JOB. Measured on this box 2026-07-18:

      329 git repositories discovered     175 dirty     111 with no upstream

  and almost none of that is yours to fix:

      258  third-party clones under ~/.claude/plugins/**      the CLI plugin cache
       20  detached-HEAD scratch worktrees, ~/.claude/agent-worktrees/*   all 0 dirty
        8  no-remote temp_subdir_*.clone husks in that same cache
      ~37  dirty files across insta-mcp, hexstrike-ai, mcp_agent_mail, whatsapp-mcp, ...

  An unclassified listing of 175 dirty repos is unreadable and gets ignored, so every row
  here carries a Class and only YOURS / NO-REMOTE rows carry an Action.

  CLASSES
    YOURS      origin owner matches -Owner. Your work; act on it.
    NO-REMOTE  a real repo with no remote at all. Highest risk: the work exists on this
               disk and nowhere else. 4 measured (fb-messenger-mcp, openmm-md-mcp,
               schrodinger-mcp, tiktok-mcp) plus ~/Documents/Misc, an empty git init.
    VENDORED   someone else s clone: foreign origin, or nested inside another repo, or
               living in a plugin/dependency cache. Dirt here is EXPECTED. Never actioned.
    EPHEMERAL  agent scratch worktree, reclaimed automatically. Never actioned.

  ORDER IS LOAD-BEARING: position beats provenance. A clone nested inside your repo, or
  sitting in the plugin cache, is VENDORED no matter what its origin says. The 8 husks
  above have no remote at all, so grading them on provenance first would file them under
  NO-REMOTE and let them dominate the report.

.SAFETY
  STRICTLY READ-ONLY. It runs only: status, config, rev-parse, branch. It never pushes,
  commits, stages, resets, checks out, or deletes anything, and it never writes a file.
  That guarantee is enforced by two independent tests in test_repo_sweep.py: a behavioural
  one that hashes the whole tree plus every HEAD before and after and asserts nothing moved,
  and a static one that rejects any mutating verb in command position.

.PARAMETER Roots
  Directories to scan. Default: ~/source, ~/Documents/GitHub, ~/Documents, ~/.local/opt,
  ~/.claude/agent-worktrees.
  THE ROOT LIST IS LOAD-BEARING. While building this, a first scan reported that the repo
  ~/Documents/Misc did not exist; it does. The scan root list simply did not include
  ~/Documents. A known-positive control caught it. Widen -Roots rather than trusting a
  quiet result.

.PARAMETER Owner
  GitHub owner treated as YOURS. Default: Prekzursil.

.PARAMETER All
  Also list VENDORED and EPHEMERAL rows. Off by default: that is 278 of the 329.

.PARAMETER Json
  Emit the full survey as JSON, every class included, for scripting.

.EXAMPLE
  pwsh -File scripts/repo-sweep.ps1
  pwsh -File scripts/repo-sweep.ps1 -All
  pwsh -File scripts/repo-sweep.ps1 -Json | ConvertFrom-Json
#>
[CmdletBinding()]
param(
    [string[]]$Roots,
    [string]$Owner = 'Prekzursil',
    [int]$MaxDepth = 2,
    [switch]$All,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$UserProfile = [Environment]::GetFolderPath('UserProfile')
if (-not $Roots -or $Roots.Count -eq 0) {
    $Roots = @(
        (Join-Path $UserProfile 'source'),
        (Join-Path $UserProfile 'Documents\GitHub'),
        (Join-Path $UserProfile 'Documents'),
        (Join-Path $UserProfile '.local\opt'),
        (Join-Path $UserProfile '.claude\agent-worktrees')
    )
}

$ExcludeDirs = @('.git', 'node_modules', '__pycache__', '.venv', 'venv', 'site-packages',
                 '.pytest_cache', '.mypy_cache', '.ruff_cache', '.tox', 'dist', 'build',
                 '.next', 'target', '.gradle')
# Classification markers, matched against the lowercased forward-slashed path.
$VendorMarkers    = @('/.claude/plugins/', '/.local/opt/', '/node_modules/',
                      '/site-packages/', '/vendor/', '/third_party/')
$EphemeralMarkers = @('/.claude/agent-worktrees/', '/.claude/worktrees/')
# Walk pruning is a COST control and is kept separate from the classification markers:
# pruning a path also makes its nested repos undiscoverable, so only the 258-repo plugin
# cache earns a prune.
$PruneMarkers     = @('/.claude/plugins/')

function Test-Marker {
    param([string]$Path, [string[]]$Markers)
    $n = ($Path -replace '\\', '/').ToLowerInvariant()
    foreach ($m in $Markers) { if ($n.Contains($m.ToLowerInvariant())) { return $true } }
    return $false
}

# NOTE: origin-owner parsing and per-repo git state live INSIDE the parallel block below
# (Get-Owner2 / inline status parse). Runspaces created by ForEach-Object -Parallel do not
# inherit script-scope functions, so those are defined there rather than here. Keeping a
# second serial copy at script scope would be dead code and an inevitable drift hazard.

function Find-GitRepo {
    # $Cap is threaded in explicitly (rather than closing over the script-scope $MaxDepth)
    # so the depth bound is a real parameter reference, not an implicit capture.
    param([string]$Base, [int]$Depth, [int]$Cap, [string]$Enclosing,
          [System.Collections.ArrayList]$Acc)
    if ($Depth -gt $Cap) { return }
    $here = $Enclosing
    if (Test-Path -LiteralPath (Join-Path $Base '.git')) {
        [void]$Acc.Add([pscustomobject]@{ Path = $Base; NestedIn = $Enclosing })
        $here = $Base
    }
    $kids = @(Get-ChildItem -LiteralPath $Base -Force -Directory -ErrorAction SilentlyContinue)
    foreach ($k in $kids) {
        if ($ExcludeDirs -contains $k.Name) { continue }
        if (Test-Marker -Path $k.FullName -Markers $PruneMarkers) { continue }
        Find-GitRepo -Base $k.FullName -Depth ($Depth + 1) -Cap $Cap -Enclosing $here -Acc $Acc
    }
}

# --- discover ---------------------------------------------------------------------------
$found = [System.Collections.ArrayList]::new()
foreach ($root in $Roots) {
    if (Test-Path -LiteralPath $root) {
        Find-GitRepo -Base (Resolve-Path -LiteralPath $root).Path -Depth 0 -Cap $MaxDepth `
            -Enclosing '' -Acc $found
    }
}

# De-duplicate discovery (a repo reachable from two roots appears once).
$seen = @{}
$unique = foreach ($f in $found) {
    $key = ($f.Path -replace '\\', '/').ToLowerInvariant()
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    $f
}

# Per-repo state + classification, RUN IN PARALLEL. Each repo costs two git subprocesses
# (~1.25 s of pure Windows spawn wait), so serial over ~106 repos measured 133 s -- a human
# Ctrl-Cs that. ForEach-Object -Parallel -ThrottleLimit 8 turns it into ~7 s. The reads are
# read-only, so parallel execution is safe. Runspaces do NOT inherit script functions, so
# the two helpers are reconstructed inside the block from $using: sources; the classify
# ORDER (position beats provenance) is duplicated here verbatim and pinned by the tests.
$rows = @($unique | ForEach-Object -ThrottleLimit 8 -Parallel {
    $repoPath   = $_.Path
    $nestedIn   = $_.NestedIn
    $owner      = $using:Owner
    $vmarkers   = $using:VendorMarkers
    $emarkers   = $using:EphemeralMarkers

    function Test-Marker2([string]$Path, [string[]]$Markers) {
        $n = ($Path -replace '\\', '/').ToLowerInvariant()
        foreach ($m in $Markers) { if ($n.Contains($m.ToLowerInvariant())) { return $true } }
        return $false
    }
    function Get-Owner2([string]$Origin) {
        if ([string]::IsNullOrWhiteSpace($Origin)) { return '' }
        $s = $Origin.Trim().TrimEnd('/')
        if ($s.EndsWith('.git')) { $s = $s.Substring(0, $s.Length - 4) }
        if ($s.Contains('://')) { $s = $s.Substring($s.IndexOf('://') + 3) }
        $head = $s.Split('/')[0]
        if ($head.Contains('@')) { $s = $s.Substring($s.IndexOf('@') + 1) }
        $s = $s.Replace(':', '/')
        $parts = @($s.Split('/') | Where-Object { $_ })
        if ($parts.Count -ge 2) { return $parts[$parts.Count - 2] }
        return ''
    }

    $branch = ''; $upstream = ''; $ahead = 0; $behind = 0; $dirty = 0; $unborn = $false
    $out = @(& git -C $repoPath status --porcelain=v2 --branch 2>$null)
    foreach ($line in $out) {
        if (-not $line) { continue }
        if ($line[0] -ne '#') { $dirty++; continue }
        $p = @($line -split '\s+')
        if ($p.Count -lt 3) { continue }
        switch ($p[1]) {
            'branch.oid'      { if ($p[2] -eq '(initial)') { $unborn = $true } }
            'branch.head'     { if ($p[2] -ne '(detached)') { $branch = $p[2] } }
            'branch.upstream' { $upstream = $p[2] }
            'branch.ab' {
                if ($p.Count -ge 4) {
                    $ahead  = [int]($p[2].TrimStart('+'))
                    $behind = [int]($p[3].TrimStart('-'))
                }
            }
        }
    }
    $remotes = @(& git -C $repoPath config --get-regexp '^remote\..*\.url' 2>$null)
    $origin = ''
    foreach ($line in $remotes) {
        if ($line -and $line.StartsWith('remote.origin.url ')) {
            $origin = $line.Substring('remote.origin.url '.Length).Trim()
        }
    }
    $hasRemote = ($remotes.Count -gt 0)
    $originOwner = Get-Owner2 $origin

    # ORDER IS LOAD-BEARING -- position beats provenance. See the header.
    $class = ''
    if (Test-Marker2 $repoPath $emarkers)          { $class = 'EPHEMERAL' }
    elseif ($nestedIn)                             { $class = 'VENDORED' }
    elseif (Test-Marker2 $repoPath $vmarkers)      { $class = 'VENDORED' }
    elseif ($hasRemote -and ($originOwner -ine $owner)) { $class = 'VENDORED' }
    elseif (-not $hasRemote)                       { $class = 'NO-REMOTE' }
    else                                           { $class = 'YOURS' }

    $detached = [string]::IsNullOrEmpty($branch)
    $action = '-'
    if ($class -eq 'NO-REMOTE') {
        if ($dirty -gt 0 -or -not $unborn) {
            $action = 'no remote anywhere: gh repo create --source . --private --push'
        }
    } elseif ($class -eq 'YOURS') {
        if ($dirty -gt 0 -and -not $upstream) {
            $action = 'commit, then: git push -u origin HEAD'
        } elseif ($ahead -gt 0) {
            $action = 'git push'
        } elseif ($dirty -gt 0) {
            $action = 'commit or stash'
        } elseif (-not $upstream -and -not $unborn -and -not $detached) {
            $action = 'branch never pushed: git push -u origin HEAD'
        }
    }

    [pscustomobject]@{
        Name      = Split-Path $repoPath -Leaf
        Path      = $repoPath
        Class     = $class
        Branch    = if ($detached) { '(detached)' } else { $branch }
        Upstream  = $upstream
        Ahead     = $ahead
        Behind    = $behind
        Dirty     = $dirty
        HasRemote = $hasRemote
        Origin    = $origin
        NestedIn  = $nestedIn
        Action    = $action
    }
})

# --- emit -------------------------------------------------------------------------------
if ($Json) {
    if ($rows.Count -eq 0) { '' } else { $rows | ConvertTo-Json -Depth 4 -AsArray }
    return
}

$byClass = @{}
foreach ($r in $rows) {
    if (-not $byClass.ContainsKey($r.Class)) { $byClass[$r.Class] = 0 }
    $byClass[$r.Class]++
}

Write-Output ''
Write-Output '=== repo-sweep (READ-ONLY: nothing is pushed, committed, or deleted) ==='
Write-Output ''

$shown = if ($All) { $rows } else { $rows | Where-Object { $_.Action -ne '-' } }
$shown = @($shown | Sort-Object @{ Expression = {
    switch ($_.Class) { 'NO-REMOTE' { 0 } 'YOURS' { 1 } 'VENDORED' { 2 } default { 3 } } } },
    @{ Expression = 'Dirty'; Descending = $true })

if ($shown.Count -eq 0) {
    Write-Output '  Nothing needs action.'
    Write-Output '  Trust that ONLY if the counts below are non-zero -- a zero total means the'
    Write-Output '  scan found no repositories at all, which is a broken scan, not a clean box.'
} else {
    $shown | Format-Table -AutoSize -Property Name, Class, Branch, Ahead, Behind, Dirty, Action |
        Out-String -Width 200 | Write-Output
}

$parts = @()
foreach ($c in @('YOURS', 'NO-REMOTE', 'VENDORED', 'EPHEMERAL')) {
    $n = if ($byClass.ContainsKey($c)) { $byClass[$c] } else { 0 }
    $parts += ('{0} {1}' -f $c, $n)
}
Write-Output ('  scanned {0} repo(s) across {1} root(s):  {2}' -f
    $rows.Count, $Roots.Count, ($parts -join '  |  '))
if (-not $All) {
    $hidden = $rows.Count - $shown.Count
    Write-Output ('  {0} row(s) need no action from you and are not listed. Pass -All to see them.' -f $hidden)
}
Write-Output '  VENDORED and EPHEMERAL rows are never actioned: dirt in a third-party clone or'
Write-Output '  an agent scratch worktree is the expected steady state, not a problem.'
Write-Output ''
