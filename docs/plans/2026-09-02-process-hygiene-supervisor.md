# Estate process-hygiene supervisor — root cause, architecture, install (2026-09-02)

**Status:** implemented and tested (`tools/process-hygiene-supervisor/`); ships
**report-only**, enforcing mode is an explicit owner opt-in.
**Scope:** a single estate-wide process-hygiene supervisor for the Windows 11
workstation (31.6 GB RAM) that hosts many AI agent runtimes at once. No feature
is removed to buy RAM — every runtime, MCP server and browser stays; the
supervisor removes only *leaked*, *orphaned*, *duplicated* and *idle* consumers.

All process/memory figures below are the owner's measurement taken **02.09.2026
04:50 EEST** on the Windows box, which cannot be reached from here. They are
**cited, not re-measured.**

## 0. The measurement (verbatim, cited)

- Physical RAM 31.6 GB; **3.5 GB free**; **67.7 GB committed** (commit ratio
  ≈ 2.14×); **Memory Compression 9.7 GB**.
- **chrome** 70 processes, 4.7 GB; **msedge** 42 processes, 1.6 GB.
- **node** 28 processes, 1.5 GB — of which one `cursor-agent` session `node.exe`
  is **1.0 GB after 20 minutes**, and **two `cursor-agent` CLI sessions from
  28–31 h ago** still hold **311 MB and 61 MB**.
- **vmmemWSL** 1.1 GB **with no workload inside**.
- **pwsh** 14 processes, 686 MB.
- A **retired AgentBridge `bridge-server`** crash-looping under **three Grok
  sessions** at **130–155 MB each**.
- An **`auth2api`** node process (`dist/index.js`, `:8317`) running **105 h as an
  orphan by design**.
- **4 orphaned node/python** processes whose parent is gone.
- **Basic Memory** daemon dies near-daily under pressure, restarted by a watchdog.

## 1. Root-cause inventory (every source classified, with evidence)

Classes: **agent-runtime lifecycle**, **MCP duplication**, **browser**, **WSL**,
**telemetry / commit-charge growth**.

