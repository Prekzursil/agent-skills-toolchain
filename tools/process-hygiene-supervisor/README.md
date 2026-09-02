# process-hygiene-supervisor — one estate-wide process governor for Windows

Keeps the 31.6 GB workstation that hosts many AI runtimes (Cursor agent CLI+IDE,
Claude Code, Codex, Grok, Goose, Fabric, ~42 MCP servers, WSL2, Chrome, Edge)
from chronic out-of-memory and orphan-process pile-up — **without removing any
feature**. It reaps only *leaked*, *orphaned*, *duplicated*, and *idle* consumers,
and reports (never kills) the rest.

Design, the full root-cause inventory of the 02.09.2026 measurement, and the
install/rollback runbook are in
[`docs/plans/2026-09-02-process-hygiene-supervisor.md`](../../docs/plans/2026-09-02-process-hygiene-supervisor.md).
Options that were **rejected** (working-set trimming, `wsl --shutdown`,
`taskkill /F`) and prevention work **queued for the owner** (job-object launch
shims, `node.exe` MCP entrypoints, browser discard policies) are in
[`docs/plans/2026-09-02-process-hygiene-decision-queue.md`](../../docs/plans/2026-09-02-process-hygiene-decision-queue.md)
— read that before proposing a change to how anything is killed.

## Split: Python decides, PowerShell actuates

Same shape as [`../mcp/mcp-host-supervisor`](../mcp/mcp-host-supervisor). All rules,
thresholds, and the audit ledger live in tested Python; PowerShell only samples the
process table and actuates the OS.

| file | purpose |
|---|---|
| `hygiene.py` | the decision engine: policy/snapshot validation, tiers, all rules, the JSONL ledger, `apply_plan`, and the `run`/`explain`/`validate-*` CLI. Pure — no process control. **100% line+branch.** |
| `hygiene_actuate.py` | `WindowsActuator`: the only OS-mutating surface — children-first stops on **one pinned process handle** per PID (identity → `TerminateProcess` → exit wait, so a recycled PID can never be hit), opt-in WM_CLOSE, per-distro `wsl --terminate`, and delegation to `cursor-orphan-reaper.ps1`. OS calls behind injectable seams. **100% line+branch.** |
| `process-hygiene.ps1` | thin launcher: samples the snapshot, shells to `hygiene.py run` (report-only unless `-Apply`). Makes no decisions. |
| `install_task.ps1` | registers/removes the `ProcessHygiene` scheduled task (LIMITED principal, every 5 min + logon, report-only unless `-Apply`; `-OnResourceExhaustion` adds a RADAR event-2004 trigger). |
| `policy.example.json` | the policy template — tiers, protected allowlist, runtimes, orphans, retired, MCP, WSL, ledger. |
| `wslconfig.example` | `.wslconfig` with a `memory`/`swap` cap + `autoMemoryReclaim=dropCache` under `[experimental]` (under `[wsl2]` it is a silent no-op). |
| `test-process-hygiene.ps1` | manual Windows smoke test of the launcher (not run in CI — CI has no `pwsh`). |
| `evals/` | `run_evals.py` + 11 scenarios and `EVALS.md`: replays snapshots through the engine and grades the plan (pass@1 / pass^3). |
| `tests/` | 182 Python tests + `mutation_probe.py` (26 reverted-safety mutations, all killed). |

## What it does

- **Tiers** from free RAM, commit ratio **and commit headroom** (`limit − charge`,
  the quantity whose exhaustion fails allocations) — `normal < elevated <
  critical`, escalate at once, de-escalate on repeated calm readings — gate how
  aggressive every rule may be. The `critical` ratio leg is 2.5×, deliberately
  above this box's chronic 2.14× baseline.
- **retired** — stops a retired component (AgentBridge `bridge-server`) on sight and
  names the launcher to edit so it stops respawning.
- **orphan / daemon** — parent-liveness + age + whole-tree-idle reaping, children
  first, exact-PID only, never by name; a parentless process that owns a listening
  port (auth2api) is reported as a daemon, not killed.
- **session-age / rss** — per-runtime session-age and private-byte ceilings;
  IDE-owned or peer-runtime-owned agents are only ever *reported*, and every row
  carries that runtime's `resume_hint` (how to get the session back).
- **mcp-\*** — duplicate / singleton / over-budget verdicts through the shipped
  `mcp_fleet_supervisor` + `mcp_control_plane` and `agents.json`.
- **wsl** — reports an oversized vmmem and can `wsl --terminate` an idle distro
  (paired with the `.wslconfig` cap), skipping `docker-desktop*` and standing down
  entirely while Docker Desktop or any live `wsl.exe` client is attached.
- **browser** — reports Chrome/Edge aggregates and names the exact discard
  policies to set (`TotalMemoryLimitMb`, Memory Saver, Sleeping Tabs); never kills
  and never trims.
- **protected** — auth2api, the Basic Memory daemon + watchdog, the MCP hosts,
  Windows binaries, and this supervisor survive every rule.
- **cursor-agent** parentless roots are **delegated** to the tested
  `scripts/agentic-perfection/cursor-orphan-reaper.ps1`, not reaped here.

Guards on top of the rules: a per-run **stop budget**, a **crash-loop breaker**
(a component stopped repeatedly is reported instead — the spawner is the bug), and
a bounded **network veto** so a tree holding an ESTABLISHED remote socket is not
reaped for looking idle while it waits on a model response.

Every decision is one JSONL ledger row (kills, defers, dry-runs), secrets
redacted, unchanged reports deduped, rotating over N generations. Each run also
writes `heartbeat.json` (staleness/mode) and, on a **new** kill kind or a failure,
appends one `BACKGROUND-DIGEST` line.

## Usage

```bash
# validate config / a snapshot
python hygiene.py validate-policy   --policy policy.example.json
python hygiene.py validate-snapshot --snapshot snapshot.json

# print the plan for a snapshot (writes nothing)
python hygiene.py explain --snapshot snapshot.json --policy policy.example.json \
  --registry ../../.agents/agents.json

# evaluate + write state/ledger; report-only by default, --apply to actuate
python hygiene.py run --snapshot snapshot.json --policy policy.json \
  --state state.json --ledger ledger.jsonl [--apply]
```

On Windows the launcher gathers the snapshot for you:

```powershell
pwsh -File process-hygiene.ps1 -EmitSnapshotOnly -SnapshotOut $env:TEMP\phs.json   # sample only
pwsh -File process-hygiene.ps1                                                     # report-only run
pwsh -File test-process-hygiene.ps1                                                # launcher smoke test
pwsh -File install_task.ps1            # register report-only task
pwsh -File install_task.ps1 -Apply     # flip to enforcing after a dry-run review
pwsh -File install_task.ps1 -Uninstall # remove
```

## Dev

```bash
python -m pytest tests/ --cov=hygiene --cov=hygiene_actuate --cov=run_evals \
  --cov-branch --cov-report=term-missing --cov-fail-under=100   # 182 passed, 100%
python evals/run_evals.py                                       # 11/11, pass^3 100%
python tests/mutation_probe.py                                  # 26/26 killed
uvx ruff@0.15.17 check . && uvx ruff@0.15.17 format --check .
```
