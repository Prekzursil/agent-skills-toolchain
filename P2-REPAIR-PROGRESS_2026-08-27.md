# P2 G-1 repair progress (parallel coordinator, started 28.08.2026 00:45 EEST)

## Status: IN PROGRESS — recover-first, collision-aware, LOOP-TO-GREEN (owner standing order 29.08 07:10: never stop at PARTIAL; escalate method on stall; only a true external blocker may surface — keep repairing everything else meanwhile)

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

## Sequential run (agent 5ee04101) update — 28.08 ~04:30 EEST
- **mod class 16/16 CLEARED.** Since the snapshot above the sequential run also landed:
  IMP-0417, IMP-0419, IMP-0446, IMP-0471, IMP-0479, SYN-0013, TST-0007, TST-0114,
  TST-0150, TST-0316, TST-0333, WFA-0004 — all SUCCESS:delivered (per-unit measure).
- Bonus probe-exit clears: TST-0126 (real testinfra/noop_census), IMP-0415 (still green
  after shared completion_reducer extension), ADV-0029, IMP-0080, TST-0191.
- timeout-pass1 (81 IDs, plain retry): ok=31 fail=50 — flaky-under-load recovered.
- New shared modules landed (Windows + mirror): tools/detectors/{two_state,adapters,
  campaign,census,tests}, tools/testinfra/{noop_census,test_noop_census}, tools/
  monitorcore/monitorcore/operator_surface.py (+Cockpit surface methods), tools/
  completion/{census,tests}, tools/cross_vendor pkg, tools/worktree_shard pkg,
  tools/event-ledger/{records,writer}, tools/wfa_compat pkg, tools/vendor_adapter pkg,
  lib/completion_reducer extensions. Stub shadows moved to tools/_g1_file_to_pkg_bak/
  (cross_vendor.py, plugin/detectors.py).
- All work logged append-only in ovh-monitor/g1-repair-claude_2026-08-27.log
  (mirrored WSL<->Windows). Remaining backlog is the probe-exit class (~900 minus
  the clears above); authoritative count requires the next full remeasure pass.
  - timeout-pass1 remeasure: many probe-exit:124 flap to OK under low load.
- Lockfile `ovh-monitor/g1-repair.lock` created by this coordinator 00:46 (was absent).

## Sequential run update — 28.08 ~04:55 EEST: predicate class 3/3 CLEARED
- **CC-0003, TST-0145, WFA-0134 all SUCCESS:delivered** (logged in
  repair-claude/batch6-predicate.jsonl + the append-only log).
- CC-0003: platform/lib/completion_predicate.py gained module-level verdict/outcome
  aliases (COMPLETE/FALSE/…), skip+process kwargs on evaluate (skipped ⇒ NOT_CHECKED,
  never pass), evidence_pointer, process_exit_code forensics field, checker aliases,
  FANIN_SITES + HARD_RULES; new platform/lib/fanin/ package (7 sites re-exporting the
  ONE shared evaluate object via _site_common).
- TST-0145: tools/command-center/completion_predicate.py gained role-based
  evaluate_c05_artifact (use-vs-mention, foreign-unit naming) + substring_c05_artifact
  negative control; _c05 dispatches on artifact_text; judge conditions now _ConditionRows
  (list + dict-style .get("C05")) — IMP-0418/TST-0143 stayed green.
- WFA-0134: new real tools/foundry/completion_predicate.py (12-condition Verdict
  reducer, N/A fail-closed, exit-zero-never-success) + certification_gate/local_runner/
  tournament_runner call sites + consumer.py. Gotcha: probe1 re-derives verdicts in a
  fresh temp root and diffs reason strings byte-for-byte — reasons must never embed
  absolute paths (fixed C2/C11 to cite basenames only).
- Regression sweep of shared-judge consumers: IMP-0418, TST-0143, ADV-0116, ADV-0125,
  SYN-0021 all still SUCCESS:delivered.
- Class ledger now: mod 16/16 cleared, sha 4/4, probe-missing 8/8, predicate 3/3.
  Remaining backlog = probe-exit class (assertion failures; ~900 minus prior clears).

