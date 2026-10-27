# LANE SKILLS2 / item 2 -- is the vault's OLD ui-audit main-guard actually a LIVE no-op?
#
# The brief says the vault holds "a live silent-no-op". CONFIRMED separately: the vault carries
# the OLD lexical guard `resolve(argv[1]) === resolve(__filename)` on 6/6 entry points while
# repo + skills.daily carry the fixed `__isMain`. But the OLD guard only FAILS when the
# invocation path traverses a symlink (Node resolves symlinks for ESM, so import.meta.url reports
# the REAL path while resolve(argv[1]) stays lexical). ~/.agents/skills is NOT a symlink.
#
# So: does the defect actually fire in the vault, or is it latent?
#
# BOTH-STATES CONTROL. The same file is run twice:
#   (1) through its REAL path            -- the way a Codex agent reaches the vault today
#   (2) through a purpose-made SYMLINK   -- the KNOWN-BROKEN state
# If (2) does not go silent, the detector is measuring nothing and (1) proves nothing either.

$ErrorActionPreference = 'Continue'
$vault = "$HOME\.agents\skills\ui-audit"
$daily = "$HOME\.claude\skills.daily\ui-audit"
$target = 'axe_scan.mjs'

function Probe([string]$label, [string]$dir) {
    $f = Join-Path $dir $target
    if (-not (Test-Path -LiteralPath $f)) { "{0,-40} MISSING" -f $label; return }
    $out = & node $f 2>&1 | Out-String
    $code = $LASTEXITCODE
    $ran = if ($out -match 'required|ERROR|usage') { 'MAIN-RAN' }
           elseif ([string]::IsNullOrWhiteSpace($out)) { 'SILENT-NO-OP' }
           else { 'OTHER' }
    "{0,-40} exit={1} {2,-13} out={3}" -f $label, $code, $ran, ($out.Trim() -replace '\s+', ' ').Substring(0, [Math]::Min(70, ($out.Trim() -replace '\s+', ' ').Length))
}

$tmp = Join-Path $env:TEMP ("s2guard_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
$linkVault = Join-Path $tmp 'lnk_vault'
$linkDaily = Join-Path $tmp 'lnk_daily'
New-Item -ItemType SymbolicLink -Path $linkVault -Target $vault -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType SymbolicLink -Path $linkDaily -Target $daily -ErrorAction SilentlyContinue | Out-Null

"=== REAL PATH (how the vault is reached today) ==="
Probe 'VAULT  (old guard)  real path' $vault
Probe 'DAILY  (fixed)      real path' $daily
""
"=== THROUGH A SYMLINK (the KNOWN-BROKEN state -- control) ==="
if (Test-Path -LiteralPath $linkVault) {
    Probe 'VAULT  (old guard)  via symlink' $linkVault
    Probe 'DAILY  (fixed)      via symlink' $linkDaily
} else {
    'SYMLINK CREATION FAILED -- control unavailable, real-path result proves nothing'
}
""
"CONTROL READING: if the two symlink rows are IDENTICAL the probe cannot tell the states"
"apart and every verdict above is void."
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
