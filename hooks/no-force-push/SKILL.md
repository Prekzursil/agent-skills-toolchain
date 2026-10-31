---
name: no-force-push
description: Use when the no-force-push tripwire blocks a git push --force; confirms
  whether the user explicitly approved a history-rewriting force-push before overriding.
permalink: dqverify-repo-20261013/hooks/no-force-push/skill
---

# no-force-push (forged discipline - companion procedure)

This skill is the human-followed procedure that pairs with the **no-force-push** hook
(a PreToolUse discipline forged by `forge-discipline`). The hook is the
enforcement (the harness runs it deterministically); this skill is what to DO when
it fires.

## What the hook does

When its trigger matches, the hook surfaces / enforces:

> Tripwire: refusing git push --force. Force-push can destroy remote history; AGENTS.md section 9 requires explicit user approval. If approved, re-run with FORGE_NO_FORCE_PUSH_OFF=1.

## Procedure when it fires

1. Read the hook's message - it names the exact condition that tripped.
2. Resolve the underlying cause rather than silencing the hook.
3. Only if it is a confirmed false positive, opt out for the moment via the
   `FORGE_NO_FORCE_PUSH_OFF=1` environment variable (or a `.disabled` file in the hook dir),
   and note why - do not leave the discipline disabled silently.

## Notes

- This stub is generated and intentionally minimal. Flesh out the procedure with
  the project-specific steps the discipline is meant to enforce.
- The hook fails open: if it errors it stays silent / allows, so this procedure is
  the backstop, not the only line of defence.