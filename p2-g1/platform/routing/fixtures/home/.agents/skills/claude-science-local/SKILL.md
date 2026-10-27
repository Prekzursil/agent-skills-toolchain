---
name: claude-science-local
description: Use to bring up, diagnose, or recover Anthropic's Claude Science local compchem / life-science workbench - a WSL2 daemon on 127.0.0.1:8000. Triggers - claude science, compchem or life-science workbench, :8000 down or unreachable, cs open, start claude science, science daemon wedged or off, open the science UI. Teaches the cs verbs (open, ensure, status, fix, doctor, backup, restore), why HTTP 401 means alive, the host-RAM SQLite wedge and that cs fix recovers it, cs ensure before any :8000 call, and that scope is LOCAL only.
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

### Standard flow
### `cs doctor` — what it checks
### Gotchas
### Adding data sources (brief)
