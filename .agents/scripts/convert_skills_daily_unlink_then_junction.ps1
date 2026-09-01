# Follow-up: unlink .claude\skills (the POINTER only), rename daily, junction to vault, restore pointer.
# NEVER Remove-Item -Recurse on a junction. cmd rmdir on a symlink removes the link, not the target.
$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Prekzursil'
$vault = Join-Path $ProjectRoot '.agents\skills'
$daily = Join-Path $ProjectRoot '.claude\skills.daily'
$skills = Join-Path $ProjectRoot '.claude\skills'
$dailyBak = Join-Path $ProjectRoot '.claude\skills.daily.subset-backup-20260826'

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

Write-Output '==> pre'
Show-Link $skills
Show-Link $daily
Show-Link $vault
Show-Link (Join-Path $ProjectRoot '.agents\rules')

$skillsItem = Get-Item -LiteralPath $skills -Force
if (-not $skillsItem.LinkType) {
    throw "ILLEGAL: $skills is a real directory. Abort."
}

Write-Output '==> unlink skills pointer via cmd rmdir (link only)'
$rm = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', 'rmdir', $skills) -Wait -PassThru -NoNewWindow
if ($rm.ExitCode -ne 0) {
    throw "rmdir skills pointer failed exit $($rm.ExitCode)"
}
if (Test-Path -LiteralPath $skills) {
    throw "skills pointer still exists after rmdir"
}
if (-not (Test-Path -LiteralPath $daily)) {
    throw "FATAL: daily vanished after unlinking pointer"
}
Write-Output 'UNLINKED_SKILLS_POINTER'

try {
    $dailyItem = Get-Item -LiteralPath $daily -Force
    if ($dailyItem.LinkType) {
        Write-Output ("DAILY_ALREADY_LINK`t{0}" -f ($dailyItem.Target -join ','))
    } else {
        if (Test-Path -LiteralPath $dailyBak) {
            throw "backup exists $dailyBak while daily still real"
        }
        Rename-Item -LiteralPath $daily -NewName (Split-Path $dailyBak -Leaf)
        Write-Output "RENAMED`t$dailyBak"
        New-Item -ItemType Junction -Path $daily -Target $vault | Out-Null
        Write-Output "CREATED_JUNCTION`t$daily -> $vault"
    }
} catch {
    Write-Output "RENAME_FAILED`t$($_.Exception.Message)"
    Write-Output 'Will restore skills pointer to existing daily, then copy-missing fallback needed'
    throw
} finally {
    if (-not (Test-Path -LiteralPath $skills)) {
        try {
            New-Item -ItemType Junction -Path $skills -Target $daily | Out-Null
            Write-Output "RESTORED_SKILLS_JUNCTION`t$skills -> $daily"
        } catch {
            cmd /c mklink /J $skills $daily
            Write-Output "RESTORED_SKILLS_MKLINK`t$skills -> $daily"
        }
    }
}

$finalSkills = Get-Item -LiteralPath $skills -Force
if (-not $finalSkills.LinkType) {
    throw "ILLEGAL: skills is a real directory after restore"
}

Write-Output '==> post'
Show-Link $skills
Show-Link $daily
Show-Link (Join-Path $ProjectRoot '.agents\rules')
Write-Output 'SUCCESS:daily-junction-or-restored'
