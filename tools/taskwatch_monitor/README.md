# taskwatch_monitor

A general-purpose long-task progress monitor — the FEP dashboard, generalized.
A source-agnostic engine polls any long-running job (build, download, CI run,
FEP/BPMD driver, LLM generation, rclone transfer …) through one uniform adapter
and renders an honest, BLIND-aware status: a rich CLI/TUI, an MCP server for
agent hosts, and a day-1 auto-attach hook.

It is built to kill the two bug-classes that bit the original FEP dashboard:

1. **No hidden clamps.** An out-of-range reading (`fraction > 1`) *widens* the
   ETA band and renders a full bar with a `!` marker — it is never silently
   discarded.
2. **Whole-record reads.** The progress record is read in full with a monotonic
   `seq`, never a fixed log tail — so log-rolloff can never undercount the
   frontier.

> **ETA honesty.** Unknown total ⇒ no percentage (`--%`), elapsed + rate only.
> A stall never slides the finish clock forward. A poll/tool error goes **BLIND**
> — the last verdict is held with an age stamp and never relabelled `DONE`.

---

## Two planes

Every task is watched on two planes at once:

- **Liveness (universal, always on)** — mtime / byte-growth / line-rate /
  process-up. Answers *"is it moving?"* with no cooperation from the job.
- **Progress (optional)** — an opt-in `progress.json` heartbeat
  `{schema, done, total|null, phase, ts, seq}`. Answers *"how far?"* Absent or
  `total = null` ⇒ liveness-only, no fabricated percentage.

---

## Install

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```powershell
cd tools/taskwatch_monitor
.\install.ps1            # uv sync + a `taskwatch` PATH shim
```

Or run without installing (uv handles the venv on first use):

```powershell
uv run python -m cli.app status
```

---

## CLI usage

```powershell
# register a task from a template into the registry TOML
taskwatch register generic-logfile mybuild --config path=C:\logs\build.log

taskwatch list                       # tabular listing of registered tasks
taskwatch list --json                # machine-readable registry
taskwatch status                     # one-shot honest status report
taskwatch status --json              # BLIND-aware status views as JSON
taskwatch status --watch             # live rich TUI (leg/stage grid, sparkline)
taskwatch status --history priors.db # blend sqlite priors into the ETA
```

Every subcommand takes `--registry <path>` (default `taskwatch.toml`).
`status` flags: `--watch`, `--json`, `--history DB`, `--stall-after SECS`,
`--interval SECS`.

### Templates

`register <template>` stamps a valid task spec (adapter + parser + ETA model +
notify set) from a preset, so you never hand-write TOML:

| template | source | ETA model | needs |
|---|---|---|---|
| `fep-databricks` | Schrödinger FEP+ multisim driver log | per-phase-weighted | `path` |
| `bpmd-modal` | Binding-pose metadynamics driver log | ewma-throughput | `path` |
| `modal` | Generic Modal app-log tail | ewma-throughput | `path` |
| `gh-actions-ci` | GitHub Actions run (REST JSON) | per-phase-weighted | `url` |
| `rclone-download` | rclone `--stats` transfer log | ewma-throughput | `path` |
| `npm-build` / `cargo-build` | build log tail | linear-frac | `path` |
| `git-clone` | git clone progress | ewma-throughput | `path` |
| `llm-run` | LLM token/step log | ewma-throughput | `path` |
| `generic-logfile` | any `N/M` or `NN%` log (fallback) | linear-frac | `path` |

---

## Architecture

```
core/     declarative TOML registry · 4 source-adapters behind one poll() ·
          4 ETA models (p50/p90 range + measured|prior provenance) ·
          liveness + progress planes · BLIND state · sqlite history/priors
probes/   per-source line parsers (fep, bpmd, generic) + templates
cli/      argparse surface · snapshot engine · TaskView assembly · store
mcp_server/  FastMCP stdio server — 5 tools mirroring the CLI (never `mcp`,
          to avoid shadowing the mcp SDK import)
hooks/    pure should_attach() decision-fn + PostToolUse auto-attach shell
ui/       render.py (pure string builders, 100% covered) · tui.py (rich Live
          loop, the single reasoned coverage-omit)
```

### Source adapters

One `poll() -> {lines, mtime, exists, liveness}` contract, four backends:
local-file-tail (regex), file-exists / glob-count, http-json, process/pid.

### ETA models

Each returns a **p50/p90 range** plus a provenance (`measured` | `prior` |
`none`): linear-frac, EWMA-throughput, per-phase-weighted, steady-state-window.
No estimator ever fabricates a countdown — an unknowable rate returns a
not-estimable estimate.

---

## Two tiers: observe by default, remediate opt-in

taskwatch **observes** by default. Tier-2 **remediation** (restart / re-attach)
is gated behind an explicit per-task `remediate` flag — set at `register`
time (`--remediate`) or flipped later via the MCP `attach_watch` tool. Nothing
acts on a job unless you asked for it.

**Notify** is deliberately quiet: terminal state, first-progress, and stall
only — no per-poll spam.

---

## MCP server

A FastMCP stdio server exposes the same surface to an agent host:

```powershell
uv run taskwatch-mcp        # console-script entrypoint (mcp_server.server:main)
```

Tools: `register_task`, `list_tasks`, `status`, `attach_watch`, `set_notify`.
Every tool returns a terminal-state `{"ok": ...}` envelope — it never raises.

---

## Auto-attach hook

A pure decision function drives a day-1 PostToolUse / longrun shell:

```
should_attach(op_kind, elapsed_s, whitelist, killswitch) -> bool
```

60-second threshold, fail-open, deduped. The pure fn is 100% covered; the shell
around it is thin.

---

## Live watch dashboard

```powershell
.\launch.ps1                          # new console, watches taskwatch.toml
.\launch.ps1 -Inline                  # current console
.\launch.ps1 -Registry runs\a2d.toml  # a specific registry
```

The watch loop (`ui/tui.py`) is presentation / event-loop code built entirely
from the pure `ui/render.py` builders. It is the **single** reasoned
`[tool.coverage.run] omit` — the same pattern as mcp-manager's `ui/app.py`. Every
testable decision (status derivation, ETA selection, string building,
GPU-percent parsing, sparkline scaling) lives in the 100%-covered modules.

---

## Development

The cov-gated template (mirrors tools/mcp-manager exactly):

```powershell
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
basedpyright core probes cli ui mcp_server hooks
pytest --cov=. --cov-branch --cov-report=term-missing --cov-fail-under=100
```

100% **branch** coverage is mandatory. The only coverage-omit is the
`ui/tui.py` render loop (reasoned, greppable — see `pyproject.toml`).
basedpyright runs at **standard** mode. Tests are fully offline: every adapter,
clock, poller, filesystem, and notifier is dependency-injected, so no test
touches a real job, network, or wall clock.
