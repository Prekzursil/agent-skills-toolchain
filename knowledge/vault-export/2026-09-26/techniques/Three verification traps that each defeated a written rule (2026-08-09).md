---
title: Three verification traps that each defeated a written rule (2026-08-09)
type: note
permalink: main/techniques/three-verification-traps-that-each-defeated-a-written-rule-2026-08-09
tags:
- verification
- detector-failure
- windows
- git
- worktree
- fan-out
- rules-defect
---

One wave, three traps. Each one defeated a rule that was already written down, which is the
interesting part: the guidance existed and was still insufficient.

## 1. `git archive` does NOT give you the blob — it gives you CRLF

`rules/common/windows-shell.md` §8b prescribed `git archive <rev> | tar -x -C <tmp>` to obtain
"blob content (LF) = exactly what CI checks out", for verifying formatters whose output differs
between CRLF and LF. **It returns the opposite.** `git archive` applies export-time EOL conversion.

Measured on one file, three routes, with a control proving all three are byte-identical after
LF-normalisation (so the delta is purely line endings, not content):

| route | bytes | CRLF |
|---|---|---|
| `git archive` + `tar -x` | 3,837 | **100** |
| `git cat-file -p <rev>:<path>` | 3,737 | 0 |
| `git show <rev>:<path>` | 3,737 | 0 |

**THREE independent agents hit this in a single wave** and each re-derived the fix separately; a
fourth (me) had already used the recipe to clear a ruff gate, where the verdict happened to be
right for unrelated reasons — the method was invalid regardless.

**A rule that points at the wrong bytes is worse than no rule**: it manufactures false confidence
in precisely the check meant to catch that class. Use `git cat-file -p` / `git show`.

## 2. Worktree isolation resolves the repo from cwd — and can land in someone else's project

`isolation: 'worktree'` in a Workflow resolves the target repo from the session's working
directory. Mine was `C:\Users\Prekzursil` — home, **not a git repo** — so it fell through to a
DIFFERENT project's checkout belonging to a concurrent session, which already held ~40 of its own
agent worktrees. Five agents were placed there.

No damage, and only because ONE lane verified its own environment before writing, produced two
independent signals (the `.git` gitdir path, and `package.json` productName + README + the workflow
file set), **refused to mutate**, and escalated with concrete options.

Two durable rules:
- Never rely on harness worktree resolution. Create worktrees yourself:
  `git -C <intended repo> worktree add -b <branch> <path> origin/main`, then have each agent
  re-verify with `git -C <path> remote get-url origin` **before its first write**.
- **Put the self-verification in the agent prompt.** An agent that quietly ADAPTS to a wrong
  environment conceals the orchestrator's bug; one that stops and reports exposes it. Design for
  escalation, not for resilience, when the environment itself may be wrong.

## 3. The isolated suite passes either way — only the full-scope run catches the regression

Fixing a `sys.modules` basename collision (four `hooks/*/gate.py`; a bare `import gate` resolves to
whichever loaded first), I namespaced the module via `spec_from_file_location`. Correct. I also
namespaced its sibling `tree_index`. **That broke two other tests**: `gate.py` does a bare
`import tree_index`, resolving under the ordinary key, so the test's monkeypatch of
`ti.get_or_build` patched a *copy the module under test never consults*. Two passing tests started
failing with expected-RAISED/got-FINDING.

`pytest hooks/recall-gate` passes **9/9 either way**. Only the exact CI command
(`pytest hooks/ -q --import-mode=importlib --ignore=...`) surfaced it.

- Namespace only the name that actually **collides**; a shared module must stay shared.
- `--import-mode=importlib` fixes test-FILE basename clashes, NOT a test's own module import —
  which is why CI passed collection and then failed at runtime.
- **Reproduce at the gate's real scope.** A fix validated on the narrow suite is unvalidated.

## The through-line

All three are the same shape as [[single-signal-verification]]: an instrument that looked
authoritative and measured the wrong thing. What differs is that in each case the *written
guidance itself* was the faulty instrument — a rule prescribing the wrong command, an isolation
mechanism with an unstated cwd dependency, a test scope that cannot see the failure. Grading a
rule requires the same both-states discipline as grading code: run the prescribed recipe against a
known answer before trusting what it returns.

Relates to [[subagent-stop-re-entrancy-loop-a-hook-that-commands-a-forbidden-action-cannot-be-cleared-2026-08-08]],
[[why-two-whole-programs-got-forgotten-three-measured-mechanisms-not-a-memory-failure-2026-08-08]].
