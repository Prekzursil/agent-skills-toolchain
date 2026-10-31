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
    [string]$Runtime  = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude\rules\common"),
    [string]$HookRoot = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".claude\hooks")
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
"  hook runtime    : $HookRoot  (exists: $(Test-Path $HookRoot))"
""

$fail = 0
foreach ($r in $rules) {
    $cited    = $contractText -match [regex]::Escape($r.Name)
    $deployed = Test-Path (Join-Path $Runtime $r.Name)
    # LOADABLE is the third condition, and the one this lint originally missed.
    # The loader keys off a `paths:` list in the frontmatter. A rule sitting in the right
    # directory with the wrong frontmatter shape is DEPLOYED but INERT - which is how
    # "the discipline rules now load" was claimed on 2026-09-25 while four of them
    # (all authored that day) had no `paths:` key at all and never loaded once.
    $head     = (Get-Content $r.FullName -TotalCount 14 -ErrorAction SilentlyContinue) -join "`n"
    $loadable = $head -match '(?m)^paths:'
    $ok       = $cited -and $deployed -and $loadable
    $status   = if ($ok) { 'OK  ' } else { 'FAIL' }
    if (-not $ok) { $fail++ }
    "  {0} {1,-32} cited={2,-5} deployed={3,-5} loadable={4}" -f $status, $r.Name, $cited, $deployed, $loadable
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

# A hook ENFORCEMENT layer cited by the contract that is not deployed at runtime is a
# dead gate: the contract promises every session a Stop/UserPromptSubmit control that
# the loader never runs. Found 2026-10-13 - sections 1c/1d cite
# hooks/gap-check/gap_check.py (Stop) while ~/.claude/hooks/gap-check/ did not exist,
# and nothing in this lint (or any other check) caught a dangling hook citation.
# Hooks follow the same authored->runtime shape as the rules above (authored
# ~/.agents/hooks, deployed ~/.claude/hooks), so a citation is satisfied only by the
# RUNTIME copy; an authored-only citation is deployment drift and FAILs, exactly like
# a rule that is cited but not deployed. The runtime root is a parameter (not derived
# from -Contract) so a green-proof run against a patched contract copy in %TEMP%
# still checks the real deployed tree.
$hookCited = [regex]::Matches($contractText, '(?<![\w~])((?:\.claude/|\.agents/)?hooks/[A-Za-z0-9_./-]+\.(?:py|ps1|sh))') |
             ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
foreach ($h in $hookCited) {
    $rel          = $h -replace '^\.(?:claude|agents)/', ''
    $runtimePath  = Join-Path (Split-Path $HookRoot -Parent) $rel
    $authoredPath = Join-Path $Repo $rel
    if (Test-Path $runtimePath) {
        "  OK   hook citation deployed: $h"
    } elseif (Test-Path $authoredPath) {
        "  FAIL hook citation NOT deployed (authored copy only: $authoredPath): $h"
        $fail++
    } else {
        "  FAIL hook citation missing everywhere (no runtime copy, no authored copy): $h"
        $fail++
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
