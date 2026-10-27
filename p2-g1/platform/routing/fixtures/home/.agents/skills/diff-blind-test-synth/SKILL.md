---
name: diff-blind-test-synth
description: Use when you want an INDEPENDENT external check that a patch/PR actually satisfies the spec — synthesize executable tests from ONLY the spec + public API (never the diff), then run them against the pre-patch tree (expect FAIL) and the patched tree (expect PASS). A divergence from that expected pattern flags a spec-miss (patch does not implement the requirement) or an over/under-fitted patch. Distinct from fail-first/red-proof (which validates the author's OWN changed tests) and execution-consensus rerank (which picks among candidate patches). Runs in SHADOW mode: observe + log only, never blocks. Evidence: UTBoost (2506.09289), MASTER A-Tier2.
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

### Diff-blindness is the whole point — enforce the isolation
### Protocol
### SHADOW mode (per council C5 — always ship observe-only)
### Anti-flake / anti-overfit guards
### Inline runner (shadow-mode, write on demand — no separate skill file)
### $BASE = merge-base, $TESTFILE = diff-blind synthesized test, $PKG = importable package
