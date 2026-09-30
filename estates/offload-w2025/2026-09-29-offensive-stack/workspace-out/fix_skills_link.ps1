$ErrorActionPreference = 'Stop'
$live = 'C:\Users\prekzursil\.claude\skills'
$vault = 'C:\Users\prekzursil\.agents\skills'
$daily = 'C:\Users\prekzursil\.claude\skills.daily'

# 1. merge vault-missing items from the deployed copy into the vault (SSOT)
$missing = Get-ChildItem -LiteralPath $live -Force | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $vault $_.Name))
}
foreach ($m in $missing) {
    Copy-Item -LiteralPath $m.FullName -Destination (Join-Path $vault $m.Name) -Recurse -Force
    Write-Output "merged into vault: $($m.Name)"
}

# 2. keep the real dir as a backup, then create the required junction
Rename-Item -LiteralPath $live -NewName 'skills.real-dir-pre-junction-20260929'
New-Item -ItemType Junction -Path $live -Target $daily -Force | Out-Null
Write-Output ("junction: " + (Get-Item $live).LinkType + " -> " + (Get-Item $live).Target)
# 3. sanity: a vault skill visible through the link
Test-Path -LiteralPath (Join-Path $live 'grill\SKILL.md')
