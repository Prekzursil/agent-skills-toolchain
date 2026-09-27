# Lane: Supervision and reliability (key: supervision)

**Status: COMPLETE. Both-states proof GREEN — 26/26 controls, exit 0, empty stderr.**
Host: OFFLOAD-W2025 (Windows Server 2025, PowerShell 7). 2026-09-25.

```
SUCCESS:sup-selftest3 (94s)   [exited with code 0]
controls: 26  passed: 26  failed: 0
SUCCESS:supervise-selftest 26/26
```

## Deliverable

`~/.agents/scripts/supervise.ps1` (33 KB) — one shared supervision primitive:
(a) liveness vs readiness split, (b) capped exponential backoff with full jitter, (c) sliding-window
restart budget with an escalating + notifying latch, (d) evidence capture before the kill,
(e) durable latch state + operator-visible churn. Plus a kill guard that refuses to stop the
agent/MCP fleet or any process the supervisor did not itself start.

Proof harness: `~/.agents/scripts/supervise.selftest.ps1` + `supervise.selftest/` (throwaway test
process, readiness probe, escalation stub, splatting runner).

## Claim ledger

| # | Claim | Status | Label | Confidence |
|---|---|---|---|---|
| 1 | The premise outage is real and ONGOING | CONFIRMED | VERIFIED | high (95%) |
| 2 | Existing bespoke watchdogs enumerated | 5 found, each read | VERIFIED | high (90%) |
| 3 | `supervise.ps1` exists and parses | PASS | VERIFIED | high (99%) |
| 4 | BOTH-STATES: restarts a deliberately-killed proc | C1.1-C1.3 PASS | VERIFIED | high (95%) |
| 5 | BOTH-STATES: REFUSES to restart a mute-but-alive proc | C2.1-C2.4 PASS | VERIFIED | high (95%) |
| 5b | REFUSES inside the warmup grace | C2.5 PASS | VERIFIED | high (95%) |
| 6 | Latch fires, escalates, notifies, KEEPS notifying | C6.1-C6.6 PASS | VERIFIED | high (95%) |
| 7 | Backoff exponential + capped + full-jitter | C8.1-C8.4 PASS | VERIFIED | high (95%) |
| 8 | Evidence written BEFORE the kill | C4.1 PASS | VERIFIED | high (95%) |
| 9 | Latch durable across a fresh supervisor process | C7.1-C7.3 PASS | VERIFIED | high (95%) |
| 10 | NET-NEGATIVE: what this RETIRES | reported below | VERIFIED | high (90%) |
| 11 | Zero footprint on anything live | VERIFIED below | VERIFIED | high (95%) |

**Not claimed:** that this primitive works against a REAL daemon. It has never been pointed at one
(rule: do not target a live daemon). Every control ran against a throwaway `pwsh` test process.
Wiring it to `rclone serve`, Claude Science or basic-memory is a follow-up the owner approves, and
the first such wiring should be re-proven with a unit-specific readiness probe.

## Claim 1 — the premise, VERIFIED on THIS host, independently of the brief

The brief asserted the home-side fact. I did not re-derive it from the same side; I measured the
CLIENT side on this VM — a different machine, a different log, a different process:

```
mount-L.log: lines=3324  couldn't-connect=340
  FIRST 2026/09/23 22:31:54 ... dial tcp 100.97.16.36:2022 ...
  LAST  2026/09/25 22:40:54 ... dial tcp 100.97.16.36:2022 ...
mount-M.log: lines=3289  couldn't-connect=309   (same span, :2023)
```

340 + 309 = **649** failures across **two days, still failing**. The brief's 337+305 = 642 has
GROWN to 649 — proof the failure is live and unnoticed, not historical.

