# Claude Code WorktreeRemove hook.
# stdin: JSON { cwd, worktree_path }
# Non-blocking: always exit 0 (failures are logged, never abort the agent lifecycle).
$ErrorActionPreference = "Continue"
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $wt = $in.worktree_path
    if (-not $wt) { exit 0 }
    $wt = $wt -replace '/', '\'
    if (-not (Test-Path $wt)) { exit 0 }

    # Find the MAIN repo via the worktree's git-common-dir (a worktree's .git is a
    # file pointing back to the main repo, so we can't just walk up for a .git dir).
    $common = & git -C $wt rev-parse --git-common-dir 2>$null
    if ($LASTEXITCODE -eq 0 -and $common) {
        $common = $common -replace '/', '\'
        if (-not [System.IO.Path]::IsPathRooted($common)) { $common = Join-Path $wt $common }
        $main = Split-Path $common   # <main>\.git -> <main>
        if ($main -and (Test-Path $main)) {
            & git -C $main worktree remove --force $wt 2>&1 | Out-Null
            & git -C $main worktree prune 2>&1 | Out-Null
        }
    }
    exit 0
}
catch {
    exit 0
}
