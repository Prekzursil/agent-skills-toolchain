# MEGAWAVE C — lane-C artifact: supervise `-ProcessNameFallback` liveness + basic-memory re-pilot

STATUS: COMPLETE — all sections measured. `SUCCESS:lane-C`.
Goal (re-anchor): owner-decided `-ProcessNameFallback` liveness in
`C:\Users\Prekzursil\.agents\scripts\supervise.ps1` (fixes the pidfile-contract mismatch),
selftest green (old 26 + 5 new), re-pilot basic-memory under `BasicMemory-Supervised` to
verdict=HEALTHY + one clean kill-drill restart. All done; residuals registered in OPEN-LOOPS.

## 1. Code change — supervise.ps1 — VERIFIED

- Params added: `[switch]$ProcessNameFallback`, `[string]$FallbackMatch` (use-site default =
  `$ProcessNameMatch`; param() cannot reference sibling params). Plus new
  `Get-SupFallbackNeedle` and rewritten `Get-SupLivePid`.
- Needle derivation (order): (1) value of flag `-p|-port|--port`, (2) LAST flag->value pair,
  (3) last bare arg. Microtest (AST-isolated invocation of the real function):
  bm-like args → `18765`; selftest args → per-unit heartbeat path; empty → `''`. VERIFIED.
- Liveness semantics: pidfile branch unchanged (missing/stale=DEAD; name-mismatch=pid-reuse WARN).
  Fallback branch ONLY when `-PidFile` absent/empty AND `-ProcessNameFallback`: Name regex match
  AND CommandLine contains needle (OrdinalIgnoreCase); never self-matches; logs
  `FOUND-BY-FALLBACK pid=N`; weak needle (<4 chars) or no StartArgs → loud WARN, reads DEAD.
- Production evidence (events log, exact lines):
  `2026-09-28T14:29:01.9176225+00:00 [INFO] basic-memory FOUND-BY-FALLBACK pid=35664 (name /basic-memory/ + needle '18765')`
- Residual, measured and retired: uv shim → venv python → server python (3-generation chain).
  Shim-kill takes the whole chain (probe: kill 9388 → 11316 died; drill: kill 35664 → no
  35664-lineage procs remained). Supervisor-initiated stops are therefore chain-complete FOR THIS
  SHAPE on this box (INFERRED general case, confidence ~70%: job-coupling measured on 2 samples).

## 2. Selftest controls — VERIFIED (31/31)

`pwsh -NoProfile -File C:\Users\Prekzursil\.agents\scripts\supervise.selftest.ps1` →
`SUCCESS:supervise-selftest 31/31` (exit 0, longrun `sup-selftest-C2`, 169s).
C9.1 defect-pin (pidfile-less, no fallback, alive → DEAD+restarted) · C9.2 fallback finds unit
(FOUND-BY-FALLBACK log + HEALTHY, no restart) · C9.3 needle specificity, genuinely discriminating
(foreign same-name pwsh untouched: `foreign=49444 foreignAlive=True new=5304`) · C9.4 stop-refusal
on a fallback-found protected process · C9.5 pidfile outranks fallback (canonical path, fallback
inert). Old 26 all PASS.
Run #1 honesty note: first run 27/30 — failures were MY control-design bug (`-Fallback` without
`-NoPidFile` let the pidfile answer), and C9.3's pass was a false-green under the same bug
(§3c control-that-cannot-distinguish). Fixed by making the controls pidfile-less + adding C9.5.

## 3. Git — VERIFIED

- Local commit `a17951775` "supervise: -ProcessNameFallback liveness (mega-wave C)" — exactly
  2 files (`git show --stat`: scripts/supervise.ps1 +111/-16 lines region, scripts/supervise.selftest.ps1,
  193 insertions, 16 deletions); staged index verified EMPTY before `git add`.
- Plain push rejected (remote had 3 sibling TASKBOX commits). NO force used. Integrated via
  throwaway worktree: cherry-pick → `git push origin tmp-megawave-c:live-capture/2026-09-02` →
  `ee21a2fb0..6a206a7e4` FAST-FORWARD. Two signals: push output + `git ls-remote` = `6a206a7e4`.
- Local branch left ahead-1/behind-3 (patch-equivalent) — OPEN-LOOP for a clean-tree
  `git pull --rebase`. Worktree + temp branch removed.

## 4. basic-memory re-pilot — VERIFIED, HEALTHY, drill green

Cutover (all measured):
- Old task `BasicMemory-HTTP-MCP`: Stopped + **Disabled** (state=Disabled VERIFIED) — prevents
  logon-respawn fighting the new task.
