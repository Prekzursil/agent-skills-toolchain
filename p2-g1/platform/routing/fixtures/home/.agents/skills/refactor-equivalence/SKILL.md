---
name: refactor-equivalence
description: Use when a change CLAIMS to be a pure/deterministic refactor — "same behavior, cleaner code", "no functional change", "just simplified this", extract-method, inline, rewrite a helper — and you want an EXTERNAL proof (not the author's opinion) that old and new are actually equivalent. CrossHair `diffbehavior` uses Z3 to search for a concrete input where old_fn(x) != new_fn(x); if none exists across all paths, the refactor is likely sound. A Hypothesis differential test is the fallback when CrossHair can't symbolically execute the function (C extensions, unsupported types, timeouts). Scoped to PURE, DETERMINISTIC functions only (no I/O, no globals, no clock/random/network). NOT for behavior-CHANGING edits, not a general test runner (use smallest-check-ladder), not for non-Python. Advisory/shadow: it reports a counterexample, it never blocks.
---

# Refactor-Equivalence (CrossHair diffbehavior + Hypothesis fallback)

An agent asserting "this refactor is behavior-preserving" is the weakest kind of verifier — it is grading its own work. This skill replaces the assertion with an **external, symbolic proof**: CrossHair's `diffbehavior` drives Z3 to hunt for a concrete input where the old and new implementations diverge. Find one → the "pure refactor" is a silent behavior change; find none across all explored paths → high confidence the refactor is sound.

This is the differential (two-function) counterpart to the cosmetic-patch tripwire (which proves a change *cannot* alter behavior at the bytecode level). Use this when the code genuinely changed but is *claimed* semantically identical.

Evidence: MASTER decision-queue A-Tier2 (CrossHair `diffbehavior`), `agentic-repair-2 #5`, `general 4f` — REC: ADOPT, verified.

## When to run
- A diff is described as a **pure / deterministic refactor**: "same output", "no functional change", "just cleaner", extract/inline, rewrite a pure helper, simplify a branch.
- During VALIDATE for a work-unit whose acceptance is "behavior unchanged".
- Before trusting an agent-authored refactor of a **pure** function (arithmetic, string/collection transforms, parsers, clamps, comparators, encoders).

## Scope guard (READ FIRST — false results otherwise)
`diffbehavior` only reasons about **pure, deterministic** functions. It will give misleading or unstable answers if the function:
- does I/O, touches the filesystem/network, or logs;

### Protocol
### 1. Make old and new both importable
### 2. Run the symbolic diff (primary rail)
### in a Python 3.12 venv with:  pip install crosshair-tool
### tuning knobs when needed:
### --per_condition_timeout=<sec>   cap Z3 time per path (raise for hard fns)
### --per_path_timeout=<sec>
### 3. Hypothesis differential fallback (when CrossHair can't)
### 4. Report (advisory / shadow — never blocks)
### Why symbolic beats "I re-read it and it looks the same"
### Verified (this machine)
