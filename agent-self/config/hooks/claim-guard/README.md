---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/config/hooks/claim-guard/readme
---

# claim-guard — Claim/Evidence Hook Pair

Mechanizes the "NEVER self-certify" / anti-sycophancy rule from `AGENTS.md`:

> A PostToolUse hook records every Bash command + its exit status to an on-disk
> NDJSON ledger; a Stop hook scans the assistant's final response for unverified
> success-claims and, if a claim has NO supporting successful command in the
> ledger this turn, INJECTS a warning.

## Files

| File | Hook event | Purpose |
|------|-----------|---------|
| `ledger-write.py` | PostToolUse (matcher: `Bash`) | Appends `{ts, cmd, exit, ok, turn}` records to the per-session ledger |
| `ledger-write.py` | PostToolUse (matcher: `Bash\|PowerShell`) | Appends `{ts, cmd, exit, ok}` records to the per-session ledger |
| `claim-check.py` | Stop (no matcher) | Parses the final assistant response; warns if claims lack evidence |

## Turn scoping (why the ledger is not just per-session)

The ledger FILE is per session, but the contract above says evidence **this
turn**. A session spans many turns, so session scope alone let a receipt vouch
for a later turn that ran nothing: turn 1 runs `pytest -q` successfully, turn 2
runs no tests and says "Tests pass.", and the checker stayed silent because the
turn-1 record was still in the file.

`claim-check.py` therefore appends a `{"turn_end": true}` boundary marker at the
end of **every** Stop that is not a `stop_hook_active` continuation — including
the silent paths, since a turn that made no claim still consumed its receipts —
and `_load_ledger` returns only the records written after the last marker.
`ledger-write.py` stamps each receipt with `turn`, the number of markers that
preceded it, so a record carries its own turn identity.

## Behavior

### ledger-write.py (PostToolUse)
- Fires after every shell tool call (`Bash` and `PowerShell` — PowerShell is a
  first-class shell here, and dropping it left the Stop consumers reading an empty
  ledger and calling real evidence "never run")
- Extracts the command string and exit code from the tool payload
- Appends a JSON record to the session ledger
- Completely silent (record-only, never injects text)
- FAIL-OPEN: any error → silent exit 0

### claim-check.py (Stop)
- Fires when Claude finishes a turn
- Parses the final assistant message from the session transcript JSONL
- Detects assertive (non-hedged) success-claim phrases:
  - **tests** — "tests pass", "tests passing", "all tests pass", "test suite passes"
  - **build** — "build succeeds", "build passes", "builds successfully", "build is green"
  - **lint** — "lint passes", "lint is clean", "no linting errors"
  - **coverage** — "coverage met", "coverage passes", "meets the coverage"
  - **fixed** — "is fixed", "has been fixed", "the bug is now fixed"
  - **all_green** — "all green", "all checks are green", "everything's passing"
  - **no_errors** — "no errors found", "zero errors"
- Cross-references each claim category against the ledger:
  - `tests` → requires a `pytest`/`jest`/`go test`/`npm test`/... command with `ok=true`
  - `build` → requires `tsc`/`cargo build`/`npm run build`/... with `ok=true`
  - `lint` → requires `eslint`/`ruff`/`flake8`/... with `ok=true`
  - `fixed`/`all_green`/`no_errors` → ANY `ok=true` command suffices
- If unsupported claims exist → emits ONE `additionalContext` warning (exit 0)
- If all claims are supported or no claims found → completely silent
- FAIL-OPEN: any error → silent exit 0

## False-positive controls

- **Hypothetical hedge suppression**: phrases like "should pass", "would pass",
  "expected to", "once you run", "looks like it might" within ±120 chars of the
  match suppress the warning. Only assertive past/present-tense claims trigger it.
- **Conservative exit-code inference**: when the ledger cannot determine ok/fail
  with confidence, it defaults to `ok=true` to avoid false "unverified" warnings.
- **Word-boundary anchors**: all patterns use `\b` to avoid false matches
  (e.g. "fixed" in "as-fixed" will not match).

## Ledger location

```
%TEMP%\claude-claim-ledger\<session_id>.ndjson
```

On Windows: typically `C:\Users\<user>\AppData\Local\Temp\claude-claim-ledger\`

**This directory is gitignore-safe** — it lives in the system temp directory,
not inside any repository. No `.gitignore` changes are needed.

Each line is a JSON record:
```json
{"ts": "2026-06-15T10:23:01Z", "cmd": "pytest tests/", "exit": 0, "ok": true}
```

### Override via environment variable

```
CLAIM_GUARD_LEDGER_ROOT=C:\path\to\custom\ledger\dir
```

## Mode control

Set `CLAIM_GUARD_MODE` in the environment or in `settings.json` → `env`:

| Value | Behavior |
|-------|---------|
| `warn` (default) | Injects `additionalContext` warning; exit 0 |
| `off` | Completely disabled — both hooks exit silently |
| `block` | Stub reserved for future escalation (currently falls through to warn) |

## settings.json registration

Add these two blocks to your `settings.json` `hooks` section:

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Bash|PowerShell",
      "hooks": [
        {
          "type": "command",
          "command": "python C:/Users/Prekzursil/.claude/hooks/claim-guard/ledger-write.py",
          "timeout": 5,
          "statusMessage": "Claim-guard: recording shell result to ledger"
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "python C:/Users/Prekzursil/.claude/hooks/claim-guard/claim-check.py",
          "timeout": 10,
          "statusMessage": "Claim-guard: checking for unverified success claims"
        }
      ]
    }
  ]
}
```

**Important**: the existing `Stop` hook for the event-ledger (`stop-hook.py`) runs
as a separate entry in the `Stop` array. These hooks COEXIST — do not replace the
existing entry. The `Stop` array should contain both:

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python C:/Users/Prekzursil/.claude/hooks/event-ledger/stop-hook.py",
        "timeout": 10,
        "statusMessage": "Recording turn to event-ledger"
      }
    ]
  },
  {
    "hooks": [
      {
        "type": "command",
        "command": "python C:/Users/Prekzursil/.claude/hooks/claim-guard/claim-check.py",
        "timeout": 10,
        "statusMessage": "Claim-guard: checking for unverified success claims"
      }
    ]
  }
]
```

## Design notes

- **Coexistence**: claim-check.py is a separate Stop hook entry — it does NOT
  replace or modify the existing `stop-hook.py` event-ledger hook.
- **Anti-loop**: both hooks check `stop_hook_active` (Stop) and fail gracefully
  if the payload is malformed.
- **Windows compatibility**: all file I/O uses `encoding="utf-8", errors="replace"`.
  Python 3 is used throughout (`#!/usr/bin/env python3`).
- **No external dependencies**: stdlib only (json, re, os, sys, tempfile, pathlib).