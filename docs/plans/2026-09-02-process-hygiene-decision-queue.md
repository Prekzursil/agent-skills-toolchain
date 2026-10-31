---
title: 2026-09-02-process-hygiene-decision-queue
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-09-02-process-hygiene-decision-queue
---

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
| **Re-sampling free RAM from a "free page list" counter** | Proposed on the theory that `Win32_OperatingSystem.FreePhysicalMemory` excludes the standby list and is "near zero by design". Checked: it maps to Task Manager's **Available** (free + zero + standby), the same quantity as `\Memory\Available MBytes`. The near-zero counter is `\Memory\Free & Zero Page List Bytes`, which the supervisor never reads. The thresholds are calibrated correctly; "fixing" this would have mis-set them by ~an order of magnitude. The sampling site now says so, since the field name `free_bytes` invites the same wrong fix. |
| **`taskkill /PID` (no `/F`) as a graceful stop for agents** | Posts WM_CLOSE only to windows a process owns; refused outright for windowless console processes — which is exactly what node/python agent sessions and MCP servers are. Kept as an opt-in that forces immediately when refused. |

## 2. The queue — every item now shipped (2026-09-02, second pass)

The user asked for the queue to be handled end to end. Each item below keeps its
original evidence and blast-radius note; a **Shipped** line records what was built,
where, and what the owner still has to *do* (the code cannot enrol a machine, edit
the owner's `$PROFILE`, or reboot for a pagefile). Nothing was applied to the
owner's box from here; everything is a tool the install steps in the design doc
walk through in order.

| item | shipped as | owner action that remains |
| --- | --- | --- |
| Q1 job-object shim | `hygiene_launch.py` + `profile/Start-Agent.ps1` | dot-source the profile |
| Q2 direct-exec MCP | `hygiene_doctor.py rewrite-mcp` (dry run → `--apply`), `wrapper-chain` rule | run it per JSON config; paste for TOML |
| Q3 browser discard | `hygiene_doctor.py browser-policy` (.reg + rollback + verify) | apply as admin, check `chrome://policy` |
| Q4 Resource-Guard fold | `resource-guard.ps1` calls `hygiene_doctor.py --quick` | none (inert until deployed) |
| Q5 % committed | `commit_pct` in metrics (headroom leg already carries the tier) | none |
| Q6 stale surface | `doctor` heartbeat check + `--digest`, via Q4 | none |
| Q7 memory priority | `memoryPriority` policy (default **off**), `pages_input_per_sec` measurement | enable only with a before/after |
| Q8 vendor fixes | `doctor` runtime-version check (Claude ≥ 2.1.153 verified; Codex advisory) | update the CLIs |
| Q9 pagefile | `commit-ceiling` advisory with pagefile facts sampled | set a fixed pagefile if `pinned_by: disk` |
| Q10 admission | `hygiene_launch.py` gate (critical or ETA < 30 min refuses; fails open) | as Q1 |

### Original evidence and blast radius, per item

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

**Evidence — and the mechanism, which is sharper than the process count.**
libuv (so: Cursor, the VS Code extension host, and any Node/Electron host) creates
each direct child inside a job object carrying `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
**and** `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`. The breakaway flag *deliberately
excludes grandchildren* from that job — so with `cmd /c npx pkg` (a three-deep tree:
`cmd.exe` → npx shim → the real server) the server is a grandchild and **survives
the host's death by design**. That is the orphan shape in the incident, and it is
not a bug in the host: it is what the flags say. Resolve the entrypoint once and
spawn `node.exe <entry.js>` and the server becomes the **direct** child, which the
OS tears down with the host — the orphan class disappears instead of being reaped.
`npx` also re-resolves the package on every start (slower, plus a supply-chain
surface).

**Now partly self-serving:** the shipped `wrapper-chain` rule reports exactly which
servers are in this shape, with this remediation, so the config edit is a list to
work through rather than a hunt. Verified for libuv hosts; unverified for the
Bun-compiled Claude Code binary and the Rust-based Codex/Goose.

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

### Q7. Memory priority for idle tenants (NOT the same thing as trimming)

**Evidence.** Under pressure Windows trims working sets fairly indiscriminately, so
the *active* session's hot pages are taken alongside the 42 idle MCP servers —
which is itself part of the freeze. `SetProcessInformation(ProcessMemoryPriority,
MEMORY_PRIORITY_VERY_LOW)` on confirmed-idle trees makes those pages the reclaim
pool that gets taken **first**. Meta's TMO/Senpai is the same idea (mild proactive
reclaim of cold tenants so pressure never reaches hot ones) at fleet scale.

**Why this is not the rejected trimming.** Setting a *priority* changes **whose**
pages the OS takes; calling `EmptyWorkingSet` **forces** pages out now, into the
compression store, and is rejected in §1. Q7 is the priority half only.

**Honest limits.** The docs call priority a hint; it does nothing for commit, so it
addresses the freezes and not the daemon deaths; and it mutates OS state on
processes the supervisor does not own. It should not ship unmeasured — the
validating measurement is `\Memory\Pages Input/sec` plus the active session's
page-fault rate, before and after, under real pressure.

### Q8. Vendor fixes and per-repo MCP scoping (free, upstream)

**Evidence.** All four runtimes have open or recently-fixed orphan bugs, so some of
today's pile-up is already fixed upstream: Claude Code 2.1.153 fixes orphaned MCP
servers when VS Code closes on Windows; Codex PR #19753 adds process-group kill
plus an explicit MCP client shutdown after a leak of 492 children / 82 GB from one
long-lived daemon; Cursor's leak is staff-confirmed with no ETA, which is precisely
why the reaper is load-bearing here. Separately, Claude Code's
`--strict-mcp-config` with a per-repo `.mcp.json` stops *every* session from
inheriting all ~42 global servers — the fan-out that makes each new session
expensive.

**Blast radius.** Version pins are routine; moving servers from global to per-repo
config changes which tools a session sees, so it is the owner's call.

### Q9. Fixed, disk-unpinned pagefile — the honest lever for the daemon deaths

**Evidence.** The commit limit is RAM + pagefile, and a system-managed pagefile
grows only when commit reaches ~90% of the limit, capped at one-eighth of the
volume and only when free disk exists. The incident record has C: at **98% used /
15.5 GiB free**, so the pagefile probably *cannot* grow — the commit ceiling is
pinned by **disk**, and each growth attempt is itself a stall. A fixed min=max
pagefile (≈ peak commit − RAM + headroom) on a volume with room is the *designed*
backing store for committed-but-untouched V8/Chromium reservations; this is not
leak-hiding.

**Honest limits.** It fixes allocation failures (the daemon deaths) and does
**nothing** for the freezes, which are a touched-set problem. Owner action: check
System-log Resource-Exhaustion-Detector event 2004 (it names the top commit
consumers at each exhaustion) and confirm the current pagefile mode first.

### Q10. Per-runtime admission control (ceilings at launch)

**Evidence.** The council's Skeptic voice, and the arithmetic behind the
report-only default: one 4 GiB kill returns ~6% of commit and the session comes
back at the next tick. A launch-time ceiling (job memory limit, or a runtime's
own `--max-old-space-size` where it has one) makes the oversized session
impossible instead of recurrent. Depends on Q1.

## 2b. Shipped from this review, not queued

Three findings were small and self-contained enough to implement rather than queue:

- **The tier now names its failure mode.** `tier` is one ordinal scale over two
  different failures: commit-limit exhaustion (allocations fail — the daemon
  deaths, relieved by less commit or Q9) and working-set pressure (hard faults and
  a growing compression store — the freezes, which a pagefile does not touch). The
  ledger and the digest line now carry `pressure_modes` and per-leg verdicts, so
  "critical" is never reported without saying critical *of what*.
- **The `wrapper-chain` rule** (report-only) names launcher shapes whose real
  server is a grandchild of the host, with the direct-exec remediation from Q2 —
  turning that queued config change into a concrete, evidence-carrying list rather
  than advice. This is why the mechanism is worth stating precisely: libuv hosts
  set `KILL_ON_JOB_CLOSE` **and** `SILENT_BREAKAWAY_OK` on their child job, so
  grandchildren are *deliberately* excluded and outlive the host.
- **The `free_bytes` sampling comment**, so the refuted "free page list" fix in §1
  cannot be re-attempted from the field name alone.

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
  is what the tier legs, the digest line and the heartbeat are for — and why Q1/Q10
  (prevention) rank above any reclaim tuning.

**Consequence already applied:** the `critical` ratio leg moved to 2.5× and the
headroom leg was added, because a "critical" that is always true would have made
this an academic question.

## 4. The uncomfortable arithmetic, stated plainly

A 9.7 GB compression store on 31.6 GB of RAM means the **touched** set is roughly
2× physical memory. Everything in this document — admission control, job limits,
memory priority, idle terminate, the supervisor itself — changes *who* pays and
*when*. Only a smaller touched set (fewer concurrent runtimes, fewer resident MCP
servers, browsers discarding tabs) or more DIMMs changes *whether* the box thrashes.

"Permanent fix, no feature removed" is achievable in the sense that matters — no
capability is deleted, and the leaked/orphaned/duplicated waste really does go away
— but it holds only while the hot set of the features actually in use fits in RAM.
If the owner routinely runs several 2-4 GiB agent sessions *at once*, alongside 70
Chrome and 42 Edge processes, no supervisor makes that fit; Q1/Q10 (admission
control) then becomes the honest answer, because it converts "everything is slow
and something dies" into "the fifth session waits".