---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Commit is green | Suite run from a FRESH CLONE of that commit: exit 0 | Working-tree green |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Working-Tree Green Is Not Clone Green

Your working tree is not what CI checks out, so a green run there is evidence
about YOUR disk -- not about the commit.

- **Untracked and uncommitted files leak in.** A suite reporting **3,910 passed**
  in the working tree produced **31 collection errors** from a FRESH CLONE of the
  SAME commit (measured 2026-08-10). The tree was green on files git never saw.
- **On Windows, CRLF flips formatter verdicts.** The working tree is CRLF, the
  stored blob is LF, and a formatter can decide differently on the two bodies.
  A local `ruff format --check` green is NOT a CI green.

Verify against the STORED BLOB, not the file on disk:

```
git ls-files -s -- <path>     # the blob sha you are about to commit
git cat-file -p <blob-sha>    # the exact bytes CI checks out
```

**Do NOT reach for `git archive` here.** Measured 2026-08-14 on a CRLF-tracked
markdown file in this repo, one file through three routes: `git archive` + `tar -x`
returned CRLF-converted bytes (139 CRLF) -- `git archive` applies export-time EOL
conversion -- while `git cat-file -p` and `git show <rev>:<path>` each returned the
blob (0 CRLF). All three are identical after LF-normalisation, so the only delta is
the line endings -- which is exactly the delta that flips the formatter.

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

**Tests:**
```
 [Run test command] [See: 34/34 pass] "All tests pass"
 "Should pass now" / "Looks correct"
```

**Regression tests (TDD Red-Green):**
```
 Write -> Run (pass) -> Revert fix -> Run (MUST FAIL) -> Restore -> Run (pass)
 "I've written a regression test" (without red-green verification)
```

**Build:**
```
 [Run build] [See: exit 0] "Build passes"
 "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
 Re-read plan -> Create checklist -> Verify each -> Report gaps or completion
 "Tests pass, phase complete"
```

**Agent delegation:**
```
 Agent reports success -> Check VCS diff -> Verify changes -> Report actual state
 Trust agent report
```

## Why This Matters

From 24 failure memories:
- your human partner said "I don't believe you" - trust broken
- Undefined functions shipped - would crash
- Missing requirements shipped - incomplete features
- Time wasted on false completion -> redirect -> rework
- Violates: "Honesty is a core value. If you lie, you'll be replaced."

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## Checkpoint Provenance: disk-verified vs agent-claimed (Wave C, 2026-08-27)

Fail-closed completion doctrine (canonical text: `~\AGENTS.md` "Verification doctrine"):
**a budget-aborted gate is never green; completion claims require disk artifacts.**

- Every checkpoint / execution-state entry you write (`.beads\context\execution-state.md`,
  wave execution logs, resume files) carries a provenance tag:
  - **`disk-verified`** — you re-read the artifact/path the entry claims, in this message.
  - **`agent-claimed`** — asserted by an agent (including yourself, earlier) and not yet re-read.
- On resume, treat `agent-claimed` entries as UNVERIFIED: re-check the artifact before building
  on them. An absent artifact downgrades the claim to false — but only after a **grace window**
  (~60s re-check) because artifact writes lag under RAM pressure on this box (transcript-flush
  lag); an honest completion must not be marked false by a slow flush.
- A gate that was killed by budget (time/tokens/RAM) reports **FAILED-TO-RUN**, never PASS and
  never silently green. Enforcement hooks for this are deliberately NOT built yet — gated on
  Wave B's observe-mode evidence.

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.
