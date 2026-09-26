---
title: Ultracode workflow-orchestration + reconcile learnings 2026-07-11
type: note
permalink: main/reference/ultracode-workflow-orchestration-reconcile-learnings-2026-07-11
tags:
- ultracode
- workflow
- reconcile
- self-reflect
- learnings
---

# Ultracode workflow-orchestration + reconcile learnings (2026-07-11)

Captured via /self-reflect after the Reframe 89-finding ultracode sweep (see [[project_reframe_ultracode_reconcile_state_2026-07-11]] / the reconcile-state note). Durable patterns, quality-graded high (each cost real recovery this session).

## Workflow orchestration
- **parallel() barrier deadlocks on ONE hung agent** (no per-agent timeout): a verify:shortmaker.py agent hung 34m (76.9k tok) and stalled the whole phase. Detect via journal `started` count > `results` count + a single agent-file with a frozen mtime while others completed. RECOVERY that works: TaskStop → edit the script to SHORT-CIRCUIT only that one finding (a conservative pre-set verdict, e.g. `if file endsWith shortmaker.py: return {..f, isReal:true}`) leaving every OTHER agent() call byte-identical so its journaled result still cache-hits → resume. Extends [[feedback_workflow_orchestration]].
- **Cross-session Workflow RESUME can CACHE-MISS** and re-run a whole phase live (burned ~100 agents). Do NOT trust resume cache across a CC process restart for the incomplete phase. ROBUST recovery for a large workflow that died mid-phase: RECONSTRUCT completed results from journal.jsonl (parse `{"type":"result",...,"result":{...}}` + map each to its input via the agent transcript's prompt), then launch a FIX-ONLY workflow with the salvaged data as args — 0 agents re-run.
- **Worktree isolation FAILS when the workflow cwd is not the git repo** ("Cannot create agent worktree: not in a git repository"). Here session cwd = C:\Users\Prekzursil but the repo is Documents/GitHub/Reframe. FALLBACK = direct-edit on the shared working tree: partition agents by FILE-DISJOINT source files, agents write NEW tests in UNIQUELY-NAMED files (test_ce_*.py / <Name>.ce.test.tsx) to avoid collisions, and REPORT (a) sharedTestEdits for consolidated test files they can't own + (b) behaviorChangesToWatch. The orchestrator applies the shared edits serially + runs the real gates. check-before-apply in the prompt makes it idempotent over an already-partially-reconciled tree.
- Workflow agents can't run the full 100% gate (no venv/node_modules in a worktree; and here no worktree at all) → they produce the change; the MAIN LOOP is the authoritative gate. Trust nothing, verify the union.

## Reconcile discipline (vet every failure)
- For each gate failure: is the FIX correct (→ update the test) or a REGRESSION (→ fix the code)? Never blanket-green. Two failures became IMPROVEMENTS not paper-overs: provider.py `_prefer_provider_first` now prefers an EXACT-id match over a label-only match; a half-wired frame-times seam (fixer wrote a test for an unadded Services ctor seam) was COMPLETED (add the seam) not reverted.
- **RoutingPolicy fail-closed pattern** (DEFAULT_GLOBAL='local'): when a fix extends RoutingPolicy enforcement to a new function (vision reranker/scorer, director editPlan, translation/dub), existing tests that grant CONSENT but not ROUTING correctly resolve to local → add `"routingPolicy": {"global": "cloud"}` to the test settings. This is a CORRECT security tightening (the function now honors local/cloud policy like _provider_for_function), NOT a regression. Same for per-provider TEXT consent gates → add `"consent": {"perProvider": {<id>: {"text": true}}}`.
- A newly-registered RPC (e.g. index.plan) breaks an exact-RPC-surface guard test → add it to the FROZEN set (intentional additions are fine; the guard just needs updating).

## Mechanics
- **Bash heredoc `git commit -F -` FAILS this session** (Bash shell broken) → use PowerShell `git commit -q -F <msgfile>` (write the message to a scratch file first; avoids all quoting issues for multi-line bodies).
- Commit in gate-verified batches scoped by area: `git reset -q; git add sidecar/` (or `app/`) then verify `git diff --cached --name-only | where !match area` is empty before committing — keeps the untracked build/ artifact out.
- `coverage report -m --include="*x.py"` reads the EXISTING .coverage data (instant, no re-run) to get exact missing branch lines like `948->947`.