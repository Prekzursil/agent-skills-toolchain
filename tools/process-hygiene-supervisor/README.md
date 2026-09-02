# process-hygiene-supervisor — one estate-wide process governor for Windows

Keeps the 31.6 GB workstation that hosts many AI runtimes (Cursor agent CLI+IDE,
Claude Code, Codex, Grok, Goose, Fabric, ~42 MCP servers, WSL2, Chrome, Edge)
from chronic out-of-memory and orphan-process pile-up — **without removing any
feature**. It reaps only *leaked*, *orphaned*, *duplicated*, and *idle* consumers,
reports (never kills) the rest, and — the half that matters more — **prevents the
orphan class from forming** with a job-object launcher and direct-exec MCP configs.

Design, the full root-cause inventory of the 02.09.2026 measurement, and the
install/rollback runbook are in
[`docs/plans/2026-09-02-process-hygiene-supervisor.md`](../../docs/plans/2026-09-02-process-hygiene-supervisor.md).
Options that were **rejected on evidence** (working-set trimming, `wsl --shutdown`,
`taskkill /F`, a "free page list" resample) and the record of every queue item — all
now shipped — are in
[`docs/plans/2026-09-02-process-hygiene-decision-queue.md`](../../docs/plans/2026-09-02-process-hygiene-decision-queue.md);
read that before proposing a change to how anything is killed.

## Split: Python decides, PowerShell actuates

Same shape as [`../mcp/mcp-host-supervisor`](../mcp/mcp-host-supervisor). All rules,
thresholds, and the audit ledger live in tested Python; PowerShell only samples the
process table and actuates the OS.

| file | purpose |
|---|---|
| `hygiene.py` | the decision engine: policy/snapshot validation, tiers (available RAM ∨ commit ratio ∨ **commit headroom**, with the live *failure mode* named), all rules, JSONL ledger, `apply_plan` (stop budget, crash-loop breaker, report dedupe), effectiveness measurement, heartbeat + digest, and the `run`/`explain`/`validate-*` CLI. Pure — no process control. **100% line+branch.** |
| `hygiene_actuate.py` | `WindowsActuator`: the only OS-mutating surface — children-first stops on **one pinned process handle** per PID (identity → `TerminateProcess` → exit wait; a recycled PID can never be hit), opt-in WM_CLOSE, per-distro `wsl --terminate`, opt-in memory-priority hints, reaper delegation. kernel32 calls carry explicit prototypes (a 64-bit `HANDLE` must never go through a C `int`). **100% line+branch.** |
| `hygiene_doctor.py` | read-only estate checks (`doctor`: heartbeat staleness, runtime versions vs known orphan fixes, `.wslconfig` key placement, wrapper-launched MCP servers), the **`rewrite-mcp`** tool that resolves `npx`/`cmd /c`/`uvx` wrappers to direct entrypoints (dry-run + diff; `--apply` after a backup), and **`browser-policy`** (discard-policy `.reg` + rollback + verify). **100% line+branch.** |
| `hygiene_launch.py` | **admission gate + job-object launch shim**: refuses a new agent session when the box is critical or the commit limit is < 30 min away (exit 75; `--force` recorded), fails open if the supervisor is down, runs the command inside a `KILL_ON_JOB_CLOSE` job (optional hard commit cap that fails allocations rather than killing), and writes a per-session bill (peak job memory, duration, exit). **100% line+branch.** |
| `process-hygiene.ps1` | thin launcher: samples the snapshot (processes, commit counters, hard-fault rate, WSL/Docker state, listeners + ESTABLISHED sockets, pagefile facts) and shells to `hygiene.py run` (report-only unless `-Apply`). Makes no decisions. |
| `install_task.ps1` | registers/removes the `ProcessHygiene` scheduled task (LIMITED principal, every 5 min + logon, report-only unless `-Apply`; `-OnResourceExhaustion` adds a RADAR event-2004 trigger). |
| `profile/Start-Agent.ps1` | dot-source from `$PROFILE`: `claude`/`codex`/`cursor-agent`/`grok`/`goose` become functions that route through `hygiene_launch.py` (precedence over the `.exe`, nothing shadowed on disk, removable with no residue). |
| `policy.example.json` | the policy template — every section a **closed schema** (a typo fails validation instead of silently disabling a rule). |
| `wslconfig.example` | `.wslconfig` with a `memory`/`swap` cap + `autoMemoryReclaim=dropCache` under `[experimental]` (under `[wsl2]` it is a silent no-op); `sparseVhd` deliberately off. |
| `test-process-hygiene.ps1` | Windows smoke test: live sampler contract, report-only, network veto, a **real spawned process killed through the pinned-handle Win32 path**, and a PID-reuse bait that must be refused. Not run in CI (no `pwsh`). |
| `evals/` | `run_evals.py` + 13 scenarios and `EVALS.md`: replays process tables through the engine and grades the plan (pass@1 / pass^3). |
| `tests/` | 433 tests incl. `test_invariants_fuzz.py` (14 safety invariants over random tables, seeded) and `mutation_probe.py` (31 reverted-safety mutations, all killed). |

## What it does

- **Tiers** from available RAM, commit ratio **and commit headroom** (`limit − charge`,
  the quantity whose exhaustion fails allocations) — `normal < elevated < critical`,
  escalate at once, de-escalate on repeated calm readings. The `critical` ratio leg is
  2.5×, deliberately above this box's chronic 2.14× baseline. The ledger names the live
  **failure mode**: `working-set` (hard faults, compression store — the freezes) vs
  `commit-exhaustion` (allocations fail — the daemon deaths), because a pagefile
  relieves the second and does nothing for the first.
