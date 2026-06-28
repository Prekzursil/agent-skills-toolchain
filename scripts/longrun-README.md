# longrun — long-operation wrapper with heartbeat + terminal markers

`longrun.ps1` (Windows/PowerShell) and `longrun.sh` (bash) wrap a command
whose lifecycle you want to observe without blocking the agent session.  
They replace the anti-pattern `cmd | tail -f` (synchronous, floods output)
with a clean model: **raw output → log file; one heartbeat line per interval
to the notification stream; a terminal marker on exit.**

---

## Why this exists

The user's single biggest friction in long agent sessions is the
"are you still running or stuck?" polling loop. Empirically (Codex CLI data):
~94 turns/81 sessions; 165 turn-aborts/133 sessions just to read status.

`longrun` eliminates that by:
1. Printing a **stable log path** before launch (stop-and-report can always
   read it).
2. Emitting a **one-line heartbeat** (`⏳ <id>: <elapsed>s | <last log line>`)
   every N seconds — easily distinguishable noise on a Monitor stream.
3. Terminating with a **machine-readable marker** (`SUCCESS:<id>` or
   `FAILED:<id> exit=<code> :: <reason>`) that agent harnesses parse
   deterministically.
4. Optionally **killing the process tree** if no new output appears for
   `HangTimeoutSec` seconds (detects a hung test runner, silent deadlock, etc.).

---

## Marker format

```
SUCCESS:<id> (<elapsed>s)
FAILED:<id> exit=<code> :: <last non-empty stderr/stdout line>
FAILED:<id> exit=HANG :: hung for <N>s with no output | last: <line>
```

The `<id>` is always the first token after the colon — regex `^(SUCCESS|FAILED):(\S+)`.

---

## PowerShell usage (`longrun.ps1`)

Pass the executable via `-Cmd`. All arguments to the wrapped command go
**positionally after** `-Cmd <value>` — PowerShell's `ValueFromRemainingArguments`
captures them (including dashed flags like `-NoProfile`) without confusing them
with longrun.ps1's own named parameters.

```powershell
# Via pwsh -File (flat string / run_in_background):
pwsh -File .\longrun.ps1 -Id dotnet-test -HeartbeatSec 10 -Cmd dotnet test --no-build

# Hang-kill: fail if silent for 120s, heartbeat every 20s:
pwsh -File .\longrun.ps1 -Id jest-coverage -HeartbeatSec 20 -HangTimeoutSec 120 -Cmd npx jest --coverage

# Inline loop test — 5 steps x 2s, heartbeat every 3s:
pwsh -File .\longrun.ps1 -Id loop-test -HeartbeatSec 3 -Cmd pwsh -NoProfile -Command "foreach (`$i in 1..5) { Write-Host 'step'; Start-Sleep 2 }"
```

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `-Cmd` | (required) | Executable or script to run |
| `-Id` | Cmd basename | Label in all output lines |
| `-HeartbeatSec` | `15` | Interval between heartbeat lines |
| `-HangTimeoutSec` | `0` (off) | Kill + FAILED if silent for N seconds |
| `-LogDir` | `$env:TEMP` | Directory for log files |

Three log files are created per run:
- `longrun-<id>-<stamp>-stdout.log`
- `longrun-<id>-<stamp>-stderr.log`
- `longrun-<id>-<stamp>-merged.log` (tagged `[OUT]`/`[ERR]` lines, chronological)

All three paths are printed to stdout **before launch** — they are valid
even if the launch fails.

---

## Bash usage (`longrun.sh`)

```bash
# Basic:
./longrun.sh -i dotnet-test -- dotnet test --no-build

# Hang-kill + heartbeat:
./longrun.sh -i jest-coverage -h 20 -t 120 -- npx jest --coverage

# Inline test:
./longrun.sh -i loop-test -h 3 -- bash -c \
    'for i in 1 2 3 4 5; do echo "step $i"; sleep 2; done'
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `-i / --id` | command basename | Label |
| `-h / --heartbeat-sec` | `15` | Heartbeat interval (seconds) |
| `-t / --hang-timeout-sec` | `0` (off) | Hang-kill threshold |
| `-d / --log-dir` | `$TMPDIR` or `/tmp` | Log directory |

Two log files are created per run (stdout and stderr, printed before launch).
`stdbuf` is used if present (line-buffered output); the script falls back
gracefully when absent (Git Bash, minimal Alpine, etc.) — writing directly
to files is already unbuffered enough for heartbeat visibility.

---

## How to stream heartbeats via run\_in\_background + Monitor

The intended pattern is:

```
# 1. Launch in background — Bash tool:
#    run_in_background=True
#    command = "pwsh -File C:\\...\\longrun.ps1 -Id jest -HeartbeatSec 15 -Cmd npx jest --coverage"

# 2. Each heartbeat line becomes a notification event in Monitor:
#    ⏳ jest: 15s | Test Suites: 3 passed

# 3. Terminal marker signals completion:
#    SUCCESS:jest (47s)
#    — or —
#    FAILED:jest exit=1 :: ● Test suite failed to run
```

The Monitor tool surfaces each stdout line of the background process as a
separate notification. `longrun` keeps that stream minimal:
- Lines **before** the command starts: 4 lines (id, 3 log paths)
- Lines **during**: one per heartbeat interval
- Lines **at end**: exactly one terminal marker

No raw command output floods the notification channel.

---

## Stop-and-report convention

When you need to inspect the full output or detect changed files mid-run
or after completion:

1. **Log path is always known** — it was printed at the start of the run
   (save it, or search `$env:TEMP\longrun-<id>-*.log`).
2. **Last N lines of merged log:**
   ```powershell
   Get-Content "$env:TEMP\longrun-jest-20260615-143022-merged.log" -Tail 30
   ```
3. **Changed files since run start** (e.g. after test coverage wrote reports):
   ```powershell
   Get-ChildItem -Recurse -File | Where-Object LastWriteTime -GT (Get-Date).AddSeconds(-60)
   ```
4. A "stop-and-report" action does **not** require the process to still be
   running — the log file persists after exit.

---

## Codex mirror note

The same discipline applies to long Codex CLI generations via
`codex-cli-runtime`. Wrap codex invocations that are expected to run >60s
with `longrun` (or the equivalent `run_in_background` + `Monitor` primitives
baked into the runtime skill) so generations stream heartbeats rather than
blocking the parent session. The terminal `SUCCESS/FAILED` marker integrates
directly with the `codex-result-handling` skill's marker-parsing step.

---

## Exit codes

| Code | Meaning |
|---|---|
| Command's own code | Passed through unchanged on normal exit |
| `1` | `longrun` itself failed to launch the command |
| `124` | Hang-timeout: command killed for silence |
