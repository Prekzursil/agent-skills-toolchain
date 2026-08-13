# RULERESEARCH — VERIFY lane: independent re-measurement of the BUILD lane

Every claim below was produced by a command **I executed in this session**, not read from the
build report. Where I accepted a builder number, I re-derived it; where I could not, I say so.

COVERAGE: all four DoD items MEASURED. Commit scope MEASURED. Nine contradictions: 5 re-verified
at their own source in depth, 4 by direct measurement of the count/predicate they assert.
UNMEASURED: the "before" half of "167/167 before and after" (see §7), and exhaustiveness of the
contradiction list (unprovable; my independent slice is in §6).

## Verdict: PARTIAL — every DoD item reproduces; one overclaim, no real defects

| DoD item | verdict |
|---|---|
| 1. every rule classified always-on vs lazy by measured frontmatter | **PASS** |
| 2. always-on token cost totalled | **PASS** |
| 3. every contradiction measured and listed with the correction | **PASS as scoped** (builder correctly labels "every" UNVERIFIED) |
| 4. no rule rewritten without evidence | **PASS** |

PARTIAL, not CLEAN, for exactly one reason: the self-test control count is asserted as **20** in
three places and is **17**. Nothing else I ran disagreed with the report.

## 1. Commit scope — PASS

    23ee1622  17 files, +11,449 / -24     (report: identical)
    e3493fc8   1 file,  +11               (report: identical)

Foreign-path filter over `git show --name-only` for both commits: **empty**.
DETECTOR CONTROL (mandatory before trusting that silence): the same filter against sibling commit
`de77c002` correctly emits `command-center/hook-audit/orchestrator-findings.md`. The detector
fires, so the empty result is a measurement.
`git diff HEAD -- docs/rule-audit/ rules/` is empty ⇒ everything below ran on the committed state.

## 2. DoD 1 — classification — PASS, and independently confirmed by my own session

`python docs/rule-audit/rule_audit.py --json <tmp> --md <tmp>` reproduces the report exactly:

    repo        files= 88 always-on= 8 (no-fm=8, fm-no-paths=0) lazy= 80 always-on-tok=17,107 all-tok= 63,294
    agent-self  files= 78 always-on= 4 (no-fm=4, fm-no-paths=0) lazy= 74 always-on-tok= 1,201 all-tok= 38,008
    live        files= 88 always-on= 8 (no-fm=8, fm-no-paths=0) lazy= 80 always-on-tok=15,141 all-tok= 54,426
    repo_vs_live: content_differs=29 only_first=0 only_second=0 load_semantics_differs=0
    repo_vs_agent_self: content_differs=9 only_first=10 only_second=0 load_semantics_differs=3

**THIRD-SESSION FIRST-PARTY CONFIRMATION.** This is not a re-run of the builder's predictor; it is
the harness itself acting on my prompt, which is a mechanically different instrument:

* My turn-0 system prompt carried **exactly** the 8 no-frontmatter live rules and no others —
  agents · bash-hud-and-terminal-emit · cross-vendor-dispatch · fan-out-contract ·
  harness-vcs-hygiene · single-signal-verification · stale-megapr-reconcile · windows-shell.
  8/8, zero false positives across 88 files.
* The DISCRIMINATING control: `common/owner-ops-authorization.md` carries the broadest possible
  selector `paths: ["**/*"]` and was **absent at turn 0**, arriving only after I Read a `.py`.
  This separates "frontmatter gates injection" from "glob breadth gates it" and confirms the
  inverse-intuition claim — `paths: ["**/*"]` DEMOTES an always-on rule.
* After that Read the harness injected **exactly** the 16 rules hardcoded as `OBSERVED_INJECTED`
  (11 `common/` + 5 `python/`) and withheld `common/hooks.md`. `lazy_predict.py`: 16/16 predicted,
  negative control PASS.

The third bucket (`frontmatter_without_paths`, which would load always-on while looking scoped) is
measured EMPTY in all three trees, so the no-frontmatter shorthand is verified-safe-today rather
than assumed. Correct call to report three buckets, not a binary.

## 3. DoD 2 — token totals — PASS

Recomputed from the fresh JSON, not copied:

    live always-on rules           15,141
    ~/.claude/CLAUDE.md   2,422  ~/.claude/AGENTS.md 2,707  ~/CLAUDE.md 2,780
    floor                          23,050          (matches)
    the 16 lazily-injected rules    8,520
    working total after a .py touch 31,570          (matches, 23,050 + 8,520)
    windows-shell 4,560 + single-signal 3,634 = 8,194 = 54.1% of 15,141

The artifact states `**54.1%** (8,194 / 15,141)` — denominator shown inline, correctly scoped.
(The *commit message* phrases it as "54.1% of it" directly after quoting the 23,050 floor, where
the figure would be 35.5%. The artifact is right; only the commit prose is ambiguous. Not a defect.)

Estimator caveat is enforced in code, not just prose: control 4 asserts the encoder NAME is
`tiktoken/cl100k_base`, so a silent `chars/4` fallback cannot be reported as exact.

