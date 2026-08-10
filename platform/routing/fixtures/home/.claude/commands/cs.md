---
description: One-command control for the local Claude Science WSL2 workbench (127.0.0.1:8000). Shells to the cs dispatcher - open, status, fix, doctor, ensure, stop, backup, restore.
---

# cs — Claude Science (local) control

Bring up, diagnose, or recover Anthropic's **Claude Science** compchem / life-science
workbench — a WSL2 daemon serving `http://127.0.0.1:8000/`. **LOCAL only.**

## Usage

```
/cs [open|status|fix|doctor|ensure|stop|backup|restore <ts|latest>]
```

- `open` — ensure up (start-if-down / recover-if-wedged, wait for readiness) then open the UI. The one-click.
- `status` — state + latency + a `wedged` flag (add `-Json` for machine output). **Default when no verb is given.**
- `fix` — graceful force-recover (clears stale locks, restarts). The wedge cure.
- `doctor` — full-stack PASS/WARN/FAIL health report.
- `ensure` — headless ensure-up for tools/agents → `SUCCESS:cs-up` / `FAILED:cs-down`.
- `stop` · `backup` · `restore <ts|latest>` — daemon stop / online SQLite snapshot / rollback.

$ARGUMENTS

## What to Do

Shell to the dispatcher, passing `$ARGUMENTS` through as the verb (and any trailing
