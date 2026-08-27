# One-shot LEGAL conversion: keep .claude\skills -> skills.daily,
# make skills.daily a junction to .agents\skills. Never turn .claude\skills
# into a real directory. Does NOT run MCP merge / import_codex_mcp.py.
$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Prekzursil'
$stamp = '20260826'
$bakRoot = Join-Path $ProjectRoot ".claude\harness-share-backup-$stamp"
$vault = Join-Path $ProjectRoot '.agents\skills'
$daily = Join-Path $ProjectRoot '.claude\skills.daily'
$skills = Join-Path $ProjectRoot '.claude\skills'
$dailyBak = Join-Path $ProjectRoot ".claude\skills.daily.subset-backup-$stamp"
$rulesSrc = Join-Path $ProjectRoot '.claude\rules'
$rulesDst = Join-Path $ProjectRoot '.agents\rules'
$coworkOut = Join-Path $ProjectRoot 'Cowork\output'

function Show-Link([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Output "MISSING`t$Path"
        return
    }
    $item = Get-Item -LiteralPath $Path -Force
    $kind = if ($item.LinkType) { $item.LinkType } else { 'RealDirOrFile' }
    $target = if ($item.Target) { $item.Target -join ',' } else { '' }
    Write-Output ("LINK`t{0}`t{1}`t{2}" -f $Path, $kind, $target)
}

New-Item -ItemType Directory -Path $bakRoot -Force | Out-Null
New-Item -ItemType Directory -Path $coworkOut -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot '.grok\config.toml') -Destination (Join-Path $bakRoot 'grok-config.toml') -Force

Write-Output '==> pre-state'
Show-Link $skills
Show-Link $daily
Show-Link $vault
Show-Link $rulesSrc
Show-Link $rulesDst

$skillsItem = Get-Item -LiteralPath $skills -Force
if (-not $skillsItem.LinkType) {
    throw "ILLEGAL: $skills is a real directory. Aborting. Do not convert."
}

if (-not (Test-Path -LiteralPath $vault)) {
    throw "STOP: vault missing $vault"
}

# Rules: .agents\rules junction -> .claude\rules (one tree, Grok extra_rule_dirs)
if (-not (Test-Path -LiteralPath $rulesDst)) {
    New-Item -ItemType Junction -Path $rulesDst -Target $rulesSrc | Out-Null
    Write-Output "CREATED_JUNCTION`t$rulesDst -> $rulesSrc"
} else {
    Show-Link $rulesDst
}

# skills.daily: backup-rename real dir, then junction to vault
$dailyItem = Get-Item -LiteralPath $daily -Force
if ($dailyItem.LinkType) {
    $t = $dailyItem.Target
    if ($t -is [array]) { $t = $t[0] }
    Write-Output "DAILY_ALREADY_LINK`t$t"
} else {
    if (Test-Path -LiteralPath $dailyBak) {
        throw "STOP: backup already exists at $dailyBak ; daily is still a real dir. Inspect by hand."
    }
    Rename-Item -LiteralPath $daily -NewName (Split-Path $dailyBak -Leaf)
    Write-Output "RENAMED_DAILY_TO_BACKUP`t$dailyBak"
    New-Item -ItemType Junction -Path $daily -Target $vault | Out-Null
    Write-Output "CREATED_JUNCTION`t$daily -> $vault"
}

# Re-verify .claude\skills is STILL a link (not a real dir)
$skillsItem2 = Get-Item -LiteralPath $skills -Force
if (-not $skillsItem2.LinkType) {
    throw "ILLEGAL after convert: $skills became a real directory"
}

Write-Output '==> post-state'
Show-Link $skills
Show-Link $daily
Show-Link $rulesDst
Show-Link (Join-Path $ProjectRoot '.gemini\skills')

Write-Output '==> named extras (top-level only)'
$named = @(
    (Join-Path $env:APPDATA 'goose'),
    (Join-Path $env:APPDATA 'Block\goose'),
    (Join-Path $env:LOCALAPPDATA 'goose'),
    (Join-Path $ProjectRoot '.copilot'),
    (Join-Path $ProjectRoot '.cursor\plugins\cache\cursor-public')
)
foreach ($p in $named) {
    if (Test-Path -LiteralPath $p) {
        Write-Output "YES`t$p"
    } else {
        Write-Output "NO`t$p"
    }
}

$pub = Join-Path $ProjectRoot '.cursor\plugins\cache\cursor-public'
if (Test-Path -LiteralPath $pub) {
    Write-Output '==> cursor-public top-level'
    Get-ChildItem -LiteralPath $pub -Force -Name | Select-Object -First 80
}

$gem = Join-Path $ProjectRoot '.gemini'
if (Test-Path -LiteralPath $gem) {
    Write-Output '==> .gemini top-level'
    Get-ChildItem -LiteralPath $gem -Force -Name | Select-Object -First 40
}

$gRoam = Join-Path $env:APPDATA 'goose'
if (Test-Path -LiteralPath $gRoam) {
    Write-Output '==> AppData\Roaming\goose top-level'
    Get-ChildItem -LiteralPath $gRoam -Force -Name | Select-Object -First 40
}

Write-Output 'SUCCESS:convert-skills-daily-to-vault-junction'
