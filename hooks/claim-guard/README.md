# claim-guard — Claim/Evidence Hook Pair

Mechanizes the "NEVER self-certify" / anti-sycophancy rule from `AGENTS.md`:

> A PostToolUse hook records every Bash command + its exit status to an on-disk
> NDJSON ledger; a Stop hook scans the assistant's final response for unverified
> success-claims and, if a claim has NO supporting successful command in the
> ledger this turn, INJECTS a warning.

## Files

| File | Hook event | Purpose |
|------|-----------|---------|
| `ledger-write.py` | PostToolUse (matcher: `Bash`) | Appends `{ts, cmd, exit, ok}` records to the per-session ledger |
| `claim-check.py` | Stop (no matcher) | Parses the final assistant response; warns if claims lack evidence |

## Behavior

### ledger-write.py (PostToolUse)
- Fires after every Bash tool call
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
  - **ci_gates** — "CI is green", "gates are green", "ready to merge", "PR is green"
  - **functional** (G1) — assertive PRODUCT "it works now" claims: "the app works",
    "shorts generate", "the button works now", "feature is working", "end to end
    works", "the flow works", "it now produces/renders", "works as expected"
- Cross-references each claim category against the ledger:
  - `tests` → requires a `pytest`/`jest`/`go test`/`npm test`/... command with `ok=true`
  - `build` → requires `tsc`/`cargo build`/`npm run build`/... with `ok=true`
  - `lint` → requires `eslint`/`ruff`/`flake8`/... with `ok=true`
  - `ci_gates` → requires a real remote-CI query (`gh pr checks`/`gh run view`/...)
  - `fixed`/`all_green`/`no_errors` → ANY `ok=true` command suffices
  - **`functional` → HIGHER, EXTERNAL bar (G1):** a generic unit-test pass does
    NOT satisfy it. It requires an `ok=true` command matching an **e2e / acceptance
    signature** — `playwright`, `cypress`, `e2e`, `golden` (golden-journey),
    `acceptance`, `nightwatch`, `webdriver`, `testcafe` — i.e. proof the product
    actually ran end to end this turn. The signature list is a small, commented
    constant (`_E2E_SIGNATURES`) that is easy to extend; add per-project
    produced-artifact signatures via the `CLAIM_GUARD_E2E_EXTRA` env var
    (comma-separated substrings, e.g. `media_studio,render_shorts`).
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
| `warn` (default) | Injects `additionalContext` warning; exit 0. Unchanged from before. |
| `off` | Completely disabled — both hooks exit silently |
| `block` | **Narrow, real block (G1):** an UNSUPPORTED `functional` ("it works now") claim exits **2** (blocks the Stop, feeds the reason to stderr). Every OTHER category — and any exception — still only warns (exit 0), so nothing that worked before starts blocking. Fail-open on any error. |

### Environment variables (G1)

| Variable | Purpose |
|----------|---------|
| `CLAIM_GUARD_E2E_EXTRA` | Comma-separated substrings added to the `functional` e2e-evidence signature list (e.g. `media_studio,render_shorts`) so a project's produced-artifact commands count as acceptance evidence. |

## settings.json registration

Add these two blocks to your `settings.json` `hooks` section:

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python C:/Users/Prekzursil/.claude/hooks/claim-guard/ledger-write.py",
          "timeout": 5,
          "statusMessage": "Claim-guard: recording Bash result to ledger"
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