## Sequential run update — 28.08 ~06:05 EEST: stale-artifact discovery + full regen sweep
- **Key finding:** a large share of probe-exit fails are STALE ARTIFACTS — emitted by the
  old stub era, now mismatching the live probes (e.g. "artifact volume_sensitive_count
  None != live 5584"). Pure `write_receipts.py` regeneration fixes them with zero code.
- Pilot wave-regen-listget (19 IDs): 6 cleared by regeneration alone (ADV-0127,
  AUD-0057, CNF-0147, IMP-0015, IMP-0440, TST-0069); 13 need real per-unit fixes
  (recorded with tails in repair-claude/wave-regen-listget.jsonl).
- New tools (seed-stage/): `_g1_regen_wave.py` (resumable regen+copy-back+measure per
  ID, appends to repair-claude/<wave>.jsonl + the append-only log), `_g1_remaining_fails.py`
  (latest full jsonl overlaid with all repair-claude/*.jsonl → current fail list),
  `_g1_cluster_members.py` (cluster member IDs + sample tail, repair-aware).
- Current arithmetic: 2007 total, **1086 ok / 921 fail** after overlaying all repair logs.
- **RUNNING:** `wave-regen-full` — full regen sweep over all 921 remaining fails
  (WSL, sequential, ~40 s/unit ≈ 10 h). Resumable: rerun the same command and it skips
  done IDs. Progress: `ovh-monitor/repair-claude/wave-regen-full.jsonl`.
- After the sweep: the residue is the true hand-repair backlog; cluster it with
  `_g1_cluster_members.py` and fix in waves (biggest known: council `_NS` stubs ~13 IDs,
  "schema accepted garbage" ~13 IDs, per-unit assertion drift).

## Coordination decision
Prior run owns the WSL measure bottleneck and shared-module edits right now. This coordinator:
1. Does NOT rsync or measure while the prior run's remeasure is active.
2. Does NOT touch shared modules while the prior run is live (it is landing mod fixes).
3. Launches Windows-only per-shard subagent batches (6-8 wide) on probe-exit shards,
   skipping IDs already OK in the prior log / latest jsonl; subagents report touched IDs
   and any new shared-module gaps; NO subagent rsyncs or measures.
4. Rsync + batch remeasure happens only when WSL goes idle (prior pass finished/stale).

## Batches
- **Batch A (28.08 ~01:00, fable):** shards 00-05. Results on disk for 01-05 (edited: 21/13/22/18/5).
  shard-00 worker died mid-run (4 edited, no result.json).
- **Batch B (28.08 ~01:05, fable):** shards 06-11 + shard-00 resume. Session interrupted 29.08 ~03:04,
  but results landed on disk for 06-11 (edited: 16/14/20/13/15/14). shard-00 still no result file.
- **Recovery point 29.08 06:20:** prior sequential run DEAD (log last 28.08 07:01, its final act was a
  `wave-regen-full` emit pass over AUD-*). WSL idle. Aggregate: 171 units edited across shards 01-11,
  135 distinct shared-module gaps catalogued (Phase 1 backlog). Sibling shard-07 worker possibly live
  (fresh 06:14 file writes) — shard-07 excluded from new dispatch.
- **Batch C (29.08 06:25, grok-4.6-xhigh per owner):** shard-00(retry) + shards 12-17, 7 subagents,
  background. Windows-only edits; coordinator holds rsync/measure.

## Resume instructions
- Read this file + `ovh-monitor/g1-repair-claude_2026-08-27.log` (append-only) +
  `g1-shards/*.result.json` (28.08 timestamps are this run's; 26.08 are the old Grok wave).
- Latest full census: `ovh-monitor/g1-local-full.jsonl` (27.08 12:12Z, 1043/964);
  prior-run remeasure appends live results to its own jsonl (see seed-stage/g1_remeasure_fails.py).
- Before measuring: verify no `g1_remeasure_fails.py`/`g1_remeasure_all.py` running in WSL
  (`wsl.exe bash -lc 'pgrep -af g1_remeasure'`); then `_g1_rsync.sh`; then measure with
  G1_WORKERS<=8.
- Fail-closed: green ONLY at full-census 2007/2007 + independent recount + 12-ID spot-check.