## 4. DoD 3 — contradictions — PASS as scoped. Five re-verified at source

1. **`sync-from-live.ps1:477`** is verbatim `$writeAllowed = (-not $WhatIf -and -not $Drift)`.
   `$Report` is absent from the gate ⇒ bare `-Report json` **WRITES**. The LIVE always-on rule
   `~/.claude/rules/common/harness-vcs-hygiene.md:20` advertises "`-Report json` to see drift".
   An always-on rule teaching a writing command as a read-only inspection. The repo copy is
   already correct (`rules/common/harness-vcs-hygiene.md:22-29`) ⇒ **deploy gap, not authoring
   gap**, exactly as reported. CONFIRMED.
2. **`agent-self/config/AGENTS.md` §9 inverts a security non-negotiable.** §9 spans `:111-:124`;
   the live `:113` bullet "NEVER remove, rotate, revoke, regenerate, unset or otherwise MODIFY any
   API key or token" is **absent entirely**, and §9b `:131` ends "→ rotate, don't just delete"
   where live `:144` says "leave the rotation to the owner. Rotating on their behalf is the banned
   action". `bootstrap.ps1` force-copies `config/*` over `~/.claude` — the copy is at **`:45`**
   (`Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force`); the report's `:44` is
   that line's comment header, a one-line anchor slip, not a wrong finding. CONFIRMED, highest
   severity in the lane.
3. **`sync-rules.ps1:14-15`** claims live is a SUPERSET holding `windows-shell.md`,
   `static-analyzer.md`, `coding-style.md` unversioned. All three are present in `rules/common`
   (and in live); the tool's own name sets are identical (`only_first=0 only_second=0`). The
   docstring is false. CONFIRMED. Also `:57` is `Get-ChildItem -Path $srcRoot -File -Filter *.md`
   with **no `-Recurse`** ⇒ the non-recursive limit the README now documents is real. CONFIRMED.
4. **`context-budget` skill absent from 5/5 skill roots**, with a POSITIVE control
   (`multi-ai-mingle` found present) proving the prober finds skills that exist. CONFIRMED.
   (Report says the control found it in 3 roots; I measure 4 of 5. The control still fires, so the
   absence verdict is unaffected — a control-detail slip, not a wrong conclusion.)
5. **`cross-vendor-dispatch.md` §1 vs `AGENTS.md` §4a.** LIVE `cross-vendor-dispatch.md:9` says
   "NEVER … `run_in_background` for a dispatch"; LIVE `AGENTS.md:63` (§4a) says >60 s ops MUST use
   `run_in_background`/`Monitor`. Both always-on, genuine collision. The repo copy reconciles it
   (`:11,:19,:23,:28` — banned only "**without a join**"). CONFIRMED live-wrong / repo-right.

Also re-derived mechanically: `rules/common` holds **20** `.md` files and `rules/` holds 14
directories = **13 language dirs** + `common` (report: 20 and 13 — correct); no `./install.sh`
exists at the repo root (`Test-Path install.sh` → False).

## 5. DoD 4 — no rule rewritten without evidence — PASS

Only two rule files touched. The `single-signal-verification.md` edit is a single line and is a
textbook C2 fix — the mechanism was right, the sentence was wider than its evidence, and the
sentence (not the rule) was corrected to "the other 12 in `common/` (80 tree-wide)". My classifier
gives 20 common − 8 always-on = **12** and **80** lazy tree-wide. Both exact.
Cost re-measured from the committed blobs: 3,634 → 3,672 = **+38 tok/turn**, exactly as disclosed.
`rules/README.md` carries `paths: ['**/*.__never_load__']` ⇒ genuinely a never-load sentinel, so
the "0 always-on tokens" claim for the README rewrite is CONFIRMED.

## 6. My own independent contradiction sweep — 0 new findings (and one self-caught error)

I ran a path-reference slice of the settling experiment the builder named
(`docs/rule-audit/_verify_pathrefs.py`, both-states control on a known-good and known-bad path):
**21 references across the 8 always-on live rules, 2 unresolvable.** Both refuted on inspection:

* `codex-rescue.md` — **exists**, at `~/.claude/plugins/.../codex/agents/codex-rescue.md`. My root
  set was too narrow. Reporting it would have been a detector failure, not a finding.
* `check_no_regression.py` — genuinely not on disk, but it appears inside a *war-story table cell*
  describing a past session, not as an instruction to run anything. **use-vs-mention**: the rule
  NAMES the tool, it does not depend on it. Not a contradiction.

So my independent slice found **no tenth contradiction**. That does not prove the list is
exhaustive — my slice covered one axis (path references) on 8 of 88 files — but it is evidence
*for* the builder's "floor, not a census" scoping rather than against it.

## 7. Gates re-run by me, on the committed state

    uvx ruff@0.15.17 check docs/rule-audit/          -> All checks passed!
    uvx ruff@0.15.17 format --check docs/rule-audit/ -> 10 files already formatted (12 with mine)
    rule_audit.py --self-test                        -> SUCCESS, exit 0  (17 assertions, not 20)
    lazy_predict.py                                  -> SUCCESS 16/16 + 1/1, exit 0
    pytest ci/tests/test_rules_*.py (8 modules)      -> 167 passed in 3.45s

