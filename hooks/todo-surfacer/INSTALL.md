---
title: INSTALL
type: note
permalink: dqverify-repo-20261013/hooks/todo-surfacer/install
---

# Install: todo-surfacer  (Stop discipline)

**STATUS: STAGED FOR REVIEW - NOT WIRED IN.** `forge-discipline` never edits your
live `settings.json` or `_dispatch/manifest.json`. You review these artifacts and
apply the one line below by hand. (Mirrors the auto-skill-authoring discipline:
forge proposes, the human installs.)

The self-test below already PASSED - the hook provably fires on its trigger, stays
silent / allows otherwise, and fails open on garbage.

## Fold target: `manifest`

1. Copy this directory to the live hooks root:

       C:/Users/Prekzursil/.claude/hooks/todo-surfacer/

2. Add this ONE line to the `checks` array under `events.Stop` in:
      C:/Users/Prekzursil/.claude/hooks/_dispatch/manifest.json

      {"name": "forge/todo-surfacer", "script": "todo-surfacer/hook.py", "args": [], "timeout": 8, "isolate": null, "side_effect": "none", "emits": true}


3. Restart Claude Code (hooks/manifest are read at session start).

## Opt-out / kill-switch

- Env: set `FORGE_TODO_SURFACER_OFF=1` to disable this discipline.
- File: drop a `.disabled` file in `C:/Users/Prekzursil/.claude/hooks/todo-surfacer/`.

## Why this fold target

- **manifest** = dispatcher-consolidated, inject-only (one line, runs in-process,
  only ever exits 0). Used for SessionStart / Stop / Pre / PostToolUse inject hooks.
- **settings** = a standalone command entry. Used for any GATE (exit-2 blocking,
  which the dispatcher cannot carry) and for UserPromptSubmit (which the dispatcher
  does not handle).

## Self-test result (GameDay / chaos)

```
unit test : PASS
UNIT-PASS: todo-surfacer fires on trigger ('You left 3 open TODO/FIXME marker(s) in your final message. Capture them as open loops before they are lost.') and is silent otherwise

chaos test: PASS
CHAOS self-test: todo-surfacer (inject / Stop)
  [PASS] fires on trigger
  [PASS] silent on non-trigger
  [PASS] fail-open on garbage[0]
  [PASS] fail-open on garbage[1]
  [PASS] fail-open on garbage[2]
  [PASS] fail-open on garbage[3]
  [PASS] fail-open on garbage[4]
  [PASS] opt-out env silences it

CHAOS-PASS: hook fires on trigger, stays silent otherwise, and fails open

```

## Spec (provenance)

```json
{
  "name": "todo-surfacer",
  "event": "stop",
  "action": "You left {count} open TODO/FIXME marker(s) in your final message. Capture them as open loops before they are lost.",
  "trigger_kind": "response",
  "trigger_regex": "\\b(TODO|FIXME)\\b|- \\[ \\]",
  "fire_example": "Remaining: TODO wire the API; FIXME handle empty. - [ ] ship it",
  "silent_example": "All done. Everything shipped and verified.",
  "needs_state": false,
  "gates": false,
  "has_procedure": false,
  "case_sensitive": false,
  "trigger_field": null,
  "matcher": null
}
```