Second, independent instance of the same class on this host: `Get-ScheduledTask vm-link-serve`
reports `LastRunTime = 11/30/1999`, `LastTaskResult = 267011` (`0x41303` =
SCHED_S_TASK_HAS_NOT_RUN) — registered, never run, never noticed. `OPEN-LOOPS.md` L-14 records the
cause of the home half: `HOME-SETUP.md` step 4 told home to run `rclone serve sftp` in a FOREGROUND
shell, so it died with the shell. Layer (b), tailnet reachability, is still OPEN.

## Claims 2 + 10 — the bespoke watchdogs, and what this RETIRES

Found by filename glob across `~/.agents`, `~/.claude`, `~/.local/opt`, `~/bin`,
`~/source/agent-skills-toolchain`, then read. Scored against the five properties:

| # | Path | B | (a) live/ready | (b) backoff+jitter | (c) latch | (d) evidence | (e) durable |
|---|---|---|---|---|---|---|---|
| W1 | `~/.agents/scripts/claude-science/cs-watchdog.ps1` | 5,404 | partial SLOW/DOWN | **none**, fixed 30s | soft, **SILENT**, self-resets | **none** | **none** (in-memory) |
| W2 | `~/.agents/scripts/agentic-perfection/bm-watchdog.ps1` | 3,496 | partial (75s marker) | **none** | **none** | **none** | marker file only |
| W3 | `C:\ProgramData\vm-link\install-home-service.ps1` | 7,861 | **none** | **none**, fixed 1 min | **none** (`-RestartCount 999`) | **none** | Task Scheduler |
| W4 | `~/.agents/scripts/claude-science/cs-supervisor.sh` | 2,655 | **best of the five** (HEALTHY/SLOW/WEDGE/DOWN, socket-accepts-but-HTTP-mute = WEDGE) | **none**, fixed 30s | **none at all** | **none** | in-memory `slow=0` |
| W5 | `~/.agents/skills/workflow-monitor/monitorcore/watchdog.py` | - | different class: agent-transcript stall detection | - | - | - | - |

The two decisive defects, from the code:

- **W1 latches SILENTLY and then forgets.** `cs-watchdog.ps1:38-41` —
  `if ($script:recoveries -ge 3 -and ... -lt 15) { Write-WdLog "CRASH-LOOP BREAKER tripped..."; return }`
  A log line and a `return`. No escalation, no notification. `:59` then resets `$recoveries = 0`
  after 15 quiet minutes, so it silently resumes. `$script:recoveries` is in-memory, so restarting
  the watchdog also forgets the breaker. **This is the rclone failure mode in source form.**
- **W3 restarts 999 times at a fixed 1-minute interval** (`:125`) — no budget, no jitter, no
  evidence, no escalation.
- **W4 has the best readiness model and NO budget whatsoever** — `cs-recover` forever (`:48-49`).

**NET-NEGATIVE (REPORTED ONLY — no deletion performed, rule 3):**

| Retire | Replaced by | Residual that must be PRESERVED, not deleted |
|---|---|---|
| W1 `:37-46` breaker + in-memory `$recoveries` | latch + durable state | W1's latency-aware `Test-CSHealth` and `wsl -t` recovery are domain knowledge → become `-ReadinessCommand` / `-EscalateCommand` |
| W2 `:16-52` whole restart policy | liveness + backoff + budget | its 75s relaunch-marker grace → `-WarmupGraceSec 75`; its kill-the-stuck-launcher sequence → the escalation |
| W3 `:125` `-RestartCount 999 -RestartInterval 1min` | `-Once` on a repeating trigger | its Tailscale check (`:6-8`) is a real DEPENDENCY probe → readiness exit 2 |
| W4 `:34-52` loop + `slow` strike counter | the same unit definition as W1 | its four-state WEDGE-vs-DOWN classifier is the model `supervise.ps1` generalises — keep it as the readiness probe |

W5 and `mcp_fleet_supervisor.py` are a DIFFERENT class (agent-loop stall detection; MCP inventory
and quarantine). **Not retired**, and saying otherwise would be the deletion-destroys-capability
mistake this estate has made before.

