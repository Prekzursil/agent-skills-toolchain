# RULERESEARCH — BUILD lane, round 2: corrections to the round-1 artifact

Round 1 shipped `RULE-AUDIT.md` (classification of 254 rule files, token totals, 9 contradictions).
An independent VERIFY lane (`RULE-AUDIT-VERIFY.md`) and an adversarial round (commit `61e69cf2`)
re-executed it. Their verdict: **zero real defects, one CONFIRMED overclaim, two anchor/detail
slips, and one disclosed weakness in the VERIFY lane's own probe.** Round 2 fixes each of those,
and — because the confirmed defect was an overclaim rather than broken code — makes the class
mechanically unrepeatable instead of just correcting the sentence.

Every number below came from a command run in this session. Nothing was copied from a prior report
without re-execution.

COVERAGE: all 8 round-2 items MEASURED. UNMEASURED and disclosed inline: the token estimator is
still `cl100k_base` (no `/context` receipt available to a subagent), exhaustiveness of the
contradiction census remains unprovable (the path axis is now closed on both trees; other axes are
not), and the new gates are re-runnable scripts, **not wired into CI** (`ci/` is outside this
lane's file scope).

## Status

| # | item | verdict |
|---|---|---|
| R2-1 | "20 detector controls" overclaim at `RULE-AUDIT.md` :26, :401, :502 <!--count-historical--> | **FIXED** — count is now printed by the tool; all three sites corrected, refuted wording kept on the record |
| R2-2 | build report quoted `SUCCESS: all controls passed (20)` <!--count-historical-->, a line the tool never printed | **FIXED** — the tool now prints its own count and per-group inventory |
| R2-3 | a fail-closed control asserted in prose but never exercised by `--self-test` | **FIXED** — folded in, and proven to fire by deleting the code it guards |
| R2-4 | anchor slip `bootstrap.ps1:44` → `:45` (two sites) | **FIXED**, re-measured |
| R2-5 | control-detail slip: `multi-ai-mingle` "3 of the same roots" | **FIXED** — measured 4 of 5; the absence verdict it controls is unaffected |
| R2-6 | `_verify_pathrefs.py` basename-fallback masks a wrong-path reference | **FIXED** — superseded by a three-way classifier whose hidden state is proven reachable |
| R2-7 | is there a tenth contradiction on the path axis? | **MEASURED: no.** 176 files across both trees, 0 unwaived positional claims |
| R2-8 | gates re-run on the changed state | **GREEN** — see §6 |

## 1. R2-1/R2-2 — the overclaim, and the gate that makes it unrepeatable

The defect was never in the code. `rule_audit.py` printed no count at all; three *sentences*
supplied one, and a hand-written breakdown table supplied a third figure. Two independent counts
(AST walk of `self_test()`; runtime PASS lines) put the round-1 truth at 17.

Correcting the sentences alone would leave the same hole open, so round 2:

1. **made the number a tool output.** `--self-test` now ends with
   `CONTROL-GROUPS: classifier=6 drift=4 crlf=2 encoder=3 failclosed=4 TOTAL=19` and
   `SUCCESS:rule_audit-self-test all controls passed (19)`, both computed from counters the
   checks increment. Nothing hand-maintained.
2. **added `r2_control_count_gate.py`**, which fails if any control-count claim in
   `docs/rule-audit/*.md` disagrees with that output, if the per-group counts do not sum to the
   total, if the AST count disagrees, or if `RULE-AUDIT.md` stops quoting the tool line verbatim.

**The gate was run against the KNOWN-BROKEN state before it was believed.** On the unmodified
round-1 prose it reported exactly the three sites the adversarial round named, plus two the VERIFY
lane had not enumerated:

    BAD RULE-AUDIT.md:26 claims 20
    BAD RULE-AUDIT.md:401 claims 20
    BAD RULE-AUDIT.md:502 claims 20
    BAD RULE-AUDIT-VERIFY.md:168 claims 20
    BAD RULE-AUDIT-VERIFY.md:173 claims 20
    FAILED:r2_control_count_gate 7 mismatch(es)

**USE-VS-MENTION, and a hole I found in my own gate.** Two of those hits are the VERIFY lane
*reporting* the wrong number, not asserting it. Flagging them would be the exact mislabel this
program keeps making. The exemption is an explicit FIELD — a line carrying `<!--count-historical-->`
is skipped — not a guess about refutation cues in prose. Separately, the first version of the
extractor **missed** `**17** detector-control assertions` <!--count-historical--> at `RULE-AUDIT-VERIFY.md:178` because
markdown bold sits between the digits and the noun; a gate that a `**` defeats is a weak detector,
so emphasis is now stripped before matching. That hit only appeared after the fix.

`RULE-AUDIT-VERIFY.md` was **not** rewritten. Its §8 is correct about round 1; it carries a dated
SUPERSEDED-IN-PART note and the three historical figures are tagged, so the finding stays legible
and the gate stays honest.

## 2. R2-3 — a control that was asserted but never ran

The round-1 report counted "`main()` returns non-zero when the repo walk yields zero files" among
its passing controls. The behaviour existed; the assertion did not. The VERIFY lane supplied the
missing both-states test out-of-band (`_verify_failclosed.py`) and named the one-line fix.

Round 2 folded it into control group `failclosed` (2 → 4 checks) and then cleared the bar the
original failed — a control added in these circumstances has to be **shown to fire**:

    $ python docs/rule-audit/r2_failclosed_mutation.py
    MUTANT  (fail-closed deleted): rc=1  expected non-zero
            line: FAIL  STATE A repo tree missing -> main() non-zero -- rc=0
    PRISTINE(unmodified)         : rc=0  expected 0
            tool-reported control count: 19
    SUCCESS:r2_failclosed_mutation the new control FIRES on the mutant and is silent on the real module

Delete the four-line fail-closed branch from `main()` and the new control goes red naming itself.
A mutation the suite survives is a hole, not a pass.

## 3. R2-4 / R2-5 — the two slips, re-measured not accepted

    $ grep -n "Copy-Item" agent-self/bootstrap.ps1
    45:Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse -Force
    $ sed -n '44p' agent-self/bootstrap.ps1
    # 3. deploy config/ -> ~/.claude (merge over existing; wins over the base layer)

`:44` is the comment header; `:45` is the copy. Corrected at both sites in `RULE-AUDIT.md`
(§3.3 and §3.4). The finding itself — a `§9` security non-negotiable inverted in a force-copied
deploy source — is unchanged and remains the highest-severity item in the lane.

    multi-ai-mingle/SKILL.md   PRESENT: skills, .agents/skills, ~/.claude/skills, ~/.agents/skills
                               absent : skills-claude-only          => 4 of 5
    context-budget/SKILL.md    absent in all five                   => 5 of 5, control fires

Round 1 said the positive control found the skill in 3 roots; it is 4. The verdict that control
supports — `context-budget` absent from 5/5 — is unaffected, and reproduced here independently.

## 4. R2-6 / R2-7 — the path axis, closed on both trees

The adversarial round disclosed that `_verify_pathrefs.py:44-46` falls back to
`REPO.rglob(basename)`, so **a reference whose PATH is wrong but whose FILENAME exists elsewhere
resolved as satisfied** — and its known-bad control used a filename absent everywhere, so that
fallback was never exercised. Its "no tenth contradiction" silence was therefore weaker than it
read.

`r2_pathrefs.py` supersedes it: a three-way verdict (`EXACT` / `BASENAME-ONLY` / `MISSING`) whose
hidden middle state is driven by a control, scope widened from 8 files to **all 176** rule files in
the live and repo trees, and markdown link targets checked alongside backticked paths.

    detector controls (all three verdicts must be reachable):
      PASS  control EXACT         -> EXACT         (a path that resolves as written)
      PASS  control BASENAME-ONLY -> BASENAME-ONLY (wrong path, filename exists)
      PASS  control MISSING       -> MISSING       (filename exists nowhere)
      PASS  control EXACT         -> EXACT         (dotted-directory path must not be mangled)
      PASS  control EXACT         -> EXACT         (a leading ./ is still stripped)

    rule files scanned: 176 across 2 trees
    non-EXACT references: 50
      bare-filename MENTIONS (no location asserted, not findings): 48
      POSITIONAL path claims that do not resolve: 2      <- both WAIVED with a read reason
    SUCCESS:r2_pathrefs scanned=176 unwaived_path_claims=0 waived=2 name_mentions=48

**The 48 are not findings, and the split is a FIELD, not a judgement.** A bare filename with no
directory component (`.coverage-thresholds.json`, `pyproject.toml`, `codex_monitor.py`) names a
file *class* and asserts no location, so it cannot be a broken pointer. Only a token carrying a
directory component makes a positional claim. Counting the document instead of the field is what
mislabels this class every time.

Both surviving positional claims were READ at source and are benign:

* `live:README.md:104 -> ../common/coding-style.md` — inside an **illustrative example** of an
  override note *as it would appear in `rules/golang/`*, where the link is correct. The probe
  resolves relative to the containing file and cannot do that for a quoted example written from
  another file's perspective. Probe limitation, disclosed, not a rule defect.
* `repo:common/cross-vendor-dispatch.md:36 -> lib/job-control.mjs` — the same sentence states the
  companion "is not present in this repo". The rule names the file to describe a historical
  mechanism; it does not depend on it.

Each is a WAIVER carrying its reason, and **a waiver that stops matching fails the sweep** — a
stale exemption widens a gate exactly the way an unexercised control does. The sweep is also a
gate: `--self-test` drives `main()` through three states (clean → 0, one broken positional claim →
1, stale waiver → 1), all passing, so its green is not the silent-pass shape.

**Answer to R2-7: no tenth contradiction on this axis.** That is now a measurement over 176 files
with the previously-hidden failure mode reachable, rather than a slice over 8. It does **not** make
the contradiction list exhaustive — other axes (command invocations, line-number citations, counted
claims) are still unmeasured, and §3 of `RULE-AUDIT.md` remains scoped as a floor.

## 5. A detector bug I shipped and caught — recorded, not quietly fixed

The first run of `r2_pathrefs.py` reported
`BASENAME-ONLY .agents/skills/claim-verify-gate/scripts/claim_gate.py`, i.e. that
`single-signal-verification.md` cites a path that does not exist. **That was my probe, not the
rule.** The cause was `token.lstrip("./")` — `lstrip` strips a character SET, not a prefix, so
`.agents/...` became `agents/...` and a real file read as a wrong pointer:

    $ ls .agents/skills/claim-verify-gate/scripts/claim_gate.py
    -rwxr-xr-x 1 Prekzursil 197611 19035 Aug  9 17:00 ...claim_gate.py     # it is right there

Had I written it up instead of resolving it, round 2 would have shipped a fabricated tenth
contradiction against an always-on rule. The fix is a prefix strip, and the case is now a permanent
regression control (`dotted-directory path must not be mangled`), so the bug cannot return silently.

Second self-inflicted case, same session: the sweep initially reported `codex-rescue.md` MISSING —
a finding the VERIFY lane had already refuted by locating it in the plugin cache. My basename index
walked only the repo. Bounded `~/.claude` lookup added. **A detector that re-raises a
known-refuted finding is a detector failure, not a finding.**

## 6. Gates, on the changed state

    uvx ruff@0.15.17 check docs/rule-audit/          -> All checks passed!
    uvx ruff@0.15.17 format --check docs/rule-audit/ -> 17 files already formatted
    rule_audit.py --self-test                        -> SUCCESS ... (19), exit 0
    rule_audit.py --json ... --md ...                -> SUCCESS:rule_audit, artifacts byte-identical
    lazy_predict.py                                  -> SUCCESS 16/16 + 1/1 negative control
    r2_failclosed_mutation.py                        -> SUCCESS (mutant red, pristine green)
    r2_pathrefs.py                                   -> SUCCESS unwaived_path_claims=0
    r2_pathrefs.py --self-test                       -> SUCCESS 3/3 gate-level controls
    r2_control_count_gate.py                         -> SUCCESS (after the prose fixes)
    pytest ci/tests/test_rules_*.py (8 modules)      -> 167 passed in 0.85s

The measurement itself is unchanged by round 2 — regenerating `rule-audit.json` and
`RULE-AUDIT-TABLES.md` produced **byte-identical** files (`git diff --stat` empty), and the
headline numbers reproduce exactly: 88/78/88 files, always-on 8/4/8, live always-on 15,141 tok,
floor 23,050 tok, drift `repo↔live 29` / `repo↔agent-self 9 differ + 10 absent + 3 semantics`.

**The ruff-format trap fired a fourth and a fifth time.** All three new scripts passed
`ruff check` and failed `ruff format --check` on first write, and `quality.yml` runs both
repo-wide — so shipping them unformatted would have redded the SHARED gate for every lane.
Formatted, then proven semantics-preserving rather than assumed: stdout of all four invocations
byte-identical before and after (`cmp` on captured output, 4/4 IDENTICAL).

The fifth instance is the useful one, because it was caught by a gate rather than by luck. A
working-tree green is measured against CRLF bytes that CI never sees, so before committing I ran
`_r2_blobcheck.py`, which extracts the **staged blobs** (`git cat-file -p :<path>` — the stored
LF form, 0 CRLF measured), copies `ruff.toml` in beside them (a bare temp dir defaults to
line-length 88 against this repo's config and manufactures a false red), and runs both ruff steps
there. It went red on a file written *after* the last format pass:

    staged .py blobs extracted: 6   CRLF pairs in blobs: 0
    ruff check: rc=0            ['All checks passed!']
    ruff format --check: rc=1   ['1 file would be reformatted, 5 files already formatted']
    CONTROL (mangled): rc=1 (must be non-zero)
    FAILED:r2_blobcheck

After formatting: `rc=0 / 6 files already formatted`, control still firing,
`SUCCESS:r2_blobcheck`. The control matters — a blob checker that cannot go red on a deliberately
mangled copy is measuring readability, not formatting.

## 7. Residual — what round 2 did NOT do

1. **Nothing was deployed.** The two live-wrong always-on rules (`harness-vcs-hygiene.md` teaching
   `-Report json` as read-only when `sync-from-live.ps1:477` makes it WRITE; `cross-vendor-dispatch.md`
   §1 colliding with always-on `AGENTS.md` §4a) are still fixed only in `rules/`, which no agent
   reads. `pwsh scripts/sync-rules.ps1 -WhatIf` then the real run lands them. Not run here: it
   mutates the live instruction set of every concurrently-running sibling lane mid-run.
2. **The `agent-self/config/AGENTS.md` §9 credential inversion is still unpatched** (propose-only
   scope). Exact patch in `RULE-AUDIT.md` §5.1. It remains the highest-severity item in the lane.
3. **The new gates are not wired into CI** (`ci/` is outside this lane's scope). Three one-line
   additions would do it; each already emits a terminal `SUCCESS:`/`FAILED:` marker and a non-zero
   exit, and each has a proven failing state.
4. **Token figures remain `cl100k_base` estimates**, ±10-20%. `/context` is the only first-party
   receipt and a subagent cannot invoke it.
5. **Exhaustiveness is still unproven.** The path axis is closed on both trees; command
   invocations, cited line numbers, and counted claims are not. Settling experiment unchanged:
   extract every checkable assertion in `rules/**` and assert it mechanically.
6. **`ci/tests` cannot go fully green on Windows** — one pre-existing failure
   (`os.fsdecode(b"\xff")`, `surrogatepass` vs `surrogateescape`), proven pre-existing in a fresh
   clone by the VERIFY lane. Not this lane's.

## 8. Confidence

* **ALMOST CERTAIN (90-99%)** — the control count is 19 (three mechanically independent counts:
  runtime PASS lines, AST walk, per-group sum, all agreeing, plus a mutation proving the newest
  control fires). `bootstrap.ps1:45` is the `Copy-Item` (read at the line). `multi-ai-mingle` in
  4 of 5 roots and `context-budget` in 0 of 5 (same probe, control fires). 0 unwaived positional
  path claims across 176 files (three-way classifier with all verdicts controlled, plus three
  gate-level states). All round-1 measurements reproduce byte-identically.
* **LIKELY (55-80%)** — that no tenth contradiction exists anywhere in the rules corpus. The path
  axis is now closed on both trees and found none, but that is one axis; exhaustiveness is not
  provable and I say so before anyone else has to.
* **UNCERTAIN, disclosed inline** — token totals (estimator, not Anthropic's tokenizer). The
  `bootstrap.ps1` promote-delta of +691 tok / 3 files is still a simulation; no deployer was run.
* **OVERCLAIM CHECK on this document.** The two waived path claims are disclosed as *waived with a
  reason*, not folded into "clean". The 48 bare-filename mentions are reported as excluded and
  why. "No tenth contradiction" is scoped to the path axis in every place it appears. The two
  detector bugs I shipped are in §5 rather than quietly patched, because a probe that mislabels a
  correct rule is the same failure class as an artifact that overclaims a control count.
