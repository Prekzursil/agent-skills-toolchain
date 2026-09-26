---
title: Checkpoint Codex Stop hook goal corruption 2026-09-02
type: note
permalink: main/compaction-checkpoints/checkpoint-codex-stop-hook-goal-corruption-2026-09-02
tags:
- checkpoint
- harness
- codex
- stop-hook
---

# Checkpoint Codex Stop hook goal corruption 2026-09-02

- [fact] Window `01a06241-3d71-7442-97cf-f9762d6a73f0`, root session `01a06214-343d-7da2-bc57-cf9e4df9cd23`.
- [decision] Fix the Stop/SubagentStop sensitive-artifact plus AUTO-CAPTURED feedback so it cannot disrupt ongoing agents or replace the active goal; then resume the original Cursor authentication architecture ADR.
- [fact] Source is `C:/Users/Prekzursil/source/agent-skills-toolchain/agent-self/harness/modules.py`; live twin is `C:/Users/Prekzursil/.agents/harness/modules.py`.
- [fact] Existing uncommitted work added a Grok-only once-per-transcript cooldown. Live terminal evidence shows Codex still repeats `sensitive_artifact` on Stop/SubagentStop, and Stop can merge `basic_memory_nudge`.
- [fact] Session goal file `7ef7bdf090130e9523b7.json` was overwritten by quoted hook feedback.
- [decision] Extend cooldown to all providers; add GoalModule stripping/ignoring for host-rendered Stop/SubagentStop plus AUTO-CAPTURED blocks while preserving genuine trailing user text; preserve the spool capability.
- [fact] Original goal: decision-record doc covering Cursor token taxonomy, local artifacts, public Auth0/WorkOS/Okta login-hop mechanics, and owner-observed request/response evidence; no replay or bypass.
- [decision] Next: add regression tests first, patch, run targeted tests and both-state controls, deploy/sync and verify parity, repair the current goal, run required Python/code reviews, then finish the ADR.
