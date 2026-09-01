# scripts/agentic-perfection/

Canonical copies of the host-side scripts in the *agentic-perfection* program's
**anticipatory layer** and **basic-memory infra fixes**. These are versioned for
durability + restore; they deploy to fixed home locations and run from **Scheduled
Tasks**, so — unlike the hook tree — they are **not** copied by `sync-hooks.ps1`.
Deploy them manually to the paths below (and register the Scheduled Tasks) when
restoring a machine.

| Script | Deploy to | Wiring | Purpose |
|--------|-----------|--------|---------|
| `bm-http-server.ps1` | `~/.basic-memory/` | Logon task `BasicMemory-HTTP-MCP` | Shared basic-memory streamable-HTTP launcher on `127.0.0.1:8765` — ONE process for all sessions. Hardened: lockfile mutex over the start+bind window, port-in-use idempotent skip, kill-stale + socket-release. Fixes the `[Errno 10048]` flapping. |
| `bm-watchdog.ps1` | `~/.basic-memory/` | Recurring task (every few min) | Keep-alive: if `:8765` isn't serving, restart via the hardened launcher. LOG + restart only; never touches a live server; fail-open. |
| `world-watch.ps1` | `~/scripts/` | Daily task `World-Watch` | Fingerprints each watcher in `world-watch.yaml`; appends a `BACKGROUND-DIGEST` line ONLY on change (first run records a baseline silently). The "while you were away" producer; the `background-digest` hook is the consumer. |
| `world-watch.yaml` | `~/scripts/` | (read by `world-watch.ps1`) | Curated watch list: BC app-version bump (offset/HGT risk), upstream repos that clobber local patches (HexStrike / BCSFE / tbcml / insta-mcp). External signals only. |
| `test-world-watch.ps1` | `~/scripts/` (or run from repo) | — | Regression test for the watcher fingerprinting + fail-open behaviour. |
| `resource-guard.ps1` | `~/scripts/` | Recurring task `Resource-Guard` | Samples RAM/disk/MCP pressure and invokes `cursor-orphan-reaper.ps1`. With the explicit reap switch, only a twice-observed, aged, whole-tree-idle Cursor Agent whose parent is absent can be terminated; never kills by name. |
| `cursor-orphan-reaper.ps1` | `~/scripts/` | Called by `Resource-Guard` | High-risk micro-guard with metadata snapshot, PID+creation identity, dead-parent check, whole-tree CPU-idle check, two-observation grace, exact tree kill, and survivor verification. |

Runtime artifacts (`*.log`, `*.state.json`) are regenerated and are intentionally
**not** versioned. No secrets: these scripts use paths and env vars only.

See [`../../docs/agentic-perfection/CHANGELOG.md`](../../docs/agentic-perfection/CHANGELOG.md)
for how these fit the wider program.
