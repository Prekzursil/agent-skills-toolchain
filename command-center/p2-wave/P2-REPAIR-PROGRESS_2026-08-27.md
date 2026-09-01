# P2 G-1 repair progress (parallel coordinator, started 28.08.2026 00:45 EEST)

## Status: IN PROGRESS — recover-first, collision-aware

## Recovered state (Step 0)
- Baseline (P2-GREEN-STATUS_2026-08-27.md, verified twice): **1043 ok / 964 fail of 2007**.
- Class split regenerated 27.08 23:30 (`g1-shards/classes.json`): mod=16, probe-missing=8,
  probe-exit=933, sha=4, predicate=3, schema=0. remaining_fp `f580be3f…bda0406`.
- **Prior sequential run (agent 5ee04101) DETECTED LIVE at 28.08 00:45**: its log
  `ovh-monitor/g1-repair-claude_2026-08-27.log` written 00:40:25; WSL shows
  `g1_remeasure_fails.py` + 7 workers actively measuring (pass 2 over the fail set).
- Prior run progress already on disk (from its log, 112 entries):
  - sha class CLEARED: ARC-0052, ARC-0059, CNF-0001, WFA-0078, ADV-0010 (adopt+sha-refresh).
  - probe-missing mostly cleared: IMP-0149, TST-0187, TST-0224, TST-0225 OK.
  - mod class 4/16 cleared: IMP-0199 (agentspec.evals.simulator), IMP-0195
    (agentspec.reachability), IMP-0273 (council.participants.select_adversarial),
    TST-0191 (lib.codex_invocation). 12 mod IDs remain: IMP-0417/0419/0446/0471/0479,
    SYN-0013, TST-0007, TST-0114, TST-0150, TST-0316, TST-0333, WFA-0004.
  - timeout-pass1 remeasure: many probe-exit:124 flap to OK under low load.
- Lockfile `ovh-monitor/g1-repair.lock` created by this coordinator 00:46 (was absent).

## Coordination decision
Prior run owns the WSL measure bottleneck and shared-module edits right now. This coordinator:
1. Does NOT rsync or measure while the prior run's remeasure is active.
2. Does NOT touch shared modules while the prior run is live (it is landing mod fixes).
3. Launches Windows-only per-shard subagent batches (6-8 wide) on probe-exit shards,
   skipping IDs already OK in the prior log / latest jsonl; subagents report touched IDs
   and any new shared-module gaps; NO subagent rsyncs or measures.
4. Rsync + batch remeasure happens only when WSL goes idle (prior pass finished/stale).

## Batches
(none launched yet — updated below as they run)

## Resume instructions
- Read this file + `ovh-monitor/g1-repair-claude_2026-08-27.log` (append-only) +
  `g1-shards/*.result.json` (28.08 timestamps are this run's; 26.08 are the old Grok wave).
- Latest full census: `ovh-monitor/g1-local-full.jsonl` (27.08 12:12Z, 1043/964);
  prior-run remeasure appends live results to its own jsonl (see seed-stage/g1_remeasure_fails.py).
- Before measuring: verify no `g1_remeasure_fails.py`/`g1_remeasure_all.py` running in WSL
  (`wsl.exe bash -lc 'pgrep -af g1_remeasure'`); then `_g1_rsync.sh`; then measure with
  G1_WORKERS<=8.
- Fail-closed: green ONLY at full-census 2007/2007 + independent recount + 12-ID spot-check.
