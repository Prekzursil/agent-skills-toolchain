---
name: claude-science-local
description: Use to bring up, diagnose, or recover Claude Science, Anthropic's local compchem / life-science workbench - a WSL2 daemon on 127.0.0.1:8000. Triggers - claude science, compchem/life-science workbench, :8000 down, cs open/status/fix/doctor/ensure, science daemon wedged. Teaches why HTTP 401 means alive, the host-RAM SQLite wedge that cs fix recovers, and cs ensure before any :8000 call.
license: MIT
---

# Claude Science (local) — one-command control

> Anthropic's **Claude Science** compchem / life-science workbench has **no
> Windows build**. It runs as a **WSL2 Ubuntu daemon** serving a web UI on
> **`http://127.0.0.1:8000/`**. The `cs` dispatcher makes it always-on and
> one-command from any Windows shell. **LOCAL only** — no remote/Tailscale.

## When to use

- "Start / open Claude Science", "the science UI is down", "`:8000` won't load".
- Before another tool or agent calls `:8000` — run `cs ensure` first.
- The daemon is **wedged** (up but slow/timing out) or **off when needed**.
- You need a health readout, a recover, or a backup/restore of the science DB.

## Two facts that flip every diagnosis

1. **HTTP 401 on `/` = ALIVE.** `:8000` is behind an auth gate; a 401 (even a
   403) means the daemon is answering. Do **not** read 401 as "down".
2. **Slow / timeout = WEDGED, not down.** The daemon accepts the socket but
   answers slowly or never. Root cause: the WSL VM is frozen under **host-RAM
   pressure**, which stalls the SQLite `operon-cli.db` (lock contention — seen up
   to a 164 s `TxMutex` hold). A naive "any HTTP response = healthy" probe is
   blind to this. `cs` is **latency-aware**: a response `>= 4 s` reads as
   **WEDGED**, and `cs fix` recovers it.

## The `cs` verbs (run from PowerShell)

```
pwsh -File ~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1 <verb>
```

| Verb | What it does |
|---|---|
| **`cs open`** | Ensure up (start-if-down / recover-if-wedged), **wait for readiness** (not a blind sleep), then open the UI in the browser. The human one-click. |
| **`cs ensure`** | Headless ensure-up for **tools/agents** — emits `SUCCESS:cs-up` / `FAILED:cs-down` (exit 0/1). **Call this before any `:8000` request.** |
| **`cs status [-Json]`** | State + measured **latency** + a `wedged` flag (+ WSL daemon detail). `-Json` for machine parsing. |
| **`cs fix`** | Graceful force-recover: stop → clear stale locks (`daemon.sock`/`operon.lock`/`sbx-*`) → restart pinned. The wedge cure. (alias: `cs recover`.) |
| **`cs stop`** | Stop the daemon. |
| **`cs backup`** | Online SQLite snapshot to `D:\Backups\claude-science` (key stored separately; keeps last 7). Safe while the daemon is up. |
| **`cs restore <ts\|latest>`** | Roll back to a snapshot (keeps a pre-restore safety copy, drops stale WAL/SHM, restarts, verifies). |
| **`cs doctor`** | Full-stack **PASS/WARN/FAIL** report — the go-to when something is off. |

## Standard flow

- **Human wants the UI:** `cs open`. Done.
- **A tool/agent needs `:8000`:** `cs ensure`; proceed only on `SUCCESS:cs-up`.
- **"It's off / slow when I need it":** `cs status`. If `*** WEDGED ***` or DOWN →
  `cs fix` → re-`cs status`. If it won't come back → `cs doctor`.

## `cs doctor` — what it checks

A read-only report that operationalizes the reliability audit. Rows (each
PASS/WARN/FAIL/INFO): **WSL reachable** · **CS daemon** (state + latency, flags
`*** WEDGED ***`) · **daemon detail** (pid/version/uptime) · **DB** (integrity +
`journal_mode` + size) · **WSL disk free** · **Host RAM free** + top consumers
(the freeze root cause) · **Watchdog registered** · **Watchdog instances**
(catches the duplicate-watchdog race) · **Watchdog heartbeat** (catches a hung
watchdog) · **Backup freshness** · **Tab-death regfix**. Ends with a
`N FAIL, N WARN, N PASS` summary; on any FAIL it suggests `cs fix` then re-run.

## Gotchas

- **Wedge ≠ crash.** The daemon rarely crashes; the usual failure is the RAM/
  SQLite **wedge**. If `:8000` is slow, don't restart WSL blindly — `cs fix`
  clears the locks and restarts cleanly.
- **Host-RAM pressure is the trigger.** If `cs doctor` shows low host RAM, the
  heavy neighbours (BOINC / LM Studio / Docker / a Claude fleet) are starving the
  VM. Free RAM, then `cs fix`.
- **A backup you can't restore is false safety.** `cs backup` and `cs restore`
  are matched — take a `cs backup` before risky changes; `cs restore latest`
  rolls back.
- **Scope is LOCAL.** Remote access / Tailscale (`cs-tailscale-serve.ps1`) is out
  of scope here — `cs` targets `127.0.0.1:8000` only.

## Adding data sources (brief)

MCP connectors are added **in the web UI only** (Customize → Connectors),
**URL/HTTP transport only** — the WSL daemon can't reach Windows stdio MCPs
directly. For the NVIDIA BioNeMo NIM compute connector and the full lifecycle
details, see `scripts/claude-science/README.md`.