**The ruff-format finding independently reproduced on me.** My own two probe scripts failed
`ruff format --check` on first write ("2 files would be reformatted") while `ruff check` passed —
the exact trap the builder documented as REFUTING the grounding lane's "ruff clean". I formatted
them and proved it semantics-preserving the same way (both still emit their `SUCCESS:` terminal
state and `checked=21` after reformat). This is a second, independent instance of the defect.

NOT MEASURED: the "before" half of "167/167 before and after". I ran only the AFTER state. The
builder scopes this correctly as a no-regression signal, explicitly *not* proof the new README
block is accurate — the accuracy evidence is the directory listing, which I re-derived in §4.

**Pre-existing full-suite failure — CONFIRMED not the builder's**, by three independent signals:
(a) the mechanism is platform-level — `sys.getfilesystemencoding()=utf-8`,
`getfilesystemencodeerrors()=surrogatepass`, and `os.fsdecode(b'\xff')` raises `UnicodeDecodeError`
on this box regardless of repo state; (b) `test_check_skill_dual_write.py` contains **0** references
to `rules/`, `docs/`, or `rule-audit`; (c) neither lane commit touched `ci/` at all, and that test
file's last change is `f15cddbf`, predating both.

## 8. The one overclaim

> **SUPERSEDED IN PART, 2026-08-13 (BUILD round 2).** This section is CORRECT as a statement about
> the round-1 code and is left intact. Two facts moved after it was written: the BUILD lane folded
> the missing fail-closed assertion into `--self-test` (the one-line fix §8's sub-point names), so
> the live count is now **19**, and `rule_audit.py` now prints that count and a per-group inventory
> itself. Every number below is therefore historical; `r2_control_count_gate.py` holds the *current*
> prose to the tool. The lines carrying those historical figures are tagged
> `<!--count-historical-->` so the gate skips them — an explicit field, not a guess about prose.
> Nothing here was rewritten to make the finding disappear.

**"20 detector controls" — the count is 17.** <!--count-historical--> Two mechanically independent counts agree: an AST
walk of `self_test()` finds **17** `check()` call sites, and the runtime emits **17** PASS lines
(6 + 4 + 2 + 3 + 2 across the five groups). The builder's own enumeration in the report sums to 18,
so no counting method yields 20. Asserted in `RULE-AUDIT.md:26`, `RULE-AUDIT.md:502`, and the
commit message. The report additionally quotes the tool as printing
`SUCCESS: all controls passed (20)` <!--count-historical-->; the tool actually prints
`SUCCESS:rule_audit-self-test all controls passed` — **the count in the quoted output does not
come from the tool.** `rule_audit.py` itself claims no count anywhere; the tool is honest and the
prose is not.

Scoped version that is CONFIRMED: *"`--self-test` runs **17** detector-control assertions across <!--count-historical-->
five control groups — classifier both-states (6), drift silent-then-firing (4), CRLF≡LF (2),
encoder honesty (3), empty/missing-dir fail-closed (2) — all passing, exit 0."* (Round-2 state:
`classifier=6 drift=4 crlf=2 encoder=3 failclosed=4 TOTAL=19`, printed by the tool.)

Sub-point: the report lists a third fail-closed control, "`main()` returns non-zero when the repo
walk yields zero files". That behaviour **is implemented and does work** — I supplied the missing
both-states test (`docs/rule-audit/_verify_failclosed.py`): STATE A (repo tree missing) → `main()`
returns **1** and prints `FAILED:rule_audit … detector broken`; STATE B (healthy) → **0**. So the
code is right; it is simply **not exercised by `--self-test`**, and counting it as a passing
control is the same widening. One-line fix: add that assertion to control group 5.

## 9. Real defects

**None.** No claim I re-executed produced a different answer, no commit swept a foreign path, no
rule was edited without a measurement behind it, and the one high-severity finding (the
`agent-self` §9 credential inversion) is real, correctly severity-ranked, and correctly left
unapplied under a propose-only scope.

## 10. Confidence

* ALMOST CERTAIN (90-99%): classification, all token totals, drift counts, commit scope, the five
  contradictions in §4, the 13→3 and +1,001→+1,216 corrections (both arithmetically closed:
  10+3=13; 1,216−1,001=215=crlf_pairs), the pre-existing test failure, and the 17-vs-20 count
  (two independent counting methods).
* LIKELY (55-80%): that no tenth contradiction exists in the always-on set. My slice was one axis
  on 8 files and found none, but exhaustiveness is not provable and the builder says so first.
* UNCERTAIN, disclosed: every token figure is `cl100k_base`, not Anthropic's tokenizer (±10-20%).
  `/context` is the only first-party receipt and a subagent cannot invoke it. This is disclosed
  inline by the tool, the artifact, and the build report — no one is hiding it.
