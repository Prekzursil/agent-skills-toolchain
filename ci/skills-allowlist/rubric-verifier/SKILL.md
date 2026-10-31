---
name: rubric-verifier
description: Use when rubric verifier is needed. Use AFTER N candidate patches exist
  (from codex council / /multi-execute / external-tools Codex+Gemini fan-out) and
  BEFORE running tests, to select the best candidate execution-free. A fresh-context
  reviewer builds a repo-grounded rubric — a weighted checklist.
metadata:
  version: 0.1.0
  compatibility: claude-code codex cursor gemini-cli opencode
  source: https://arxiv.org/abs/2601.04171
  upstream_authors: Scale AI
permalink: dqverify-repo-20261013/ci/skills-allowlist/rubric-verifier/skill
---

# Rubric Verifier — execution-free candidate selector

Select the best among N candidate patches **without running any tests**, by having a
fresh-context reviewer build a repo-grounded rubric and score each candidate against
it.  The output is a ranked advisory list; the coverage gate remains the hard blocker.

## Why this exists

After `/multi-execute`, `codex council`, or an external-tools (Codex + Gemini) fan-out
you have N candidate diffs for the same task.  The current pipeline has no principled
execution-free SELECT step:

| Existing skill | What it does | Gap |
|---|---|---|
| `fresh-context-verify` | re-derives one load-bearing value | single-value, not N-candidate ranking |
| VALIDATE (metaswarm) | runs tests | execution required; expensive to run N times |
| `code-review` | hunts for bugs in one diff | not a multi-candidate rubric scorer |

This skill fills the SELECT point: pick the best candidate before spending test-runner
cycles on all N.

## Trigger

Run this skill **after** N ≥ 2 candidate diffs exist and **before** VALIDATE, when:
- A `/multi-execute` or `codex council` run has produced N patches in a manifest file
  (default: `.multi-execute/candidates/` or `.council/candidates/`), **or**
- External-tools (Codex CLI + Gemini CLI) have each produced a patch and you need to
  pick one before committing to the VALIDATE loop.

Skip when:
- Only one candidate exists (nothing to rank).
- The issue is trivially localised (one-liner typo fix) — any diff that compiles is fine.
- The task is greenfield (no repo context to ground a rubric against).

## Composition with existing gates

```
[multi-execute / codex council / external-tools]
        |
        v
  rubric-verifier  ← THIS SKILL (advisory SELECT)
        |
        v
  VALIDATE (tests)  ← blocking gate
        |
        v
  ADVERSARIAL REVIEW
        |
        v
  COMMIT
```

The skill is **advisory**: it outputs a ranked pick + rationale.  If the top-ranked
candidate later fails VALIDATE, promote the runner-up (already flagged in the output)
and re-run VALIDATE.  The coverage gate in `.coverage-thresholds.json` is never
weakened by this skill.

---

## Phase 1 — Rubric Construction (FRESH context)

**This phase MUST run in a `Task()` subagent spawned with no prior context from the
main session.**  The anti-placebo requirement: a reviewer that already saw candidate
diffs will unconsciously anchor to them.  The fresh agent gets only the raw inputs.

### Inputs to pass to the fresh-context Task

```
TASK: Build a repo-grounded rubric for issue <ISSUE_ID / ISSUE_TITLE>.

Repo root: <ABS_PATH>
Issue description:
---
<ISSUE_TEXT>
---

Do NOT read any candidate diffs.  Do NOT look at any solution.
Your only job: explore the repo to understand what a CORRECT patch must do,
then emit a weighted rubric checklist.
```

### Fresh-agent exploration protocol

The fresh agent MUST use at least two of the following before writing the rubric:

1. **serena** (`get_symbols_overview`, `find_symbol`, `search_for_pattern`,
   `find_referencing_symbols`) — locate the symbols, classes, and call-sites the
   issue touches.
2. **repomix** (`pack_codebase` + `grep_repomix_output`) — get a compressed view of
   the affected module when the symbol graph is insufficient.
3. **Read** — read the specific files identified by steps 1/2 (entry point, callers,
   tests for the affected area).

The agent MUST NOT speculate about solutions.  It reads existing code to understand
invariants, patterns, and the expected shape of a fix.

### Rubric format (agent output)

The fresh agent emits a JSON rubric block, wrapped in fences:

