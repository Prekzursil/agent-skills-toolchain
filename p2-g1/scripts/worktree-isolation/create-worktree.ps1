# Claude Code WorktreeCreate hook.
# stdin: JSON { cwd, worktree_config: { base_directory, worktree_name, source_ref } }
# stdout (on exit 0): absolute path of the created worktree. Non-zero exit aborts creation.
# EAP=Continue so git's normal stderr progress ("Preparing worktree ...") isn't thrown as an
# error; success is judged by $LASTEXITCODE. The tool CWD here is ~/.agents/harness (not a repo)
# and the session isn't rooted in one repo, so we resolve the target repo from, in order:
# a hint file -> worktree_config.base_directory -> $env:CLAUDE_PROJECT_DIR -> cwd (first git repo).
$ErrorActionPreference = "Continue"
function Test-GitRepo($d) {
    if (-not $d) { return $false }
    & git -C $d rev-parse --is-inside-work-tree *> $null
    return ($LASTEXITCODE -eq 0)
}
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $wc = $in.worktree_config

    $cands = @()
    $targetFile = Join-Path $HOME ".claude\hooks\worktree-target.txt"
    if (Test-Path $targetFile) {
        $t = (Get-Content $targetFile -Raw).Trim()
        if ($t) { $cands += $t }
    }
    if ($wc -and $wc.base_directory) { $cands += $wc.base_directory }
    if ($env:CLAUDE_PROJECT_DIR) { $cands += $env:CLAUDE_PROJECT_DIR }
    if ($in.cwd) { $cands += $in.cwd }

    $base = $null
    foreach ($c in $cands) { if (Test-GitRepo $c) { $base = $c; break } }
    if (-not $base) { [Console]::Error.WriteLine("no git repo among candidates: $($cands -join ' | ')"); exit 1 }
    $base = $base -replace '/', '\'

    $name = if ($wc -and $wc.worktree_name) { $wc.worktree_name } else { "agent-$(Get-Random)" }
    $name = ($name -replace '[^A-Za-z0-9._-]', '-')

    # TST-0204-F1 fix (hard cap, not a convention): one named maximum for the
    # worktree_name component so a generated root can never consume the host's
    # path budget. Over-cap names are truncated deterministically to the cap
    # minus a 12-hex-char SHA-256 suffix of the FULL sanitized name - same
    # input yields the same root, distinct long names stay distinct. The cap
    # and the guard sit BEFORE `git worktree add`, so no over-cap path is ever
    # created.
    $WorktreeNameMaxChars = 48
    if ($name.Length -gt $WorktreeNameMaxChars) {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $hashHex = ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($name)))).Replace('-', '').ToLowerInvariant()
        $name = $name.Substring(0, $WorktreeNameMaxChars - 13) + '-' + $hashHex.Substring(0, 12)
    }

    $ref = if ($wc) { $wc.source_ref } else { $null }
    if (-not $ref -or $ref -eq 'fresh') { $ref = 'HEAD' }

    $dest = Join-Path (Join-Path $HOME ".claude\agent-worktrees") $name
    $parent = Split-Path $dest
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force *> $null }
    if (Test-Path $dest) {
        & git -C $base worktree remove --force $dest 2>&1 | Out-Null
        & git -C $base worktree prune 2>&1 | Out-Null
    }

    # --detach so it never collides with a branch already checked out in the main worktree.
    $out = & git -C $base worktree add --detach $dest $ref 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("git worktree add failed: $out"); exit 1 }

    Write-Output $dest
    exit 0
}
catch {
    [Console]::Error.WriteLine("WorktreeCreate hook error: $_")
    exit 1
}