- Daemons killed: shim 9388 + child 11316 (coupling probe: child died with shim). Post-kill port
  state: only `wslrelay` (38172) on 127.0.0.1 — the WSL-side mirror, intentionally left (bm_ready
  treats a dead-backend mirror as NOT ready, so no false READY).
- `BasicMemory-Supervised` registered: pwsh `-NoProfile -WindowStyle Hidden -File bm-supervised.ps1`,
  `MSFT_TaskLogonTrigger`, Hidden=True, ExecutionTimeLimit=PT0S. State=Running. VERIFIED.
- bm-supervised.ps1 v4: `-ProcessNameFallback` added; WarmupGraceSec 180→300 (measured cold
  semantic start ~3.5min left only ~26s margin inside 180s).
- Serving chain: shim `basic-memory.exe` → venv python → server python (the LISTENER, e.g. 59024
  on 172.19.16.1:18765). The netsh portproxy row is stale/inactive (OPEN-LOOP).

HEALTHY (two independent signals):
1. events log: `verdict=HEALTHY alive=True pid=35664 readiness=READY/0 ... churn=25 latched=False`
   (14:31:57, repeated consecutive ticks), held by FOUND-BY-FALLBACK lines.
2. Direct probe: `C:\Python314\python.exe C:\Users\Prekzursil\.basic-memory\bm_ready.py` →
   `READY via 172.19.16.1`, exit=0. Attempt 1 of 3. Supervisor adoption re-proven: cycling the
   supervisor re-found the live daemon (FOUND-BY-FALLBACK, churn unchanged 25, no new start).

Kill-drill (14:35:12Z, kill shim 35664 once):
- `restartedLines since drill = 1` (churn 25→26, newPid=47324, backoff 334ms, evidence captured
  BEFORE the kill), `latch lines (precise: NOTIFY [LATCH|action=latched|[ALERT]) = 0`,
  `healthyTicks >= 4`, state json `lastVerdict=HEALTHY latched=False churnTotal=26 ownPid=47324`,
  new daemon READY ~70s after restart, probe exit=0. EXACTLY-ONE-RESTART + HEALTHY + no latch: VERIFIED.

## 5. Honest incidents (mine, disclosed)

- Killed a correctly-behaving task instance at 17:20 believing it "stuck": my probe used the
  brief's log path `...supervise\basic-memory\events.log` (subdir form) — real path is FLAT
  `...supervise\basic-memory.events.log`. The instance had been faithfully LATCHED-refusing and
  notifying `operator action required: -ClearLatch` (notify.log 14:20:44Z). Instrument error, not
  system error (§3c/single-signal). Recovered: ClearLatch (operator action; latch inherited churn=24
  from PRIOR pilot attempts) → restart → HEALTHY.
- Same wrong-path probe briefly read Write-SupEvent as failing; raw `cmd /c dir` settled it.

## 6. Claims ledger

| # | Claim | Tag | Evidence |
|---|-------|-----|----------|
| 1 | fallback liveness works (find + adopt + hold) | VERIFIED | §1 log line; §4 adoption (churn unchanged); selftest C9.2 |
| 2 | needle specificity (no same-name adoption w/o needle) | VERIFIED | selftest C9.3 got-line |
| 3 | stop-refusal on fallback-found protected pid | VERIFIED | selftest C9.4 |
| 4 | pidfile outranks fallback | VERIFIED | selftest C9.5 |
| 5 | selftest 31/31 green | VERIFIED | `SUCCESS:supervise-selftest 31/31`, exit 0 |
| 6 | commit pushed (no force) | VERIFIED | `ee21a2fb0..6a206a7e4` + ls-remote |
| 7 | bm HEALTHY under BasicMemory-Supervised | VERIFIED | events + bm_ready exit 0 |
| 8 | kill-drill: exactly-one restart, no latch | VERIFIED | §4 counts + state json |
| 9 | shim-kill chain-complete | VERIFIED (2 samples) / INFERRED general ~70% | §1 |
| 10 | warmup 300s sufficient for cold restart | INFERRED ~85% (restart hit READY in ~70s warm-cached; a fully cold start measured ~210s < 300s) | §4 timings |

OPEN-LOOPS appended (2 entries): local-branch clean-tree `git pull --rebase`; stale portproxy row.
Not done (out of lane scope, deliberately): unregistering/repurposing old task (left Disabled for
rollback), portproxy row removal (owned by the watchdog maintainer).
