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
| `resource-guard.ps1` | `~/scripts/` | Recurring task `Resource-Guard` | cgroup-style fleet memory-governor: samples RAM / C: / MCP-duplication signals and surfaces a digest line. Also drives `cursor-orphan-reaper.ps1` as a **report-only** micro-guard (`-ReapOrphanCursorAgents` to enable apply). LOG-and-surface; never kills an essential. |
| `cursor-orphan-reaper.ps1` | `~/.agents/scripts/agentic-perfection/` | called by `resource-guard.ps1` (and reused by the process-hygiene supervisor) | High-risk micro-guard: terminates ONLY an exact Cursor Agent `node.exe` process tree after dead-parent + age + whole-tree-idle + repeated-observation + per-PID identity-revalidation checks. Never kills by name, never `taskkill /T`; fail-closed. |
| `test-cursor-orphan-reaper.ps1` | (run from repo) | — | Regression test for the reaper, incl. a real disposable-sleeper kill and the report-only/apply confirmation ladder. |

> The estate-wide **process-hygiene supervisor** (`tools/process-hygiene-supervisor/`,
> design in [`docs/plans/2026-09-02-process-hygiene-supervisor.md`](../../docs/plans/2026-09-02-process-hygiene-supervisor.md))
> is the superset governor: it delegates cursor-agent orphans to this reaper and
> MCP verdicts to `mcp_fleet_supervisor`, rather than duplicating either.

Runtime artifacts (`*.log`, `*.state.json`) are regenerated and are intentionally
**not** versioned. No secrets: these scripts use paths and env vars only.

See [`../../docs/agentic-perfection/CHANGELOG.md`](../../docs/agentic-perfection/CHANGELOG.md)
for how these fit the wider program.
