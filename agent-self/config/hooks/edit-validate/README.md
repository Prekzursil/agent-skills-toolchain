---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/config/hooks/edit-validate/readme
---

# edit-validate — Stop-time file validator (loop-proof successor to async-validate)

Replaces the old `async-validate` hook (deep-research #4), whose per-Edit
`asyncRewake` design caused a **degenerate wake-loop** in a workflow session:
it re-ran ruff on *every* edit and woke the main session on each transient
ruff-dirty WIP state — thousands of wakes. (Diagnosed + paused via a `.disabled`
sentinel by the session that hit it; this is the permanent fix.)

## Design

Two hooks, validation moved to the **turn boundary**:

- **`record.py`** — PostToolUse(Edit|Write|MultiEdit). Appends the edited file
  path to a per-session list (`%TEMP%/edit-validate/<session>.edits`). Does NO
  validation and NEVER wakes Claude → cannot loop. Near-zero cost.
- **`validate-stop.py`** — Stop hook. Validates the files edited this turn
  **once** (`py_compile` + `ruff` for .py, `node --check` for .js, `json.load`
  for .json). If a file is genuinely broken, emits a one-shot `decision: block`
  nudging a fix.

## Why it cannot wake-loop (three independent guards)

1. **Boundary, not per-edit** — fires once per turn. A turn with 1 edit or 1000
   edits triggers exactly ONE validation pass.
2. **Per-(file,error) dedupe** — a given breakage is nudged at most once per
   session (`<session>.warned`); the same error never re-blocks.
3. **`stop_hook_active` guard** — never blocks during a stop-continuation, so any
   chain is capped at a single extra turn.

Validates the *finished* batch, not half-written mid-edit WIP → far fewer false
alarms than per-edit.

## Opt-outs / fail-open

- `STOP_VALIDATE=off` env, or a `.disabled` sentinel file in this dir.
- Any internal error → exit 0 (silent). Never false-alarms on its own bugs.

## Migration note

The old `~/.claude/hooks/async-validate/` dir is now **unregistered/superseded**
but left on disk (its `.disabled` sentinel is managed by another session's
running workflow). Once that workflow finishes, `async-validate/` + its
`.disabled` can be deleted.