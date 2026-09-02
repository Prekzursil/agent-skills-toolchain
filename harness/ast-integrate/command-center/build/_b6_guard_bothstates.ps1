# B6: BOTH-STATES control for the ui-audit main-guard defect.
#
# The claim: the repo copy's lexical `resolve(argv[1]) === resolve(__filename)` guard NEVER
# matches when the script is invoked through the `~/.claude/skills` junction, so main() silently
# never runs -- exit 0, no output, no artifacts (a green no-op).  The live copy's realpathSync
# `__isMain` guard does match.
#
# A probe that behaved the same on both copies would measure nothing.  So this runs BOTH copies
# through a junction and requires them to DIFFER.  Direct (non-junction) invocation is also run
# as a second control: there both copies must WORK, proving the difference is junction-specific
# and not "the repo file is just broken".

$ErrorActionPreference = 'Stop'
$tmp = Join-Path $env:TEMP ("uiguard_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$realRepo = Join-Path $tmp 'real_repo'
$realLive = Join-Path $tmp 'real_live'
New-Item -ItemType Directory -Path $realRepo -Force | Out-Null
New-Item -ItemType Directory -Path $realLive -Force | Out-Null

$repoSrc = 'C:\Users\Prekzursil\source\ast-integrate\.agents\skills\ui-audit\axe_scan.mjs'
$liveSrc = 'C:\Users\Prekzursil\.claude\skills.daily\ui-audit\axe_scan.mjs'
Copy-Item $repoSrc (Join-Path $realRepo 'axe_scan.mjs')
Copy-Item $liveSrc (Join-Path $realLive 'axe_scan.mjs')

$linkRepo = Join-Path $tmp 'link_repo'
$linkLive = Join-Path $tmp 'link_live'
New-Item -ItemType Junction -Path $linkRepo -Target $realRepo | Out-Null
New-Item -ItemType Junction -Path $linkLive -Target $realLive | Out-Null

function Probe([string]$label, [string]$path) {
    $out = & node $path 2>&1 | Out-String
    $code = $LASTEXITCODE
    $ran = if ($out.Trim().Length -gt 0) { 'MAIN-RAN' } else { 'SILENT-NO-OP' }
    "{0,-28} exit={1} {2}  out={3}" -f $label, $code, $ran, ($out.Trim() -replace '\s+', ' ').Substring(0, [Math]::Min(90, ($out.Trim() -replace '\s+', ' ').Length))
}

Write-Output '--- through a JUNCTION (the documented ~/.claude/skills invocation) ---'
Write-Output (Probe 'REPO copy  (known-BROKEN)' (Join-Path $linkRepo 'axe_scan.mjs'))
Write-Output (Probe 'LIVE copy  (known-FIXED)'  (Join-Path $linkLive 'axe_scan.mjs'))
Write-Output ''
Write-Output '--- CONTROL: direct real path, no junction (both must run) ---'
Write-Output (Probe 'REPO copy  direct' (Join-Path $realRepo 'axe_scan.mjs'))
Write-Output (Probe 'LIVE copy  direct' (Join-Path $realLive 'axe_scan.mjs'))

Remove-Item $linkRepo, $linkLive -Force -Recurse -Confirm:$false
Remove-Item $tmp -Recurse -Force -Confirm:$false
