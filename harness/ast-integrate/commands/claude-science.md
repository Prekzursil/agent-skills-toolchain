---
description: One-command control for the local Claude Science WSL2 workbench (127.0.0.1:8000). Shells to the cs dispatcher - open, status, fix, doctor, ensure, stop, backup, restore.
---

# claude-science — Claude Science (local) control

Bring up, diagnose, or recover Anthropic's **Claude Science** compchem / life-science
workbench — a WSL2 daemon serving `http://127.0.0.1:8000/`. **LOCAL only.**

## Usage

```
/claude-science [open|status|fix|doctor|ensure|stop|backup|restore <ts|latest>]
```

- `open` — ensure up (start-if-down / recover-if-wedged, wait for readiness) then open the UI. The one-click.
- `status` — state + latency + a `wedged` flag (add `-Json` for machine output). **Default when no verb is given.**
- `fix` — graceful force-recover (clears stale locks, restarts). The wedge cure.
- `doctor` — full-stack PASS/WARN/FAIL/NOT-CHECKED health report. **Exits non-zero on FAIL or NOT-CHECKED**, so other tooling can gate on it.
- `ensure` — headless ensure-up for tools/agents → `SUCCESS:cs-up` / `FAILED:cs-down`.
- `stop` · `backup` · `restore <ts|latest>` — daemon stop / online SQLite snapshot / rollback.

$ARGUMENTS

## What to Do

Shell to the **installed** dispatcher, passing `$ARGUMENTS` through as the verb (and any
trailing argument, e.g. a restore timestamp). If `$ARGUMENTS` is empty, default to `status`:

```
pwsh -NoProfile -File ~/.local/bin/cs.ps1 $ARGUMENTS
```

That is the same file the `cs` shim on `PATH` runs, so the slash command and the shell command
can never diverge. **Do not point this at a source checkout.** Until 2026-08-12 this line named
`~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1`; that tree sat at a detached HEAD
holding the pre-fix tool (`cs-doctor.ps1` 5,590 B against the 13,852 B deployed one, no `cs.conf`,
no `cs-lib.sh`), so `/claude-science doctor` printed 11 rows and `0 FAIL, 1 WARN, 9 PASS` while
`cs doctor` printed 13 rows across four states — in the same minute, on the same box. `cs doctor`
now carries a **Slash-command route** row that hashes the dispatcher this file names and fails if
it is not byte-identical to the doctor actually running, so the divergence cannot come back
silently. Deploy with `install.ps1`; the repo is the source and the live tree is the target.

Then relay the dispatcher's output to the user:

- **`open`** prints `opened http://127.0.0.1:8000/...` on success, or warns and points at `doctor` on failure.
- **`ensure`** ends with the terminal marker `SUCCESS:cs-up` (exit 0) or `FAILED:cs-down` (exit 1) — report that verbatim; only proceed to touch `:8000` on `SUCCESS:cs-up`.
- **`status` / `doctor`** print a state/health table — surface the headline (state, latency, any `*** WEDGED ***` flag, and FAIL/WARN/NOT-CHECKED rows) and, if anything is wedged or down, suggest `/claude-science fix`.

## Notes

- **HTTP 401 on `/` = alive** (auth gate). A **slow/timeout** response = **WEDGED** (WSL frozen, usually host-RAM pressure) — `fix` recovers it.
- **`NOT-CHECKED` is not `PASS`.** A doctor row that could not reach its input says so and never renders green; the summary counts those rows separately, so `0 FAIL, 0 WARN` alone does not mean everything was measured.
- **A `Fault injection` row, a `[SIMULATED …]` summary or any `[INJECTED]` detail means the run is a simulation** driven by the test seam, not a measurement of this box — never quote it as health evidence. The seam is inert unless `CS_FAULT_INJECTION=1` arms it, and a `CS_FORCE_*` variable set without arming is refused *and* reported.
- Configuration (port, distro, backup root, thresholds) lives in **one** file — `scripts/claude-science/cs.conf` — and every key in it can be overridden by an environment variable of the same name, so `$env:CS_PORT = 8123` works without editing anything.
- The dispatcher is latency-aware and self-supervising; you rarely need more than `open`, `status`, `fix`, or `doctor`.

## Related

- Skill: `skills/claude-science-local/SKILL.md` — the verbs, the wedge gotcha, backup/restore.
- Docs: `scripts/claude-science/README.md` — install, NVIDIA NIM connector, reliability hardening.