```json
{
  "issue": "<ISSUE_ID>",
  "criteria": [
    {
      "id": "C1",
      "description": "Modifies <SymbolName> in <file>:<line-range> (the entry point named in the issue)",
      "weight": 3,
      "rationale": "The issue report and call-graph confirm this is the sole entry point for the broken path"
    },
    {
      "id": "C2",
      "description": "Preserves the existing public API signature of <MethodName>",
      "weight": 3,
      "rationale": "Three callers in tests/ and two in src/ rely on the current signature"
    },
    {
      "id": "C3",
      "description": "Handles the edge case where <input> is None / empty / negative (stated in issue body)",
      "weight": 2,
      "rationale": "Issue body explicitly lists this as a failing input"
    },
    {
      "id": "C4",
      "description": "Does not introduce new imports outside the existing dependency set",
      "weight": 1,
      "rationale": "Repo coding standards (found in CONTRIBUTING.md / existing patterns) avoid adding deps for small fixes"
    },
    {
      "id": "C5",
      "description": "Matches the error-handling pattern used in sibling methods (return None vs raise)",
      "weight": 1,
      "rationale": "Three sibling methods in same file use return-None; a raise would break callers"
    }
  ],
  "total_weight": 10
}
```

Rules for criteria:
- **Concrete, falsifiable** — every criterion must be checkable by reading a diff, no
  test execution allowed.
- **Repo-grounded** — each criterion must cite the specific symbol, file, or pattern
  it was inferred from.
- **Weighted 1–3** — weight 3 = must-have (wrong symbol, wrong invariant), weight 2 =
  should-have (stated edge case), weight 1 = nice-to-have (style/pattern match).
- **5–9 criteria** — fewer misses nuance; more dilutes signal.

---

## Phase 2 — Scoring (same or new Task per candidate)

For each candidate diff `C_1 … C_N`, the scorer (may be the same fresh agent, or a
separate Task per candidate for parallelism) reads the rubric from Phase 1 and the
diff, then produces a score sheet.

### Scorer prompt template

```
TASK: Score candidate patch <K> against the rubric below.

Rubric:
---
<RUBRIC JSON FROM PHASE 1>
---

Candidate diff (unified diff format):
---
<DIFF TEXT>
---

For each criterion C_i:
  - Score: FULL (earns weight_i points) | PARTIAL (earns weight_i / 2, round down) | MISS (0 points)
  - One-line justification citing a specific hunk or the absence of one.

Then compute:
  total_score = sum of earned points
  max_score   = rubric.total_weight

Flag the candidate as SPEC_MISALIGNED if:
  - It scores MISS on ANY criterion with weight == 3, OR
  - It modifies files outside the scope implied by the rubric criteria.

Output a JSON score sheet:
{
  "candidate_id": "C_K",
  "scores": [
    {"criterion": "C1", "score": "FULL|PARTIAL|MISS", "earned": <int>, "justification": "..."},
    ...
  ],
  "total_score": <int>,
  "max_score": <int>,
  "pct": <float, 0-100>,
  "spec_misaligned": <bool>,
  "misalignment_reason": "<null or string>"
}
```

### Parallelism option

If N ≥ 3, spawn N scorer Tasks simultaneously (one per candidate) rather than
running them sequentially.  Pass the same rubric JSON to each.  Wait for all to
complete before Phase 3.

---

## Phase 3 — Aggregate and Report

Collect all score sheets.  Produce the final advisory ranking:

```
## Rubric Verifier — Advisory Ranking

Issue: <ISSUE_ID>
Rubric criteria: <count> (total weight <W>)
Candidates scored: <N>

### Ranking

| Rank | Candidate | Score | % | Spec-misaligned | Notes |
|------|-----------|-------|---|-----------------|-------|
| 1    | C_K       | 8/10  | 80% | No  | Hits C1-C3 fully; partial C5 |
| 2    | C_J       | 6/10  | 60% | No  | Misses C3 (no None-guard) |
| 3    | C_M       | 4/10  | 40% | YES | Modifies wrong symbol (C1 MISS) |

### Recommendation

BEST: C_K — passes all must-haves (weight-3 criteria), highest overall score.
RUNNER-UP: C_J — promote if C_K fails VALIDATE (missing None-guard is testable).
REJECT: C_M — spec-misaligned; do not promote even if C_K and C_J both fail.

### Per-candidate rationale (brief)

**C_K (rank 1):** [one short paragraph]
**C_J (rank 2):** [one short paragraph]
**C_M (rank 3, REJECT):** [one short paragraph — why it is spec-misaligned]

---
ADVISORY — this ranking is not a gate.  Run VALIDATE on C_K next.
If C_K fails VALIDATE, promote C_J and re-run VALIDATE.
The 100%-coverage threshold in .coverage-thresholds.json remains the blocking authority.
```

