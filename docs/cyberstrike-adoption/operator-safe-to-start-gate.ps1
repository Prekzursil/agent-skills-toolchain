# =============================================================================
# CyberStrike AGENTS.md §9 auto-load-hazard SAFE-TO-START gate  (OPERATOR REVIEW AID)
# =============================================================================
# DO NOT run this from an AI agent (Claude Code / Codex / any IDE agent). It is a
# review aid to be run by a human operator from a FRESH, trusted PowerShell 7 that
# is NOT an agent. It clones the raw CyberStrike repo with a pinned EXTERNAL empty
# hooks path (no lifecycle/hooks run), materializes a SEPARATE sanitized tree, and
# quarantines every auto-load surface. The raw --no-checkout clone must never become
# an agent CWD, and no hook/script/plugin may run. On success it prints exactly
#   SAFE-TO-START:62fdec93617581a6af97901e0f0c74293cd8d52e
# Return that receipt (and the recorded hashes) to the adoption owner before any
# install/adoption of the CyberStrike runtime proceeds. A commit other than the
# pinned one is refused by design; a version bump requires redoing the full
# auto-load/compat/dependency/hook/tool/network/security review, never reusing this.
# Source: adoption prompt §2 (verbatim). Inspect blobs as inert data only.
# =============================================================================

$ErrorActionPreference = 'Stop'
$Raw = Join-Path $env:TEMP 'CyberStrike-raw-no-checkout'
$Stage = Join-Path $env:TEMP 'CyberStrike-sanitized'
$EmptyHooks = Join-Path $env:TEMP "CyberStrike-empty-hooks-$([guid]::NewGuid().ToString('N'))"
$Archive = Join-Path $env:TEMP 'CyberStrike-review.tar'
$ExpectedCommit = '62fdec93617581a6af97901e0f0c74293cd8d52e'

foreach ($Path in @($Raw, $Stage, $Archive)) {
    if (Test-Path -LiteralPath $Path) {
        throw "Refusing to overwrite existing path: $Path"
    }
}
New-Item -ItemType Directory -Path $EmptyHooks, $Stage | Out-Null
$HookPath = $EmptyHooks.Replace('\', '/')

git -c "core.hooksPath=$HookPath" clone --depth 1 --no-checkout `
    https://github.com/CyberStrikeus/CyberStrike.git $Raw
if ($LASTEXITCODE -ne 0) { throw 'clone failed' }
git -C $Raw config --local core.hooksPath $HookPath
if ($LASTEXITCODE -ne 0) { throw 'failed to pin core.hooksPath' }

$Commit = (git -C $Raw rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Commit) { throw 'failed to resolve commit' }
if ($Commit -ne $ExpectedCommit) {
    throw "Unexpected commit $Commit; expected reviewed commit $ExpectedCommit"
}
$Tree = git -C $Raw ls-tree -r -t --name-only HEAD
if ($LASTEXITCODE -ne 0 -or -not $Tree) { throw 'failed to inventory Git tree' }
$ModeTree = git -C $Raw ls-tree -r HEAD
if ($LASTEXITCODE -ne 0 -or -not $ModeTree) { throw 'failed to inventory Git modes' }
$Gitlinks = $ModeTree | Where-Object { $_ -match '^160000 commit ' }
if ($Gitlinks) { throw 'gitlink detected; manual review and explicit rejection required' }
$Symlinks = $ModeTree | Where-Object { $_ -match '^120000 blob ' }
if ($Symlinks) {
    $Symlinks
    throw 'symlink detected; add no allowlist until every blob/target is reviewed'
}
$Tree | Where-Object {
    $_ -match '(^|/)(\.claude|\.cyberstrike|\.husky|\.codex|\.agents)(/|$)' -or
    $_ -match '(^|/)(\.mcp\.json|AGENTS\.md|CLAUDE\.md|cyberstrike\.jsonc?|package\.json)$'
}
$GrepOutput = git -C $Raw grep -n -I -E `
    'shell\.env|permission\.ask|command\.execute|tool\.execute|plugin|prepare|postinstall|hooksPath' `
    HEAD -- . ':(exclude)bun.lock'
$GrepExit = $LASTEXITCODE
if ($GrepExit -gt 1) { throw "git grep failed with exit $GrepExit" }
$GrepOutput

# Inspect a listed blob as inert text, e.g.:
git -C $Raw show 'HEAD:.claude/settings.json'
if ($LASTEXITCODE -ne 0) { throw 'failed to inspect .claude/settings.json' }
git -C $Raw show 'HEAD:.husky/pre-push'
if ($LASTEXITCODE -ne 0) { throw 'failed to inspect .husky/pre-push' }
git -C $Raw show 'HEAD:package.json'
if ($LASTEXITCODE -ne 0) { throw 'failed to inspect package.json' }

git -C $Raw archive --format=tar --output=$Archive HEAD
if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }
if (-not (Test-Path -LiteralPath $Archive) -or
    (Get-Item -LiteralPath $Archive).Length -le 0) {
    throw 'archive is absent or empty'
}
tar -xf $Archive -C $Stage
if ($LASTEXITCODE -ne 0) { throw 'tar extraction failed' }
if (-not (Get-ChildItem -LiteralPath $Stage -Force | Select-Object -First 1)) {
    throw 'sanitized materialization is empty'
}
$ReparsePoints = Get-ChildItem -LiteralPath $Stage -Force -Recurse |
    Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
if ($ReparsePoints) { throw 'reparse point remains in sanitized tree' }

$Quarantine = Join-Path $env:TEMP "CyberStrike-quarantine-$($Commit.Substring(0,12))"
New-Item -ItemType Directory -Path $Quarantine | Out-Null

# Move topmost matching directories first; preserve their relative paths.
$Names = @('.claude', '.cyberstrike', '.husky', '.codex', '.agents')
$Dirs = Get-ChildItem -LiteralPath $Stage -Directory -Force -Recurse |
    Where-Object { $_.Name -in $Names } |
    Sort-Object { $_.FullName.Length }
foreach ($Item in $Dirs) {
    if (-not (Test-Path -LiteralPath $Item.FullName)) { continue }
    $Rel = [IO.Path]::GetRelativePath($Stage, $Item.FullName)
    $Dest = Join-Path $Quarantine $Rel
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    Move-Item -LiteralPath $Item.FullName -Destination $Dest
}

$FileNames = @('.mcp.json', 'AGENTS.md', 'CLAUDE.md',
               'cyberstrike.json', 'cyberstrike.jsonc')
$Files = Get-ChildItem -LiteralPath $Stage -File -Force -Recurse |
    Where-Object { $_.Name -in $FileNames }
foreach ($Item in $Files) {
    $Rel = [IO.Path]::GetRelativePath($Stage, $Item.FullName)
    $Dest = Join-Path $Quarantine $Rel
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    Move-Item -LiteralPath $Item.FullName -Destination $Dest
}

$Remaining = Get-ChildItem -LiteralPath $Stage -Force -Recurse |
    Where-Object { $_.Name -in ($Names + $FileNames) }
if ($Remaining) { throw 'Auto-load surfaces remain in sanitized tree' }
$EffectiveHookPath = (git -C $Raw config --get core.hooksPath).Trim()
if ($LASTEXITCODE -ne 0) { throw 'failed to read effective Git hooks path' }
if ($EffectiveHookPath -ne $HookPath) {
    throw 'Unexpected effective Git hooks path'
}
"SAFE-TO-START:$Commit"
