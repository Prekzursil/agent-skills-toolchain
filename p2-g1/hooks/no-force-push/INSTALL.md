# Install: no-force-push  (PreToolUse discipline)

**STATUS: STAGED FOR REVIEW - NOT WIRED IN.** `forge-discipline` never edits your
live `settings.json` or `_dispatch/manifest.json`. You review these artifacts and
apply the one line below by hand. (Mirrors the auto-skill-authoring discipline:
forge proposes, the human installs.)

The self-test below already PASSED - the hook provably fires on its trigger, stays
silent / allows otherwise, and fails open on garbage.

## Fold target: `settings`

1. Copy this directory to the live hooks root:

       C:/Users/Prekzursil/.claude/hooks/no-force-push/

2. Add this hook object to the `"PreToolUse"` array under `"hooks"` in:
      C:/Users/Prekzursil/.claude/settings.json

      {"matcher": "Bash", "hooks": [{"type": "command", "command": "python \"C:/Users/Prekzursil/.claude/hooks/no-force-push/hook.py\"", "timeout": 8, "statusMessage": "no-force-push (tripwire)"}]}

3. Restart Claude Code (hooks/manifest are read at session start).

## Opt-out / kill-switch

- Env: set `FORGE_NO_FORCE_PUSH_OFF=1` to disable this discipline.
- File: drop a `.disabled` file in `C:/Users/Prekzursil/.claude/hooks/no-force-push/`.

## Why this fold target

- **manifest** = dispatcher-consolidated, inject-only (one line, runs in-process,
  only ever exits 0). Used for SessionStart / Stop / Pre / PostToolUse inject hooks.
- **settings** = a standalone command entry. Used for any GATE (exit-2 blocking,
  which the dispatcher cannot carry) and for UserPromptSubmit (which the dispatcher
  does not handle).

## Self-test result (GameDay / chaos)

```
unit test : PASS
UNIT-PASS: no-force-push halts on trigger ('Tripwire: refusing git push --force. Force-push can destroy remote history; AGENTS.md section 9 requires explicit user approval. If approved, re-run with FORGE_NO_FORCE_PUSH_OFF=1.') and allows otherwise

chaos test: PASS
CHAOS self-test: no-force-push (gate / PreToolUse)
  [PASS] blocks dangerous op (exit 2 + reason)
  [PASS] allows benign op (exit 0)
  [PASS] fail-open on garbage[0] (exit 0, not 2)
  [PASS] fail-open on garbage[1] (exit 0, not 2)
  [PASS] fail-open on garbage[2] (exit 0, not 2)
  [PASS] fail-open on garbage[3] (exit 0, not 2)
  [PASS] fail-open on garbage[4] (exit 0, not 2)
  [PASS] opt-out env disables the gate (exit 0)
  [PASS] fail-open on broken tripwire.py (exit 0, not 2)

CHAOS-PASS: gate blocks the dangerous op, allows benign ops, and fails open

```

## Spec (provenance)

```json
{
  "name": "no-force-push",
  "event": "pretooluse",
  "action": "Tripwire: refusing git push --force. Force-push can destroy remote history; AGENTS.md section 9 requires explicit user approval. If approved, re-run with FORGE_NO_FORCE_PUSH_OFF=1.",
  "trigger_kind": "command",
  "trigger_regex": "git\\s+push\\b[^\\n]*(--force\\b|-f\\b)",
  "fire_example": "git push --force origin main",
  "silent_example": "git push origin main",
  "skill_description": "Use when the no-force-push tripwire blocks a git push --force; confirms whether the user explicitly approved a history-rewriting force-push before overriding.",
  "gates": true,
  "has_procedure": true,
  "needs_state": false,
  "case_sensitive": false,
  "trigger_field": null,
  "matcher": null
}
```
