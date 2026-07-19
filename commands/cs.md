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
argument, e.g. a restore timestamp). If `$ARGUMENTS` is empty, default to `status`:

```
pwsh -NoProfile -File ~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1 $ARGUMENTS
```

Then relay the dispatcher's output to the user:

- **`open`** prints `opened http://127.0.0.1:8000/` on success, or warns and points at `cs doctor` on failure.
- **`ensure`** ends with the terminal marker `SUCCESS:cs-up` (exit 0) or `FAILED:cs-down` (exit 1) — report that verbatim; only proceed to touch `:8000` on `SUCCESS:cs-up`.
- **`status` / `doctor`** print a state/health table — surface the headline (state, latency, any `*** WEDGED ***` flag, and FAIL/WARN rows) and, if anything is wedged or down, suggest `/cs fix`.

## Notes

- **HTTP 401 on `/` = alive** (auth gate). A **slow/timeout** response = **WEDGED** (WSL frozen, usually host-RAM pressure) — `cs fix` recovers it.
- The dispatcher is latency-aware and self-supervising; you rarely need more than `open`, `status`, `fix`, or `doctor`.

## Related

- Skill: `skills/claude-science-local/SKILL.md` — the verbs, the wedge gotcha, backup/restore.
- Docs: `scripts/claude-science/README.md` — install, NVIDIA NIM connector, reliability hardening.