| # | Source (measured) | Class | Root cause | Handling in this design |
|---|---|---|---|---|
| 1 | `cursor-agent` node.exe **1.0 GB after 20 min** | agent-runtime lifecycle | a single live session's working set grows unbounded | **`rss-soft`/`rss-hard`** per-runtime private-byte ceilings; idle → graceful stop, active → report (or stop at critical if opted in) |
| 2 | two `cursor-agent` CLI sessions **28–31 h old** (311 MB + 61 MB) | agent-runtime lifecycle | detached long-idle sessions never reclaimed; the incident `docs/incidents/2026-08-29-cursor-agent-mcp-orphan-ram.md` records parentless cursor roots surviving with full MCP trees | **`session-age`** ceiling; a *parentless* cursor root is **delegated to the tested `cursor-orphan-reaper.ps1`** (multi-observation, identity-revalidating), never reaped inline |
| 3 | retired **AgentBridge `bridge-server`** crash-loop under 3 Grok, 130–155 MB | agent-runtime lifecycle | a retired component (CLAUDE.md/AGENTS.md: AgentBridge retired 2026-07-27) still registered in a launcher, respawning | **`retired`** rule: stop on sight **and** the ledger names the parent launcher to edit so it stops respawning (killing the instance alone only buys the next crash) |
| 4 | **4 orphaned node/python** (parent gone) | agent-runtime lifecycle | Windows does not bind descendant lifecycle; a parent exit orphans MCP/tool children | **`orphan`** rule: parent-liveness + age + **whole-tree-idle** over repeated observations, children-first exact-PID kill, never by name |
| 5 | **`auth2api`** `:8317`, 105 h orphan **by design** | agent-runtime lifecycle (**protected**) | an intentional long-lived local proxy that is parentless on purpose | **protected**: matched by command token *and* by the daemon carve-out (parentless-but-owns-a-listening-port ⇒ reported, never killed) — survives every rule |
| 6 | **pwsh** 14 processes, 686 MB | agent-runtime lifecycle | shell hosts for CLI sessions; some detached | orphan rule reaps only *leaf* parentless idle shells; a shell hosting a runtime session is left to `session-age`/reaper (a detached host is only reaped once it is childless) |
| 7 | **~42 registered MCP servers** duplicated per session | MCP duplication | each session auto-starts configured **stdio** MCPs; `S` sessions × `H` servers before backends (see `tools/mcp/mcp-http-host/README.md`, incident 2026-08-29) | **`mcp-*`** rules decided through the shipped **`mcp_fleet_supervisor` + `mcp_control_plane`**: same-owner duplicate (stop the younger idle tree), cross-owner duplicate (report the shared-host migration), per-instance over-budget, **singleton** enforcement for the http daemons |
| 8 | **Basic Memory** daemon dies near-daily; watchdog restarts | MCP duplication + telemetry victim | the shared `:8765` daemon flaps under RAM pressure (`.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`); watchdog restarts can transiently duplicate it | **`mcp-singleton-duplicate`**: keep the port owner, stop only a non-owner past a warm-up grace; the daemon **and** its watchdog are **protected** so hygiene never fights the watchdog |
| 9 | **chrome** 70 proc 4.7 GB; **msedge** 42 proc 1.6 GB | browser | many renderer/tab processes hold working set | **`browser`** rule: **report only** with an aggregate + a Memory-Saver/sleeping-tabs proposal — never killed (closing tabs is the owner's call; no feature removed) |
| 10 | **vmmemWSL** 1.1 GB, no workload | WSL | WSL2 default 50%-RAM ceiling and no automatic return of freed guest memory | **`.wslconfig`** `memory` cap + `autoMemoryReclaim` (bounds the guest continuously) **plus** an idle-`wsl --shutdown` signal as a last resort |
| 11 | **67.7 GB committed / 31.6 GB physical**, Memory Compression 9.7 GB | telemetry / commit-charge growth | the aggregate symptom of 1–10: commit charge far exceeds physical, so Windows compresses/pages and sessions freeze (basic-memory "commit-exhaustion = freeze root cause") | **commit-ratio + free-RAM tiers** (`normal`/`elevated`/`critical`) gate *how aggressive* every other rule may be, with de-escalation hysteresis so a brief spike does not thrash |

Nothing in the inventory is "kill a feature". Items 5, 8, and the Basic Memory
watchdog are explicitly **preserved** (protected allowlist); browsers (9) are
report-only; runtimes (1–2, 6) lose only *idle/detached/oversized* instances.

## 2. Architecture

One supervisor, split the way the estate already splits `mcp-host-supervisor`
(Python decides, PowerShell actuates):

```
Task Scheduler ─every 5 min + logon (+ optional RADAR event 2004)─▶ process-hygiene.ps1
      │  samples Win32_Process + Get-Process (private/WS) + Get-NetTCPConnection
      │  (Listen -> listeners, Established -> connections) + Win32_OperatingSystem
      │  + Committed/Commit-Limit counters + Memory Compression + wsl --running
      │  + Docker Desktop / wsl.exe client counts  ──▶ snapshot JSON (validated)
      ▼
  hygiene.py run --snapshot … [--apply]   (PURE decision engine, 100% tested)
      │  tiers ← free RAM ∨ commit ratio ∨ COMMIT HEADROOM (+ hysteresis)
      │  rules ← retired · orphan/daemon · session-age · rss · mcp-* · wsl · browser
      │  gates ← protected allowlist · whole-tree idle · bounded network veto
      │  budget ← maxStopsPerRun · crash-loop breaker (per command_sha256)
      │  cursor-agent parentless ─────────────▶ DELEGATE
      ▼                                              │
  hygiene_actuate.WindowsActuator (--apply only)     │
      │  children-first; ONE PINNED HANDLE per PID   │
      │  (identity → TerminateProcess → exit wait);  │
      │  opt-in WM_CLOSE; wsl --terminate <distro>   │
      ▼                                              ▼
  JSONL ledger (rotating, secrets redacted)   cursor-orphan-reaper.ps1
  + heartbeat.json + one BACKGROUND-DIGEST     (tested multi-observation reaper,
    line per NEW kill kind                      report-only under Resource-Guard)
```

**Reuse, not reimplementation.** The MCP verdicts call
`scripts/mcp_fleet_supervisor.py` + `scripts/mcp_control_plane.py` (singleton
keys, `processMatch`, `maxPrivateBytes`, per-instance budgets from `agents.json`);
cursor-agent orphans are handed to `scripts/agentic-perfection/cursor-orphan-reaper.ps1`;
the `.wslconfig` cap complements, rather than replaces, the idle-shutdown signal.

**Tiers → escalating actions.** Three legs raise the tier: free physical RAM,
commit charge / physical RAM, and **commit headroom** (`commit limit − commit
charge`) — the last is the quantity whose exhaustion actually fails allocations,
and the reason the ratio leg for `critical` is **2.5×** rather than 2.0×: this
box's *chronic baseline* is 2.14×, so a 2.0× trigger would make "critical" a
permanent standing state and every critical-tier action a standing action. Each
rule declares the lowest tier at which it may *stop*; below that it only reports.
`normal`: retired components, whole-tree-idle orphans (incl. cursor-agent
fallback), hard-RSS breaches. `elevated`: soft-RSS, same-owner MCP duplicates,
non-owner singleton duplicates, idle WSL terminate. `critical`: per-instance MCP
over-budget, and (opt-in) stopping *active* oversized sessions. Escalation is
immediate; de-escalation needs repeated calm readings.

**What an oversized ACTIVE session gets at `critical`: still report-only.** Three
independent reviews (`docs/plans/2026-09-02-process-hygiene-decision-queue.md`
records them) converged: killing it frees ~6% of commit and returns at the next
tick, i.e. a serial kill loop; and *working-set trimming* — the tempting third
option — is a placebo, because `EmptyWorkingSet` moves pages to the modified list
where Windows **compresses** them into the very `Memory Compression` process that
already holds 9.7 GB, then the active heap re-faults them in seconds. Efficiency
mode/EcoQoS is CPU-only and does nothing for commit. So the default stays
`escalation.stopActiveAtCritical=false`, and the durable fix is upstream
admission control (ceilings at launch), not reactive reclaim.

**Kill-storm and crash-loop guards** (borrowed from earlyoom/oomd/kubelet):
`escalation.maxStopsPerRun` caps stops per snapshot — the remainder is ledgered
`deferred-budget` and reconsidered next tick; a command line stopped
`crashLoopKills` times inside `crashLoopWindowSeconds` is *reported*, not killed
again (`result=crash-loop`), because a respawning component means the spawner is
the bug — for the retired AgentBridge that is the `[mcp_servers.agentbridge]`
entry the `retired` remediation names.

**The idle signal has a second opinion.** Zero CPU and zero disk I/O also
describes a session waiting on a slow model response, so a tree holding an
ESTABLISHED **non-loopback** socket defers its own stop up to
`idle.networkVetoMaxCycles` times (`network_veto: true` in the ledger) — bounded,
so a half-open keep-alive cannot shield a leak forever.

**WSL: terminate the distro, and only when nobody is attached.** `wsl --shutdown`
tears down *every* distro plus the whole VM, which unrecoverably breaks VS Code
Remote-WSL sessions and Docker Desktop; the supervisor therefore issues
`wsl --terminate <distro>` per idle distro, excludes `docker-desktop*`, and skips
the action entirely while Docker Desktop or any live `wsl.exe` client is running
(ledgered `blocked_by`). `.wslconfig` carries the continuous lever:
`autoMemoryReclaim=dropCache` under `[experimental]` (**not** `[wsl2]`, where it
is a silent no-op) — `gradual` reclaims slowly and stops short of an empty guest,
a plausible cause of the measured 1.1 GB idle plateau. `sparseVhd` is left off on
purpose: it is a *disk*-space feature and is gated behind a corruption warning.

**Browsers keep every tab.** The supervisor never kills or trims a browser; it
reports and names the only lever that actually returns commit — making the
browser *discard* idle tabs: `TotalMemoryLimitMb` (Chrome and Edge, HKLM
policies), Chrome `HighEfficiencyModeEnabled` + `MemorySaverModeSavings=2`, Edge
`SleepingTabsEnabled` + `SleepingTabsTimeout` + `EfficiencyModeEnabled`.

**Auditability.** Every decision writes one JSONL row (`schema`,`ts`,`run_id`,
`rule`,`action`,`tier`,`result`,`pid`,`command_sha256`, redacted `command_line`,
private bytes, detail incl. a per-runtime `resume_hint`). Report-only rows carry
`result=dry-run`; deferred rows `result=deferred`/`deferred-budget`; kills
`forced`/`graceful`/`failed`/`vanished`/`identity-changed`. Unchanged *report*
rows are deduped to one per `ledger.reportKeepaliveSeconds` so kills are not aged
out by chatter, and the ledger rotates over `ledger.generations` files. Each run
also writes `heartbeat.json` (ts, tier, apply, script hash) so a SessionStart
check can tell "supervisor stale/disabled" from "quiet box", and appends **one**
`BACKGROUND-DIGEST` line only when a NEW rule kind stopped something, a failure
appears, or the tier first hits critical.

**Safety invariants (all mutation-tested, `tests/mutation_probe.py`, 26/26
killed).** Whole-tree idle before any reap; the protected allowlist; cursor-agent
delegation; the singleton port owner is kept; the age gate; the apply-time tier
gate; the network veto; the crash-loop breaker; the stop budget; the WSL
attach-gate; the ownership carve-out; and in the actuator: the pinned-handle
identity revalidation, the exit wait, and access-denied ≠ vanished.

**The TOCTOU window is closed in the kill path.** The actuator opens **one**
handle per member (`PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_TERMINATE|
SYNCHRONIZE`) and holds it from identity validation through `TerminateProcess`
and the exit wait: a PID cannot be recycled while a handle to it is open, whereas
`taskkill /F /PID` re-opens by PID *after* validation and can land on a newcomer
that reused the number. Polite stop is opt-in
(`integration.politeStopSeconds`, default `0`) because `taskkill /PID` without
`/F` posts WM_CLOSE only to windows a process owns and is refused outright for
windowless console processes — exactly the node/python agent sessions and MCP
servers this supervisor targets; when refused, the actuator forces immediately
instead of burning the grace window.

## 3. Windows install steps (owner)

Prereq: `C:\Python314\python.exe` present (the estate's bundled interpreter);
the repo checkout at `C:\Users\Prekzursil\source\ast-integrate` (the only edited
checkout per CLAUDE.md).

1. **Deploy the tool** to a protected runtime root (so it does not self-reap and
   is not edited by other agents):
   ```powershell
   $src  = 'C:\Users\Prekzursil\source\ast-integrate\tools\process-hygiene-supervisor'
   $root = 'C:\Users\Prekzursil\.agent-guard\process-hygiene'
   New-Item -ItemType Directory -Force -Path $root | Out-Null
   Copy-Item "$src\hygiene.py","$src\hygiene_actuate.py","$src\process-hygiene.ps1",
             "$src\install_task.ps1" -Destination $root
   Copy-Item "$src\policy.example.json" -Destination "$root\policy.json"
   ```
   Then open `$root\policy.json` and confirm the `protected` lists (auth2api,
   `bm-http-server.ps1`, `bm-watchdog.ps1`, `resource-guard.ps1`,
   `cursor-orphan-reaper.ps1`, the MCP hosts, WSL/vmmem, browsers) match your box.
2. **Cap WSL** (bounds vmmem continuously so shutdown is a last resort):
   ```powershell
   Copy-Item "$src\wslconfig.example" "$env:USERPROFILE\.wslconfig"   # review memory=8GB first
   wsl --shutdown        # apply the new limits on next WSL start
   ```
3. **Dry-run once, read the plan** (writes nothing, kills nothing):
   ```powershell
   pwsh -File "$root\process-hygiene.ps1" -EmitSnapshotOnly -SnapshotOut "$env:TEMP\phs.json"
   python "$root\hygiene.py" explain --snapshot "$env:TEMP\phs.json" `
     --policy "$root\policy.json" `
     --registry 'C:\Users\Prekzursil\source\ast-integrate\.agents\agents.json'
   ```
4. **Register the task in REPORT-ONLY** and let it run for a while, then read the
   ledger (`$root\ledger\process-hygiene.jsonl`) to confirm it would only stop
   the right things:
   ```powershell
   pwsh -File "$root\install_task.ps1"          # report-only, every 5 min + logon
   Start-ScheduledTask -TaskName ProcessHygiene
   Get-Content "$root\ledger\process-hygiene.jsonl" -Tail 40
   ```
5. **Enable enforcement** only after the dry-run week looks right:
   ```powershell
   pwsh -File "$root\install_task.ps1" -Apply   # re-registers ProcessHygiene enforcing
   ```
   Enforcing mode still reports below each rule's tier and only graceful-stops
   confirmed-idle / detached / duplicate / over-budget consumers.

## 4. Rollback

Every step is reversible and leaves no residue beyond the ledger:

- **Disable enforcement, keep observing:** `pwsh -File "$root\install_task.ps1"`
  (re-registers report-only) — or **remove entirely:**
  `pwsh -File "$root\install_task.ps1" -Uninstall` (backs up the prior task XML to
  `$root\*.BEFORE-*.xml` first).
- **Undo the WSL cap:** delete `%USERPROFILE%\.wslconfig` (or restore your prior
  one) and `wsl --shutdown`.
- **Nothing else changed.** The supervisor never edits `agents.json`,
  `~/.claude.json`, any MCP config, or a credential; it does not bind or move any
  port; it does not touch the Basic Memory daemon, its watchdog, or auth2api. The
  ledger and state under `$root` can be deleted safely; they regenerate.

## 5. Verification performed

- `hygiene.py` + `hygiene_actuate.py` + `evals/run_evals.py`: **182 tests, 100%
  line+branch** (`pytest --cov --cov-branch --cov-fail-under=100`), pinned
  `ruff==0.15.17` clean, and `tests/mutation_probe.py` kills **26/26**
  reverted-safety mutations (each mutation names the invariant it breaks).
- `evals/run_evals.py`: **11/11 scenarios, pass@1 and pass^3 = 100%** — including
  a replay of the 02.09.2026 measurement, which reads `elevated` under an 80 GB
  commit limit (12.3 GB headroom) and `critical` under 70 GB (2.3 GB headroom)
  with an identical kill set: the tier changes what may *execute*, not what is
  *decided*.
- The launcher's snapshot contract was exercised end-to-end by feeding the
  launcher-shaped payload (AgentBridge + auth2api + a network-vetoed orphan +
  vmmemWSL) through `hygiene.py` on Linux: the retired bridge is a dry-run stop,
  auth2api never appears in a stop row, the vetoed orphan is a report with
  `network_veto`, the heartbeat is written, and no digest line is emitted in
  report-only mode. `test-process-hygiene.ps1` re-proves this on Windows with the
  live sampler (and additionally asserts the sampler emits `connections`,
  `wsl.docker_desktop_running` and `wsl.client_count`); it is not run in CI
  because there is no `pwsh` there.
- Owner-steered follow-ups (Job-object launch shims, `node.exe` entrypoints
  instead of `cmd /c npx`, browser discard policies, Resource-Guard merge) are
  queued with evidence and blast radius in
  `docs/plans/2026-09-02-process-hygiene-decision-queue.md` rather than applied
  unilaterally.
