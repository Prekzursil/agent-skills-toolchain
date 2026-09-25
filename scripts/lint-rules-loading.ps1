<#
  lint-rules-loading.ps1  —  assert that authored rules actually LOAD.

  P6 of the 2026-09-25 estate audit. A rule counts as "loading" only when BOTH hold:
    (1) a numbered section of the behaviour contract CITES it by filename, and
    (2) the file physically exists at the runtime path the loader reads
        (~/.claude/rules/common, the $Dest of scripts/sync-rules.ps1).

  Measured 2026-09-25 before this lint existed: neither held. CLAUDE.md @-imported only
  AGENTS.md / AGENTS-RUNTIME.md / ~/AGENTS.md, ~/.claude/rules did not exist, and three
  rules authored that day were inert AND untracked. This lint exists so that cannot
  recur silently.

  Exit 0 = every authored rule is cited and deployed. Exit 1 = at least one is not.
#>
param(
    [string]$Repo     = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents"),
    [string]$Contract = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude\AGENTS-RUNTIME.md"),
    [string]$Runtime  = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude\rules\common")
)
$ErrorActionPreference = 'Continue'

$src = Join-Path $Repo 'rules\common'
if (-not (Test-Path $src))      { "FAIL: authored corpus missing: $src"; exit 1 }
if (-not (Test-Path $Contract)) { "FAIL: contract missing: $Contract";   exit 1 }

$contractText = Get-Content $Contract -Raw
$hasSection   = $contractText -match '(?m)^##\s*12\.'
$rules        = Get-ChildItem $src -Filter '*.md' -File | Sort-Object Name

"rules-loading lint"
"  authored corpus : $src  ($($rules.Count) rules)"
"  contract        : $Contract  (section 12 present: $hasSection)"
"  runtime dir     : $Runtime  (exists: $(Test-Path $Runtime))"
""

$fail = 0
foreach ($r in $rules) {
    $cited    = $contractText -match [regex]::Escape($r.Name)
    $deployed = Test-Path (Join-Path $Runtime $r.Name)
    $status   = if ($cited -and $deployed) { 'OK  ' } else { 'FAIL' }
    if (-not ($cited -and $deployed)) { $fail++ }
    "  {0} {1,-32} cited={2,-5} deployed={3}" -f $status, $r.Name, $cited, $deployed
}

# A rule CITED by section 12 that does not exist in the corpus is a dead pointer: the
# contract sends the reader to a file that is not there. Found 2026-09-25 - section 12
# cited windows-shell.md while the file lived only in an unversioned tree, and this lint
# passed, because it only ever walked the corpus and never the citations.
$sec12 = [regex]::Match($contractText, '(?ms)^##\s*12\..*?(?=^##\s*\d|\z)').Value
if ($sec12) {
    # USE-vs-MENTION: only TABLE ROWS cite a rule. Section 12's prose also names files
    # (e.g. "`CLAUDE.md` @-imports only ...") and a naive scan of the whole section
    # reports those as dead rules - which is exactly what it did on first run.
    $rows  = ($sec12 -split "`n") | Where-Object { $_.TrimStart().StartsWith('|') }
    $cited = [regex]::Matches(($rows -join "`n"), '`([A-Za-z0-9._-]+\.md)`') |
             ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    foreach ($c in $cited) {
        if (-not (Test-Path (Join-Path $src $c))) {
            "  FAIL dead citation in section 12 (no such rule in the corpus): $c"
            $fail++
        }
    }
}

# A rule deployed at runtime but absent from the authored corpus is drift in the other
# direction - it loads but nobody can version or review it.
if (Test-Path $Runtime) {
    $orphans = Get-ChildItem $Runtime -Filter '*.md' -File |
               Where-Object { -not (Test-Path (Join-Path $src $_.Name)) }
    foreach ($o in $orphans) { "  WARN runtime-only rule (not in the authored corpus): $($o.Name)"; $fail++ }
}

""
if (-not $hasSection) { "FAIL: no '## 12.' section in the contract - nothing cites the rules"; $fail++ }
if ($fail -eq 0) { "PASS: every authored rule is cited AND deployed."; exit 0 }
"FAIL: $fail problem(s). Run scripts/sync-rules.ps1 and/or cite the rule in contract section 12."
exit 1
