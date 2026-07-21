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
- reads/writes module globals or mutable default args;
- uses `time`, `random`, `uuid`, thread/PID, dict/set iteration order, or any non-determinism;
- mutates its arguments in place (compare return values only).

If the function isn't pure, either extract the pure core and diff *that*, or fall back to a Hypothesis differential test with a fixed seed. Local Python is **3.14 (unsupported by CrossHair today)** — run under **3.12** (a `py -3.12` venv, matching CI).

## Protocol

### 1. Make old and new both importable
`diffbehavior` compares two importable callables. Keep the pre-refactor body reachable — e.g. copy it to `mod.clip_old` and the new one to `mod.clip_new`, or point at two git revisions of the same qualified name. Both must be plain functions with the same call signature; **type-annotate the parameters** (CrossHair uses the hints to build symbolic inputs).

### 2. Run the symbolic diff (primary rail)
```bash
# in a Python 3.12 venv with:  pip install crosshair-tool
python -m crosshair diffbehavior mod.clip_old mod.clip_new
# tuning knobs when needed:
#   --per_condition_timeout=<sec>   cap Z3 time per path (raise for hard fns)
#   --per_path_timeout=<sec>
```
Read the exit code, not prose:
- **Counterexample printed, exit 1** → NOT equivalent. The listed `(x=...)` input is a concrete reproducer where the two disagree; this is the silent behavior change. Surface it.
- **`No differences found ... functions are likely the same!`, exit 0** → equivalent across all explored paths. Confidence scales with how much of the input space Z3 exhausted ("All paths exhausted" = strongest).
- **exit 2 / can't analyze** → CrossHair couldn't symbolically execute it → go to the fallback.

### 3. Hypothesis differential fallback (when CrossHair can't)
When the function hits a C extension, an unsupported type, or times out, fuzz both and assert equality:
```python
from hypothesis import given, strategies as st, settings
from mod import clip_old, clip_new

@settings(max_examples=300)  # deterministic seed by default; add derandomize=True in CI
@given(x=st.integers(min_value=-1000, max_value=1000))
def test_refactor_equivalent(x):
    assert clip_old(x) == clip_new(x), f"diverge at x={x}"
```
A falsifying example is the same signal as a Z3 counterexample (weaker guarantee — sampled, not exhaustive — but works on anything runnable). Choose strategies that actually cover boundaries (`min_value`/`max_value`, empty collections, None, NaN).

### 4. Report (advisory / shadow — never blocks)
This skill **observes and reports**; it does not gate a commit or nag. Emit a terminal-state line:
- `EQUIV: mod.old ≡ mod.new (crosshair: all paths exhausted)` — refactor claim upheld.
- `DIVERGE: mod.old ≠ mod.new at (x=100) → 100 vs 99` — the "pure refactor" changes behavior; hand the reproducer back for a fix or a spec decision.

Do not auto-fail the work-unit on a DIVERGE; a divergence can be an *intended* behavior change mislabeled as a refactor. Name it and let the author/owner decide.

## Why symbolic beats "I re-read it and it looks the same"
Re-reading is same-context self-confirmation. Z3 is an independent solver that will find the off-by-one boundary you missed — e.g. `max(0, min(x, 99))` vs a real `[0,100]` clamp diverges precisely at `x=100`, which random spot-checks around 50 never hit. The solver targets the path constraints, so it lands on exactly the edge inputs a human skims past.

## Verified (this machine)
Proven end-to-end under Python 3.12.10, `crosshair-tool 0.0.108`:
- **Broken clamp** `clip_old` (`[0,100]`) vs `clip_new` (`max(0,min(x,99))`): `diffbehavior` returned `Given: (x=100), clip_old: returns 100 / clip_new: returns 99`, exit 1. ✅ caught the off-by-one.
- **True equivalence** `x + x` vs `x * 2`: `No differences found ... functions are likely the same!`, exit 0. ✅ no false positive.
- **Hypothesis fallback** on the same broken clamp: falsifying example `x=100` (`100 != 99`), exit 1 — independently reproduced the identical boundary. ✅ fallback rail works.