Honest addition that retires nothing: the self-test harness. Justification: none of W1-W5 has a
both-states test, and the lane's premise is that an unproven supervisor is worthless. It earned
its place immediately — see below.

## The both-states proof — 26/26

Run with `longrun.ps1 -Id sup-selftest3` (94s, exit 0, stderr log never even created). Every tick
is a separate `pwsh` process, so passing also proves the state is genuinely durable across
supervisor restarts. Each property is asserted in BOTH states — the ACT half and the REFUSE half —
because a supervisor that fires on everything is worse than one that never fires.

| Control | Result (run 3, final) |
|---|---|
| C1.1 first tick starts the unit | PASS `verdict=DEAD action=restarted churn=1` |
| C1.2 a HEALTHY unit is left ALONE (the refuse-half control) | PASS `verdict=HEALTHY action=none churn=1` |
| C1.3 a KILLED unit is restarted with a NEW pid | PASS `churn=2 old=... new=...` |
| C2.1 mute-but-alive => DEGRADED-DEPENDENCY, NO restart | PASS `action=no-restart churn=1 samePid alive` |
| C2.2 the refusal is by POLICY, not the kill guard | PASS `state.ownPid == live pid` |
| C2.3 the refusal is not silent | PASS notify log names DEGRADED-DEPENDENCY |
| C2.4 UNKNOWN readiness (probe exit 42) never restarts | PASS `DEGRADED-UNKNOWN / no-restart` |
| C2.5 not-ready INSIDE the warmup grace is WARMING | PASS `verdict=WARMING action=no-restart churn=1` |
| C3.1 SELF-FAULT below threshold does NOT restart | PASS two ticks `SELF-FAULT-PENDING/no-restart` |
| C3.2 SELF-FAULT at the threshold DOES restart | PASS `WEDGED / restarted churn=2` |
| C4.1 evidence captured BEFORE the kill | PASS `pid=50296 pidMatch=True cmdlineCaptured=True rss=92639232 targetDeadNow=True` |
| C5.1 protected name => stop REFUSED | PASS `action=stop-refused churn=1 alive=True` |
| C5.2 non-protected => stop ALLOWED | PASS `action=restarted churn=2` |
| C6.1 restarts inside the budget permitted | PASS |
| C6.2 the budget-busting restart LATCHES | PASS `action=latched exit=3 latched=True churn=2` |
| C6.3 the latch ESCALATES to a DIFFERENT remediation | PASS `ESCALATED t-latch restart budget exhausted: 2 restarts in 900s (max 2)` |
| C6.4 the latch NOTIFIES | PASS `hasLATCH=True hasReason=True` |
| C6.5 the latch captures evidence | PASS |
| C6.6 a LATCHED unit KEEPS talking | PASS `action=latched-refused notifyLines 1 -> 2 hasLATCHED=True` |
| C7.1 a fresh process still sees the latch | PASS `exit=3 ... restartsInWindow=2/2 latched=True` |
| C7.2 `-ClearLatch` is the only way out | PASS `clearExit=0 statusExit=0 latchedFalse=True` |
| C7.3 churn readable as a bare integer | PASS `churnFile=2` |
| C8.1 ceiling doubles then CAPS | PASS `ceilings = 100,200,400,400,400` |
| C8.2 every delay inside `[0, ceiling]` | PASS `samples=5 outOfBand=0 J=35,59,121,199,109` |
| C8.3 jitter really applied, not always the ceiling | PASS `strictlyBelow=5/5` |
| C8.4 seeded reproduces, unseeded differs | PASS `seed7a=[38,77,153] seed7b=[38,77,153] unseeded=[57,193,333]` |

The three load-bearing controls:

- **C4.1 (evidence before the kill).** `process.json` holds pid 50296's command line and
  RSS 92,639,232 while that pid is **now dead** — the capture can only have happened pre-kill.
