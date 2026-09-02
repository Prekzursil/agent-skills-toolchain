# Process-hygiene: decision queue and rejected options (2026-09-02)

Everything here came out of a fan-out review of the shipped supervisor (fifteen
parallel research lenses plus a three-voice council on one contested default).
The **applied** findings are in the code and in
`2026-09-02-process-hygiene-supervisor.md`. This file records two other kinds of
outcome, both of which are worth more than a changelog line:

1. **Queued** — changes that would touch launchers, browser policy or another
   tool's tree. Each carries the evidence, the blast radius and the reversal, so
   the owner can say yes or no without re-deriving anything. None is applied.
2. **Rejected** — options that look right and are not, with the measurement or
   source that kills them. These exist so the next agent does not re-propose
   them (two of them were in my own first draft).

## 1. Rejected — do not re-propose

| Option | Why it fails |
| --- | --- |
| **Trim working sets (`EmptyWorkingSet`) instead of stopping anything** | Moves pages to the modified list, where Windows **compresses** them into the `Memory Compression` process that already holds 9.7 GB on this box. Commit charge — the leg that fails allocations — does not move at all, and an *active* heap re-faults its hot set within seconds, so a box that is already paging gets a fault storm plus compression CPU. Trimming a *browser* is worse: it fights the browser's own discard heuristics. |
| **Efficiency mode / EcoQoS as a memory remedy** | Low CPU priority + EcoQoS is a **CPU** feature. It slows a leaking process down; it never returns a byte. Useful for noisy-neighbour CPU, irrelevant here. |
| **`critical` at commit ratio > 2.0×** | This box's chronic baseline is 2.14× (67.7 GB on 31.6 GB). A 2.0× trigger makes `critical` permanent, i.e. every critical-tier action becomes a *standing* action. Shipped as 2.5× plus a commit-**headroom** leg. |
| **`wsl --shutdown` as the routine reclaim path** | Tears down every distro and the VM: VS Code Remote-WSL sessions die unrecoverably and Docker Desktop needs a restart. Shipped as per-distro `wsl --terminate`, gated on no attached client. |
| **`sparseVhd=true` in `.wslconfig`** | A *disk*-space feature (does nothing for RAM/commit) that the WSL source gates behind a corruption warning. Left commented out with an export-first note. |
| **`taskkill /F /PID` as the kill primitive** | Re-opens the PID *after* validation, so it can land on a process that reused the number. Shipped as one pinned handle held across identity → `TerminateProcess` → exit wait. |
| **`taskkill /PID` (no `/F`) as a graceful stop for agents** | Posts WM_CLOSE only to windows a process owns; refused outright for windowless console processes — which is exactly what node/python agent sessions and MCP servers are. Kept as an opt-in that forces immediately when refused. |

## 2. Queued for the owner — prevention, not reclaim

Ordered by the ratio of measured relief to blast radius. Items Q1–Q2 attack the
*cause* the supervisor can only mop up after.

### Q1. Job-object launch shim for agent CLIs (removes orphans structurally)