- **Time to exhaustion** from the last hour of commit samples (`minutes_to_commit_limit`);
  under 30 min the digest is `ACTION_REQUIRED` and the launcher refuses new sessions.
- **retired** — stops a retired component (AgentBridge `bridge-server`) on sight and
  names the launcher to edit; a **crash-loop breaker** stops killing a respawning
  component and reports it instead (the spawner is the bug).
- **orphan / daemon** — parent-liveness + age + whole-tree-idle reaping, children
  first, exact-PID only, never by name; a parentless process that owns a listening
  port is a daemon, reported not killed; a tree holding an ESTABLISHED remote socket
  gets a bounded **network veto** (idle ≠ waiting on a model).
- **session-age / rss** — per-runtime ceilings; IDE-owned or peer-owned agents are
  only reported; every row carries a `resume_hint`.
- **mcp-\*** — duplicate / singleton / over-budget verdicts through the shipped
  `mcp_fleet_supervisor` + `mcp_control_plane` and `agents.json`.
- **wrapper-chain** — reports MCP servers launched via `npx` / `cmd /c` / `uvx` (libuv
  hosts set `SILENT_BREAKAWAY_OK` on their child job, so the real server — a
  grandchild — outlives the host by design) with the direct-exec fix `rewrite-mcp` applies.
- **commit-ceiling** — reports when the pagefile cannot grow to restore headroom (disk
  nearly full, or a custom maximum): the ceiling, not a process, is the constraint.
- **wsl** — reports an oversized vmmem and can `wsl --terminate` an idle distro, skipping
  `docker-desktop*` and standing down while Docker Desktop or any `wsl.exe` client is attached.
- **browser** — reports aggregates and points at `browser-policy`; never kills, never trims.
- **memory-priority** (opt-in, default off) — confirmed-idle tenants get
  `MEMORY_PRIORITY_VERY_LOW` so the memory manager trims *their* pages before the active
  session's; restored on activity or when pressure lifts; listening daemons excluded.
  Judge it by `pages_input_per_sec` before/after — it is a hint, not a reclaim.
- **protected** — auth2api, the Basic Memory daemon + watchdog, the MCP hosts, Windows
  binaries, browsers, WSL and this supervisor survive every rule.
- **cursor-agent** parentless roots are **delegated** to the tested
  `scripts/agentic-perfection/cursor-orphan-reaper.ps1`, not reaped here.

Guards on top: a per-run **stop budget**, **report dedupe** with an hourly keepalive,
bounded state, an **effectiveness** row after every apply run (expected vs realized
commit change — did the kill help, or did it come back?), `heartbeat.json`, and one
`BACKGROUND-DIGEST` line only on a new kill kind, a failure, critical, or imminent
exhaustion (contract-tested against the estate's `reader.py`).

## Usage

```bash
# validate config / a snapshot; print the plan for a snapshot (writes nothing)
python hygiene.py validate-policy   --policy policy.example.json
python hygiene.py validate-snapshot --snapshot snapshot.json
python hygiene.py explain --snapshot snapshot.json --policy policy.example.json \
  --registry ../../.agents/agents.json

# evaluate + write state/ledger; report-only by default, --apply to actuate
python hygiene.py run --snapshot snapshot.json --policy policy.json \
  --state state.json --ledger ledger.jsonl [--apply] [--digest BACKGROUND-DIGEST.md]

# read-only estate checks; exit 1 on anything ACTION_REQUIRED
python hygiene_doctor.py [--json] [--quick] [--digest BACKGROUND-DIGEST.md]
# resolve wrapper-launched MCP servers to direct entrypoints (dry run -> <cfg>.rewritten.json)
python hygiene_doctor.py rewrite-mcp --config ~/.claude.json [--node "C:/Program Files/nodejs/node.exe"] [--apply]
# browser discard policies (.reg + rollback + verify script)
python hygiene_doctor.py browser-policy --emit out/ [--hive HKLM|HKCU]

# launch an agent through the admission gate inside a job object
python hygiene_launch.py --runtime claude --job-memory-limit 6442450944 -- claude --resume abc
```

On Windows the launcher gathers the snapshot for you:

```powershell
pwsh -File process-hygiene.ps1 -EmitSnapshotOnly -SnapshotOut $env:TEMP\phs.json   # sample only
pwsh -File process-hygiene.ps1                                                     # report-only run
pwsh -File test-process-hygiene.ps1                                                # smoke test (kills a real spawned victim)
pwsh -File install_task.ps1            # register report-only task
pwsh -File install_task.ps1 -Apply     # flip to enforcing after a dry-run review
pwsh -File install_task.ps1 -Uninstall # remove
. .\profile\Start-Agent.ps1            # claude/codex/... now launch through the gate + job object
```

## Dev

```bash
python -m pytest tests/ --cov=hygiene --cov=hygiene_actuate --cov=hygiene_doctor \
  --cov=hygiene_launch --cov=run_evals --cov-branch --cov-report=term-missing \
  --cov-fail-under=100                                          # 433 passed, 100%
python evals/run_evals.py                                       # 13/13, pass^3 100%
python tests/mutation_probe.py                                  # 31/31 killed (~80 s)
uvx ruff@0.15.17 check . && uvx ruff@0.15.17 format --check .
```

To hunt harder than CI does, raise `CASES`/`ROUNDS` in `tests/test_invariants_fuzz.py`
locally (3,000 × 7 was clean on 2026-09-02).
