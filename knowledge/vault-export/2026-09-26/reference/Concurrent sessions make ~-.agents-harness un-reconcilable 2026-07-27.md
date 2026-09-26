---
title: Concurrent sessions make ~/.agents/harness un-reconcilable 2026-07-27
type: note
permalink: main/reference/concurrent-sessions-make-.agents-harness-un-reconcilable-2026-07-27
valid_as_of: 2026-07-27
tags:
- harness
- multi-session
- tdd
- false-positive
- reconcile
- agents-tree
---

# Concurrent sessions make ~/.agents/harness un-reconcilable

## The trap

Measured 2026-07-27 06:15 during a live-vs-git harness reconcile: **four Claude sessions were
running simultaneously** (`30bd50d4` = mine, plus `efee9a16`, `5c615def`, `09158d9e`, all
writing within 2 minutes), with 5 `claude.exe` CLI processes live.

At least one of them was doing **active TDD inside `C:\Users\Prekzursil\.agents\harness`**:

```
04:54  adapters.py          ┐ paired, ~1 min apart
04:53  tests/test_native_events.py             ┘
04:22  dispatcher.py        ┐
04:19  tests/test_dispatcher_degraded_health.py┘
03:49  tests/test_cov_dispatcher_adapters.py
03:15  redaction.py
02:56  ledger.py            ┐
02:56  tests/test_ledger_receipts_and_taint.py ┘
```

## The false positive it produced

A recon lane reported CRITICAL: *"Live `ledger.py` lacks the whole `claim_edge` API its own
byte-identical test asserts (5 failures)."*

That is **the red state of a TDD cycle**, not breakage — test committed first, implementation
pending, both touched at 02:56. Acting on it would have collided head-on with another
session's in-progress work.

## Observations

- [rule] Before classifying any tree as DRIFTED or BROKEN, check mtimes for ACTIVE EDITING. A file pair (impl + its test) touched minutes apart is in-progress work, not a defect #reconcile
- [rule] `~/.agents/harness` is NOT safe to reconcile while other sessions are live — same constraint class as an in-use git checkout #multi-session
- [failure-mode] "Test asserts an API the implementation lacks" reads identically as (a) a real regression and (b) a healthy TDD red state. The discriminator is TIMING, not content #detector
- [method] Detect concurrent sessions with: `find ~/.claude/projects -maxdepth 2 -name '*.jsonl' -newermt '-30 minutes'` — each live session appends continuously #ops
- [stable] `~/.agents/harness/modules.py` mtime 2026-07-20 — untouched, so the LIVE-AHEAD OwnerOps finding against it is trustworthy #harness
- [safe] `~/.claude/rules/common/` had ZERO modifications in 90 min — the rules restore is not contended #harness

## Workflow-resume lesson

`TaskStop` mid-run **cannot** cache in-flight agents. Resuming a 60-agent run that had 47
results + 13 in-flight respawned 21 agents (13 killed + 8 queued-but-unstarted). The cache
replay itself worked correctly (journal showed 81 unique starts, not ~120), but the 13
in-flight agents' partial work — ~15 min each — is unrecoverable. Budget that cost explicitly
before calling TaskStop.

## Relations

- relates_to [[harness-rules-common-empty-dual-guard-failure-2026-07-27]]
- relates_to [[feedback_parallel_agent_worktree]]
- relates_to [[feedback_workflow_orchestration]]