**Evidence.** Windows does not cascade termination: that is *why* the
02.09.2026 measurement found parentless `node.exe` trees at all. A job object
with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` makes the OS kill the whole tree when
the launcher's handle closes — including on a hard kill of the launcher — and
`JobMemoryLimit` can cap a tree's commit so one session cannot take the box
down. This is the same mechanism VS Code and Chrome use for their child trees.

**Shape.** A small `Start-AgentJob` wrapper (or a ~40-line C#/ctypes shim) that
creates the job, assigns the child, and holds the handle for the session's
lifetime; agent launchers call it instead of spawning directly.

**Blast radius.** Touches how *every* agent session starts — the highest-risk
item here, and the reason it is queued rather than applied. A bug in the shim
does not leak memory, it *prevents sessions from starting*.

**Reversal.** Launchers stop calling the wrapper; nothing persists.

### Q2. Launch MCP stdio servers as `node.exe <entry.js>`, not `cmd /c npx …`

**Evidence.** `cmd /c npx pkg` creates a three-deep tree (`cmd.exe` →
`node.exe` npx shim → `node.exe` server). Killing the client leaves the middle
and leaf behind — the classic orphan shape in the incident. `npx` also resolves
the package on every start (slower, and a supply-chain surface). Resolving the
entrypoint once and spawning `node.exe` directly removes two processes per
server and makes the tree one level deep.

**Shape.** Rewrite the affected `command`/`args` pairs in the MCP configs to the
resolved `node.exe <path-to-dist/index.js>`; keep `npx` only where a package
genuinely has no stable entrypoint.

**Blast radius.** Config-only, per server, individually reversible; a wrong path
fails loudly at start rather than silently.

### Q3. Browser discard policies (keeps every tab; returns commit)

**Evidence.** `TotalMemoryLimitMb` (Chrome and Edge, HKLM policy) makes the
browser discard the least-recently-used tabs when the process family exceeds the
limit — tabs stay in the tab strip and reload on click. Chrome
`HighEfficiencyModeEnabled=1` + `MemorySaverModeSavings=2` and Edge
`SleepingTabsEnabled=1` + `SleepingTabsTimeout=300` +
`EfficiencyModeEnabled=1` do the same on a timer. This is the only lever that
returns *commit* from a browser without closing anything.

**Blast radius.** Registry policy under HKLM; visible to the user as tabs
reloading. Fully reversible by deleting the values. The supervisor already
*reports* this and never acts on a browser.

### Q4. Fold Resource-Guard's micro-guard into the supervisor

**Evidence.** `scripts/agentic-perfection/resource-guard.ps1` already samples
memory and runs an orphan micro-guard on its own cadence; the supervisor now
does a superset of that sampling. Two schedulers watching the same box can
disagree and double-act.

**Shape.** Keep Resource-Guard as the *reporting* front-end and have it read the
supervisor's `heartbeat.json`, or retire its micro-guard leg. Needs a read of
both schedules before touching either.

### Q5. `% Committed Bytes In Use` as a fourth tier leg

**Evidence.** The perf counter is the same quantity as the headroom leg but
normalised, and it is what the Resource-Exhaustion-Detector itself watches. Worth
adding only if the absolute-headroom leg proves noisy on a variable pagefile.
The RADAR **event trigger** half of this idea is already shipped as an opt-in
(`install_task.ps1 -OnResourceExhaustion`, event 2004).

### Q6. A "supervisor is stale/disabled" surface

**Evidence.** The worst failure mode of a watchdog is silence: if the task is
disabled, erroring on every run, or stuck in report-only long after the owner
meant to enable it, nothing says so — a quiet box and a dead supervisor look
identical. The supervisor now writes `heartbeat.json` (ts, tier, apply mode,
script hash) on every run, so the *signal* exists.

**Why it is queued rather than wired.** The obvious consumer is
`hooks/background-digest/reader.py`, but that is a **generic** digest reader
shared by every producer; teaching it one specific tool's heartbeat path would
couple a shared hook to this tool. The clean options are (a) a two-line check in
whichever producer already runs on a schedule (Resource-Guard — so this folds
into Q4), or (b) a tiny standalone producer that only compares
`now − heartbeat.ts` against the task interval. Both are the owner's call about
the hook budget.

**Already proven, so the queued half is small:** the supervisor's digest line is
contract-tested against the real `reader.py` (`_is_entry`, `_priority`,
`build_message`) — the failure line carries `ACTION_REQUIRED` so the reader ranks
it ahead of routine chatter, while a merely-critical tier is written lowercase so
it does not. If either side's format drifts, the supervisor's test suite fails
instead of the digest silently going unread.

### Q7. Per-runtime admission control (ceilings at launch)

**Evidence.** The council's Skeptic voice, and the arithmetic behind the
report-only default: one 4 GiB kill returns ~6% of commit and the session comes
back at the next tick. A launch-time ceiling (job memory limit, or a runtime's
own `--max-old-space-size` where it has one) makes the oversized session
impossible instead of recurrent. Depends on Q1.

## 3. The contested default, recorded

**Question.** At `critical` tier, what should happen to an *active* (non-idle)
agent session that is over its hard private-bytes ceiling? (a) report only,
(b) graceful stop then kill, (c) trim/throttle instead.

**Outcome: (a) report-only stays the default**, `escalation.stopActiveAtCritical`
remains opt-in, and (c) is rejected outright (see §1). The reasoning that
survived review:

- (c) is a placebo *and* actively harmful under pressure — it relocates RAM into
  the compression store and re-faults immediately.
- (b) does not clear the tier: ~4 GiB against a 4.5 GB shortfall means the next
  tick kills the next-largest session, and the one after that — a serial kill
  loop authored by the supervisor, against work the user is actively doing.
  "Graceful" degrades to `TerminateProcess` for a console app anyway, and resume
  restores the transcript, not a half-applied refactor or an interrupted git
  operation.
- (a) is the only default that cannot destroy work. Its honest failure mode is
  the unattended 03:00 case: nobody reads the report and the box thrashes. That
  is what the tier legs, the digest line and the heartbeat are for — and why Q1/Q7
  (prevention) rank above any reclaim tuning.

**Consequence already applied:** the `critical` ratio leg moved to 2.5× and the
headroom leg was added, because a "critical" that is always true would have made
this an academic question.
