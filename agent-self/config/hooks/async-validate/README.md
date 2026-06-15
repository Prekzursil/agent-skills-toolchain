# async-validate — background file validator hook

## What it does

`validate.py` is a **PostToolUse** hook that runs a fast, language-appropriate
correctness check on every file that `Edit` or `Write` touches.

It is registered with **`asyncRewake: true`** so it runs *off the critical path* —
Claude never waits for it.  The hook is truly invisible on the happy path: it
exits 0 silently, adding zero perceived latency to every edit.  The only time it
interrupts work is when a file is actually broken.

### Language dispatch

| Extension         | Check                                                             |
|-------------------|-------------------------------------------------------------------|
| `.py`             | `python -m py_compile` (syntax) + `ruff check` if available      |
| `.js` `.mjs` `.cjs` | `node --check` (V8 parser)                                      |
| `.ts` `.tsx`      | **Skipped** — `tsc --noEmit` is project-wide and too slow/noisy for edit-time; wire a fast per-file TS parser here if you have one |
| `.json`           | `json.load` in-process (no subprocess overhead)                   |
| anything else     | Exit 0 — not applicable                                           |

### Opt-out

Set `ASYNC_VALIDATE=off` in your environment or in `settings.json` `env` block
to disable completely without unregistering the hook.

---

## The asyncRewake mechanism (verified from docs)

Source: <https://docs.claude.com/en/docs/claude-code/hooks>

> **`asyncRewake`** — If `true`, runs in the background and **wakes Claude on
> exit code 2**.  Implies `async`.  The hook's stderr (or stdout if stderr is
> empty) is shown to Claude as a **system reminder** so it can react to a
> long-running background failure.

### Exit-code contract

| Exit code | Meaning                                                        |
|-----------|----------------------------------------------------------------|
| `0`       | Success (or not applicable, or internal error — fail-open).   |
| `2`       | Validation failure. CC surfaces `stderr` to Claude as a system reminder and wakes it so it can react. |
| other     | Non-blocking error (not used by this hook).                   |

### How the async wake works

```
  Claude issues Edit ──► CC runs hook in BACKGROUND ──► validate.py starts
         │                                                        │
         ▼                                                        ▼
  Claude continues                                    (file is valid)
  working normally                                     exit 0 — SILENT
                                                                  │
                                                     (file has error)
                                                       exit 2 + stderr
                                                                  │
                                                                  ▼
                                                   CC wakes Claude:
                                                   system reminder =
                                                   "[async-validate] foo.py:
                                                    invalid syntax (line 12)"
                                                                  │
                                                                  ▼
                                                   Claude sees the reminder
                                                   and fixes the file
```

The key property: **the happy path is zero-cost**.  Only failures interrupt.

---

## Exact settings.json registration block

Add this entry inside `hooks.PostToolUse` in
`~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "matcher": "Edit|Write",
  "hooks": [
    {
      "type": "command",
      "command": "python C:/Users/Prekzursil/.claude/hooks/async-validate/validate.py",
      "asyncRewake": true,
      "statusMessage": "Async file validator (background)"
    }
  ]
}
```

> **Note:** `asyncRewake: true` implies `async: true` — you do not need both.
> No `timeout` is needed because the hook is fully async; CC does not block on it.
> The `statusMessage` is shown only briefly at hook launch (if at all), since the
> hook does not block the UI.

---

## Wiring heavier gates the same way

Any long-running check that has a clear pass/fail signal can use this pattern:

```json
{
  "matcher": "Edit|Write|Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python C:/Users/Prekzursil/.claude/hooks/your-gate/check.py",
      "asyncRewake": true,
      "statusMessage": "Running heavy gate in background"
    }
  ]
}
```

Examples of heavier gates that fit naturally here:
- **Full coverage check** — run `pytest --cov` after any `.py` edit; exit 2 if
  coverage drops below threshold.
- **SAST scan** — run `semgrep` or `bandit` on the edited file; exit 2 on
  HIGH-severity findings.
- **Secret scan** — run `gitleaks detect` or `trufflehog`; exit 2 if a secret
  pattern matches the new content.
- **Build validation** — run `tsc --noEmit` or `cargo check` after a batch of
  edits; exit 2 if the build is broken.

The contract is always the same: **exit 0 = silent, exit 2 = stderr wakes Claude**.