- **C6.6 (the rclone failure mode).** A latched unit produced `action=latched-refused` AND a second
  notification. It stops restarting without going quiet. This is the single control that the
  existing watchdogs would all fail.
- **C8.2/C8.4 (full jitter).** Delays 35,59,121,199,109 against ceilings 100,200,400,400,400 —
  inside the band, all strictly below it, reproducible under a seed and not reproduced without one.
  That is full jitter, not equal jitter and not a fixed interval.

### C6.3 was a race in the TEST, not a supervisor defect (run 2)

Run 2 reported C6.3 FAIL. The escalation had genuinely run; the harness read the marker too early:

```
state/t-latch.events.log : 2026-09-25T23:36:20.0575911+00:00 [INFO] t-latch escalation dispatched: pwsh
escalated.txt            : 2026-09-25T23:36:20.7358405+00:00 ESCALATED t-latch restart budget exhausted: 2 restarts in 900s (max 2)
```

~680 ms apart. Escalation is dispatched asynchronously **on purpose** — a supervisor must never
block on a pager. The control now polls for up to 10s. Recording this rather than deleting it: the
first reading was a false FAIL, and a harness that produces those erodes trust in the greens.

## THE BUG THE HARNESS CAUGHT — and the honest story of how I misdiagnosed it first

Run 1: the latch **never fired**. `restartsInWindow=1/2` while `churnTotal=3`.

Root cause: `Get-SupWindowRestarts` returned its array as `, $keep` and callers did
`@(...).Count`. The comma operator wraps the array, so the caller receives exactly ONE object and
`.Count` is **1 for any length**. With `MaxRestarts=2` the budget check was permanently
`(1+1) > 2 = false`: **the latch was structurally unreachable.** A supervisor with an
unreachable latch is precisely the rclone failure mode — and nothing but an assertion on the
latch could have found it.

Two process failures worth recording, because both are the kind this estate keeps repeating:

1. **My first probe was inert and I nearly shipped its verdict.** `probe_comma.ps1` used
   `1..$n | ForEach-Object { $k += $_ }`; `+=` inside `ForEach-Object` writes to a CHILD scope, so
   `$k` stayed empty and every variant returned 1 — including `n=0`, which should have tipped me
   off. It "confirmed" the right answer for the wrong reason. The real independent signal arrived
   as a runtime type error in run 2: `Could not compare "97" to "100 200 400 400 400"` — one
   object whose `.C` member-enumerated the whole array. (Same defect was in the HARNESS's own
   `Get-Backoffs`; C8.1 "passed" only because member enumeration happened to yield the right five
   values, and C8.2 crashed.)
2. **I changed two things at once** (comma-return AND ISO→epoch storage), so the re-run could not
   attribute the fix. Settled with an isolating experiment against an original-format state file
   holding 2 in-window restarts:

```
state on disk holds 2 restarts; after ConvertFrom-Json elemType=DateTime
TRUTH                                     = 2
A) ISO dates + int return                 = 2
B) ISO dates + comma return, @(..).Count  = 1
budget check ((count)+1) > 2 :  A -> True   B -> False   TRUTH -> True
```

So: **the comma-return was the sole cause.** The ISO→epoch change was NOT required for the latch;
it is separate hardening that removes a real but different fragility — `ConvertFrom-Json` silently
converts an ISO-8601 property into a `[DateTime]` whose `[string]` form is the culture-dependent
`09/25/2026 23:30:27`, losing sub-second precision. Both fixes are kept; only one was the bug.

## Measured Windows gotchas worth keeping

1. **`pwsh -File script.ps1 -Arr a b c` binds ONLY the first element** to a `[string[]]` param
   (`$Arr.Count = 1`); `-Arr a,b,c` binds one element containing literal commas. In-process
   splatting `& $script @hashtable` binds correctly (Count=2) and `exit N` inside it propagates to
   `$LASTEXITCODE` (verified 7). Hence `supervise.selftest/run-sup.ps1`. Without this probe every
   control would have run against a one-element `-StartArgs` and passed for the wrong reason.
