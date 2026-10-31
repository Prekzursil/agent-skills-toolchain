---
title: README
type: note
permalink: dqverify-repo-20261013/hooks/stopfailure-notify/readme
---

# stopfailure-notify

A Claude Code `StopFailure` hook that **logs API errors to a file and fires a
non-blocking Windows balloon notification** so unattended overnight runs don't
fail silently.

---

## What it does

When Claude Code terminates a turn due to an API error (rate limit, overload,
billing, server error, etc.) the hook:

1. **Appends a timestamped line** to a log file so you can correlate stalls
   with the 5-hour quota window:

   ```
   2026-06-15T02:34:11 StopFailure: rate_limit | msg='Rate limit exceeded. Retry after 60s.' | model=claude-sonnet-4-6 | turn=17 | cwd=C:\my-project | session=abc123456789abcd
   ```

2. **Fires a Windows desktop balloon notification** (non-blocking, auto-dismisses
   after ~9 seconds) in the system tray — visible even when the terminal window
   is minimized.

The hook is **fire-and-forget**: `StopFailure` ignores exit codes and stdout, so
every path is wrapped in `try/except` and exits 0. It cannot hang or crash your
session.

---

## Files

```
hooks/stopfailure-notify/
├── notify.py    # the hook script
└── README.md    # this file
```

---

## Log file location

| Priority | Path |
|----------|------|
| 1st | `STOPFAILURE_LOG` env var (explicit override) |
| 2nd | `%TEMP%\claude-stopfailure.log` (default on Windows) |
| 3rd | `~/.claude/event-ledger/stopfailures.log` (fallback) |

---

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `STOPFAILURE_NOTIFY` | `1` | Set to `0` to silence the balloon notification (log still written) |
| `STOPFAILURE_LOG` | *(see above)* | Override the log file path |
| `EVENT_LEDGER_ROOT` | `~/.claude/event-ledger` | Affects fallback log location only |

---

## settings.json registration

Add a `StopFailure` entry to the `hooks` section of
`~/.claude/settings.json`.

### Form 1 — catch ALL API errors (recommended for unattended runs)

```json
{
  "hooks": {
    "StopFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python C:/Users/Prekzursil/.claude/hooks/stopfailure-notify/notify.py",
            "timeout": 15,
            "statusMessage": "StopFailure: logging error + notifying"
          }
        ]
      }
    ]
  }
}
```

> Omitting the `matcher` field means all `error_type` values are matched.

### Form 2 — match only the "interesting" runtime errors (rate limit, overload, billing, server)

```json
{
  "hooks": {
    "StopFailure": [
      {
        "matcher": "rate_limit|overloaded|billing_error|server_error",
        "hooks": [
          {
            "type": "command",
            "command": "python C:/Users/Prekzursil/.claude/hooks/stopfailure-notify/notify.py",
            "timeout": 15,
            "statusMessage": "StopFailure: logging error + notifying"
          }
        ]
      }
    ]
  }
}
```

### Full `error_type` enum (from docs)

| Value | Meaning |
|-------|---------|
| `rate_limit` | Per-minute or per-day token rate exceeded |
| `overloaded` | API servers temporarily at capacity |
| `authentication_failed` | API key rejected |
| `oauth_org_not_allowed` | OAuth org restriction |
| `billing_error` | Account billing issue / credit exhausted |
| `invalid_request` | Malformed request (bad params, context too large) |
| `model_not_found` | Model ID not available |
| `server_error` | Internal API server error |
| `max_output_tokens` | Response hit output token limit |
| `unknown` | Unclassified error |

---

## StopFailure payload (stdin JSON)

```json
{
  "session_id": "abc123",
  "transcript_path": "C:/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "C:/my-project",
  "hook_event_name": "StopFailure",
  "error_type": "rate_limit",
  "error_message": "Rate limit exceeded. Please retry after 60 seconds.",
  "model": "claude-sonnet-4-6",
  "turn_number": 17
}
```

---

## Notes

- `StopFailure` hooks cannot block or modify behavior — output and exit code are
  ignored by Claude Code. This hook is purely observability.
- The balloon notification uses `System.Windows.Forms.NotifyIcon` (part of the
  .NET Framework GAC on every Windows 10/11 machine) — no extra modules needed.
- The PowerShell process is spawned detached (`DETACHED_PROCESS | CREATE_NO_WINDOW`)
  so `notify.py` returns immediately and never blocks the hook timeout.
- If PowerShell is unavailable or the spawn fails, the hook falls back to log-only
  (fail-open).