---

## Caveats and honest limitations

- **Absolute numbers come from a specific experimental setting.** The +3.5 pp
  selection-quality improvement over baseline selectors (reported in arXiv:2601.04171)
  was measured on SWE-Bench Verified with Qwen-based candidates.  Your repo, model
  mix, and issue distribution will differ; treat the rubric rank as a strong prior,
  not a guarantee.
- **Execution-free means no runtime surprise coverage.** A candidate may pass all
  rubric criteria and still fail a test that exercises an untouched invariant.  The
  coverage gate exists precisely for this.
- **Rubric quality depends on repo exploration quality.** If serena/repomix cannot
  resolve the affected symbols (e.g. generated code, heavy metaprogramming), the
  criteria will be shallower.  Surface this in the rubric's `rationale` fields so the
  orchestrator can decide whether to trust the ranking.
- **SPEC_MISALIGNED is conservative.** A weight-3 MISS flags the candidate regardless
  of its total score.  This is intentional: a candidate that touches the wrong symbol
  is structurally wrong, not just incomplete.

---

## Worked example — rubric for a real-shaped issue

**Issue:** "TypeError: `process_batch` returns None when input list is empty (should
return an empty list).  Affects `DataPipeline.run()` callers."

**Phase 1 fresh-agent exploration finds:**
- `process_batch(items: list) -> list` in `src/pipeline/batch.py:L42`
- Called by `DataPipeline.run()` at `src/pipeline/core.py:L88` — result is iterated
  directly (a `None` return crashes the loop)
- `tests/test_batch.py` has no test for empty input
- Sibling method `process_single` returns `[]` for empty input (line 61)

**Rubric emitted:**

```json
{
  "issue": "GH-412",
  "criteria": [
    {
      "id": "C1",
      "description": "Modifies process_batch in src/pipeline/batch.py (the reported function)",
      "weight": 3,
      "rationale": "Issue names this function explicitly; it is the only definition"
    },
    {
      "id": "C2",
      "description": "Preserves signature process_batch(items: list) -> list",
      "weight": 3,
      "rationale": "core.py:L88 iterates the return value; a type change breaks it"
    },
    {
      "id": "C3",
      "description": "Returns [] (not None) when items is empty",
      "weight": 3,
      "rationale": "This is the exact reported bug; issue body gives this as the failing input"
    },
    {
      "id": "C4",
      "description": "Does not add new imports to batch.py",
      "weight": 1,
      "rationale": "Fix should be a single guard; new imports signal over-engineering"
    },
    {
      "id": "C5",
      "description": "Uses return [] style consistent with process_single (batch.py:L61)",
      "weight": 1,
      "rationale": "Sibling method establishes the pattern; diverging introduces inconsistency"
    }
  ],
  "total_weight": 11
}
```

**Two candidate diffs arrive:**

- **C_A:** adds `if not items: return []` at the top of `process_batch`.
  Scores: C1 FULL(3) C2 FULL(3) C3 FULL(3) C4 FULL(1) C5 FULL(1) = 11/11 (100%).

- **C_B:** refactors `DataPipeline.run()` to guard against `None` returns.
  Scores: C1 MISS(0) — wrong symbol — SPEC_MISALIGNED; overall score irrelevant.

**Output:** C_A ranked #1, C_B REJECTED (spec-misaligned).
Recommendation: run VALIDATE on C_A; do not promote C_B.

---

## Helper script

A small helper, `score_candidates.py` (co-located in this skill directory), can be
used to parse a candidates manifest and emit the scorer prompt for each diff as a
ready-to-paste block.  Run it from the repo root:

```
python path/to/skills/rubric-verifier/score_candidates.py \
    --rubric rubric.json \
    --manifest .multi-execute/candidates/manifest.json \
    [--out scoring-prompts/]
```

See `score_candidates.py` for the manifest format expected (one JSON entry per
candidate with `id` and `diff_path` keys).