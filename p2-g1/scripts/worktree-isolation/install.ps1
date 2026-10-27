# Installs the worktree-isolation hooks into ~/.claude.
#   install.ps1                 -> copy scripts to ~/.claude/hooks + print the settings snippet
#   install.ps1 -PatchSettings  -> also merge WorktreeCreate/WorktreeRemove into ~/.claude/settings.json
# Idempotent. Backs up settings.json before patching. NOTE: -PatchSettings round-trips the JSON
# (re-indents the whole file); on a carefully hand-formatted settings.json prefer the manual snippet.
param([switch]$PatchSettings)
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$hooksDir = Join-Path $HOME ".claude\hooks"
if (-not (Test-Path $hooksDir)) { New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null }
Copy-Item "$src\create-worktree.ps1" "$hooksDir\create-worktree.ps1" -Force
Copy-Item "$src\remove-worktree.ps1" "$hooksDir\remove-worktree.ps1" -Force
Write-Output "[ok] copied create/remove-worktree.ps1 -> $hooksDir"

$snippetPath = "$src\settings-hooks-snippet.json"
if ($PatchSettings) {
    $settingsPath = Join-Path $HOME ".claude\settings.json"
    if (-not (Test-Path $settingsPath)) { throw "settings.json not found at $settingsPath" }
    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    Copy-Item $settingsPath "$settingsPath.bak-worktree-$stamp" -Force
    Write-Output "[ok] backed up settings.json -> settings.json.bak-worktree-$stamp"
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    $snippet = Get-Content $snippetPath -Raw | ConvertFrom-Json
    if (-not $settings.hooks) { $settings | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) }
    $settings.hooks | Add-Member -NotePropertyName WorktreeCreate -NotePropertyValue $snippet.WorktreeCreate -Force
    $settings.hooks | Add-Member -NotePropertyName WorktreeRemove -NotePropertyValue $snippet.WorktreeRemove -Force
    ($settings | ConvertTo-Json -Depth 30) | Set-Content $settingsPath -Encoding utf8
    # validate
    $null = Get-Content $settingsPath -Raw | ConvertFrom-Json
    Write-Output "[ok] registered WorktreeCreate/WorktreeRemove in settings.json (validated)"
}
else {
    Write-Output "`nAdd these two keys to the 'hooks' object of ~/.claude/settings.json (or re-run with -PatchSettings):`n"
    Get-Content $snippetPath -Raw | Write-Output
}
Write-Output "`nThen set the target repo before dispatching worktree agents:"
Write-Output "  Set-Content `$HOME\.claude\hooks\worktree-target.txt 'C:\path\to\repo' -NoNewline"
Write-Output "  # Agent(isolation:'worktree') will then run in ~/.claude/agent-worktrees/<name>"
