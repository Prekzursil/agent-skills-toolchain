---
name: diff-blind-test-synth
description: 'Use when you want an INDEPENDENT external check that a patch/PR actually
  satisfies the spec - synthesize executable tests from ONLY the spec + public API
  (never the diff), then run them against the pre-patch tree (expect FAIL) and the
  patched tree (expect PASS). A divergence flags a spec-miss or over/under-fitted
  patch. Distinct from fail-first/red-proof. SHADOW mode: never blocks.'
permalink: dqverify-repo-20261013/skills/diff-blind-test-synth/skill
---

# Diff-Blind Adversarial Test Synthesis

The fixing agent authored the patch AND (usually) the tests that prove it — so "tests pass" only proves the patch is self-consistent, not that it meets the requirement. The one signal the author cannot fabricate is a test written by someone who **never saw the diff**. This skill produces that signal: a fresh Opus, given only the spec and the public API surface, writes executable tests; their PASS/FAIL pattern across the pre-patch and post-patch trees is an external oracle on whether the patch does what the spec asked.

Grounded in UTBoost (arXiv 2506.09289): LLM-synthesized, ground-truth-blind tests materially raise the bug-detection power of a patch benchmark by catching patches that pass the shipped suite yet miss the actual fix.

## When to run
- Reviewing a fleet/Codex/subagent patch or PR where the author wrote both code and tests.
- A bugfix task where you want proof the fix addresses the REQUIREMENT, not just the author's chosen test.
- Before adopting a "green-tested" change you did not write, when the spec is concrete enough to author tests from.
- NOT for: pure refactors with no behavioral spec; changes whose spec is only visible in the diff itself.

## What makes this distinct (do not conflate)
- **vs A3 fail-first / red-proof gate:** that gate takes the AUTHOR's changed tests and proves they fail on the merge-base. Here the tests are authored **blind to the diff** by a fresh context — it catches the case where the author's own tests are tautological or under-specify the requirement.
- **vs A4 / execution-consensus best-of-N rerank:** that picks the best among several candidate patches by behavioral clustering. Here there is ONE patch and the oracle is spec-derived tests, not candidate agreement.
- The three compose: red-proof validates the author's tests, diff-blind adds independent tests, consensus ranks candidates.

## Diff-blindness is the whole point — enforce the isolation
The synthesizing agent must receive the spec + public API/signatures ONLY. It must NEVER receive: the diff, the patched file bodies, the author's new tests, the PR description's implementation notes, or your own summary of the fix. Any leak makes the test co-author the patch and destroys the signal. Hand it a typed, minimal context (see step 2) — nothing more.

## Protocol
1. **Freeze the two trees.** Identify the merge-base (`git merge-base HEAD <base>`) = PRE tree, and the patched HEAD = POST tree. Prepare disjoint worktrees so the synthesized tests can run against each without cross-contamination (ride the existing WorktreeCreate flow; do not edit either tree).
2. **Spawn the diff-blind author (fresh context).** Use the `Agent` tool (general-purpose, Opus) with a prompt containing ONLY:
   - the requirement/spec (issue text, DoD, acceptance criteria) — verbatim, no implementation hints;
   - the public API surface the tests will call (function/class signatures, CLI flags, HTTP routes, types) — signatures only, NOT bodies;
   - the test framework + how to run it (`npx jest`, `pytest`), and the instruction to write only *executable, deterministic, black-box* tests that assert the spec's observable behavior.
   - Explicit ban: "You will NOT be shown the implementation or the diff. Do not ask for it. Write tests purely from the spec and signatures."
3. **Run the synthesized tests against BOTH trees** (never let the author run them — you run, to keep the author blind):
   - PRE (merge-base): expect **FAIL** (the requirement was not yet implemented).
   - POST (patched HEAD): expect **PASS** (the patch implements it).
4. **Read the pattern** (this is the verdict, logged not enforced):

   | PRE | POST | Verdict | Meaning |
   |-----|------|---------|---------|
   | FAIL | PASS | `SPEC_MET` | Patch implements the requirement (external confirmation). |
   | FAIL | FAIL | `SPEC_MISS` | Patch does NOT satisfy the spec — the strongest catch. Surface the failing case. |
   | PASS | PASS | `NO_SIGNAL` | Test doesn't exercise the change (already-true, or wrong target). Discard/regenerate. |
   | PASS | FAIL | `REGRESSION` | Patch broke behavior the spec required. Surface. |
   | error | * | `INVALID` | Test didn't compile/import against the API — regenerate with corrected signatures. |
5. **Record + surface.** Write the verdict to the event ledger via `note.py` (e.g. `DIFF_BLIND:SPEC_MET` / `DIFF_BLIND:SPEC_MISS <failing test>`). On `SPEC_MISS` / `REGRESSION`, report the concrete failing assertion to the reviewer — do NOT auto-block.

## SHADOW mode (per council C5 — always ship observe-only)
This gate NEVER blocks a commit, PR, or task and NEVER nags. It emits a `DIFF_BLIND:<verdict>` ledger line + a one-line reviewer note, nothing else. Promote OFF→SHADOW→ADVISE→ENFORCE only after a burn-in shows low false-`SPEC_MISS` rate (flaky/non-deterministic synthesized tests are the main failure mode — a `SPEC_MISS` that is really test flake). Until then it is advisory signal for a human, never an automated stop.

## Anti-flake / anti-overfit guards
- Require deterministic tests only; re-run any `SPEC_MISS` once to rule out flake before surfacing (double-fail = real).
- If POST fails only because the synthesized test asserts an implementation detail the spec never named, that is an over-specified test, not a `SPEC_MISS` — discard it (the spec is the contract, not the patch's internals).
- Cross-vendor bonus: synthesizing with a DIFFERENT model than authored the patch (e.g. Codex via `mcp__codex__codex`) makes the test's blind spots independent of the patch's — strongest when the patch and the tests come from different models.

## Inline runner (shadow-mode, write on demand — no separate skill file)
Once the diff-blind author has produced a test file, run it against both trees and log the verdict. Example for a Python patch (adapt paths / `jest` analogously):

```bash
# $BASE = merge-base, $TESTFILE = diff-blind synthesized test, $PKG = importable package
set -u
run_tree () {  # $1 = git ref, prints PASS|FAIL|ERROR
  wt=$(mktemp -d)
  git worktree add -q --detach "$wt" "$1" 2>/dev/null || { echo ERROR; return; }
  cp "$TESTFILE" "$wt/diff_blind_test.py"
  ( cd "$wt" && python -m pytest -q diff_blind_test.py >/dev/null 2>&1 ) \
    && echo PASS || { [ $? -eq 1 ] && echo FAIL || echo ERROR; }
  git worktree remove -f "$wt" 2>/dev/null
}
PRE=$(run_tree "$BASE"); POST=$(run_tree HEAD)
case "$PRE/$POST" in
  FAIL/PASS)  V=SPEC_MET ;;
  FAIL/FAIL)  V=SPEC_MISS ;;
  PASS/PASS)  V=NO_SIGNAL ;;
  PASS/FAIL)  V=REGRESSION ;;
  *)          V=INVALID ;;
esac
echo "DIFF_BLIND:$V pre=$PRE post=$POST"   # SHADOW: log only, exit 0 always
```
pytest exit codes: 0=all passed, 1=tests failed, ≥2=collection/error → maps to PASS/FAIL/ERROR above. The runner is observe-only: it always exits 0 and emits the ledger line; it never returns a blocking status.