2. **`, $arr` as a function return + `@(...).Count` at the call site always reads 1.** Return a
   scalar count, or emit the array plainly.
3. **`+=` inside `ForEach-Object` writes to a child scope** and silently leaves the outer array
   empty. `foreach` (the statement) does not.

## Files changed (nothing committed — the orchestrator commits)

| Path | State |
|---|---|
| `C:\Users\prekzursil\.agents\scripts\supervise.ps1` | new, ~33 KB |
| `C:\Users\prekzursil\.agents\scripts\supervise.selftest.ps1` | new |
| `C:\Users\prekzursil\.agents\scripts\supervise.selftest\testproc.ps1` | new |
| `C:\Users\prekzursil\.agents\scripts\supervise.selftest\testprobe.ps1` | new |
| `C:\Users\prekzursil\.agents\scripts\supervise.selftest\escalate.ps1` | new |
| `C:\Users\prekzursil\.agents\scripts\supervise.selftest\run-sup.ps1` | new |

Not wired to anything: no scheduled task created or modified, no live daemon referenced, no
`~/.agents/rules/` change (so `sync-rules.ps1` is not needed for this lane).

## Proposed follow-up NOT done in this lane, and why

The three Windows gotchas above belong in `rules/common/windows-shell.md` §11 (tool-transport
class). I did **not** add them. Reason: `~/.agents/rules/common/` is a shared tree and four other
lanes of this workflow are live in it right now; editing underneath concurrent work is how a
mismatch report that is not real gets produced (estate-context §1e). Handing the orchestrator the
measured text to splice is the lower-risk move than racing for the file. The three items are:
`pwsh -File` cannot bind a multi-element array · `, $arr` as a return + `@(...).Count` always
reads 1 · `+=` inside `ForEach-Object` writes to a child scope.

## Rules honoured — each with its check

| Rule | Evidence |
|---|---|
| No live daemon targeted | Every control ran against a `pwsh` testproc in `$env:TEMP`; `Test-Path ~/.agents/state/supervise` = **False**, so the primitive left no trace in the real state tree |
| No MCP/node/python process killed | `-ProtectedNameMatch` defaults to `^(claude\|node\|python\|pythonw\|pwsh\|powershell\|uv\|uvx\|npx\|Code\|ssh\|sshd\|tailscaled)$` and is **proven to refuse** (C5.1). `grep -nE 'Stop-Process -Name\|taskkill\|Register-ScheduledTask' supervise.ps1` -> **none**; every stop is `Stop-Process -Id <a pid this supervisor started>` behind two guards |
| No orphaned test processes | post-run `Win32_Process` where CommandLine like `*testproc.ps1*` -> **0** |
| No scheduled task registered or modified | tasks matching `supervis` -> **0**; `vm-link-serve` read via `Get-ScheduledTask` only. (Observation, not my doing: `ClaudeHarnessBench` appeared in the non-Microsoft task list between my first and last listing — I register nothing, so a concurrent lane is the likely author; flagging it rather than claiming it) |
| `~/.claude.json` untouched | never opened |
| No credential read, printed or modified | none referenced |
| Nothing committed / deleted / pruned | no `git` write, no MCP/skill/plugin/branch touched; retirements are REPORTED only |
| `>60s` ops under `longrun` | all three self-test runs launched via `longrun.ps1` with `run_in_background` and joined before reporting |

## Result

**SUCCESS** — one shared supervision primitive built, all five required properties implemented, and
all 26 both-states controls green (`SUCCESS:supervise-selftest 26/26`, exit 0). The harness paid for
itself on its first run by catching a structurally unreachable latch that no existing watchdog on
this estate would have caught.
