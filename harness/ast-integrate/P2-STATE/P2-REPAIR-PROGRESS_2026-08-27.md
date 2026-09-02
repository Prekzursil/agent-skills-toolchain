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

## Coordinator 02.09 takeover (cursor-coordinator-0209, started 02.09 02:18 EEST)
- **Recovered state:** prior coordinator fe344239 dead since 29.08 06:22 (Batch C launched, no
  result files ever landed). WSL idle at takeover. Lock `g1-repair.lock` rewritten. Batch A/B
  results in `g1-shards/_claude28/shard-*.result.json`: **308 units edited (unmeasured)**, 218
  module-gap keys / 228 IDs, 63 unresolved. `delivery-pull/` is EMPTY — no salvage trees.
- **Root cause of the shared-module class:** `seed-stage/_emit_g1_modules.py` generated `_NS`
  placeholder modules (`# g1-surface: generated`, 513 files under tools/ platform/ command-center/)
  for every import harvested from probes. Real implementations never landed; each must be written
  to the probe contract. `_NS.__repr__` even has a doubled-brace bug (`<g1 {self._name}>`).
- **Strategy switch (owner + orchestrator, 02.09 02:28):** NO shard fan-out (no grok batches).
  Coordinator repairs directly, serially; regen wave runs in the background as a Windows-side
  respawn loop; optional ≤2 fable helpers only for whole independent clusters when free RAM ≥ 6 GB.
- **Overlay fix:** `_g1_remaining_fails.py`/`_g1_cluster_members.py` now also overlay
  `g1-fails-rerun.jsonl` and order repair-claude jsonl by mtime. Overlay at takeover: **893 fails**
  (`repair-claude/ids-remaining-0209.txt`). Landscape: `repair-claude/landscape-0209-pre.json`
  (612 signatures; ~200 are shared-module exceptions; 22 timeouts; 14 no-write-receipts).
- **New tools (seed-stage/):** `_g1_regen_par.py` (parallel resumable regen+ALWAYS-measure →
  repair-claude/<wave>.jsonl), `_g1_respawn.ps1` (Windows respawn loop), `_g1_landscape.py`
  (signature clustering), `_g1_probe_survey.py` (files/imports/tail per ID), `_g1_gaps_agg.py`,
  `_g1_sync_measure.sh` (copy specific paths to mirror + measure + optional record).
- **Wave `wave-regen-0209`** (02:34, 6 workers, 893 IDs): running via `_g1_respawn.ps1`; progress
  `repair-claude/wave-regen-0209.jsonl`. Resume: rerun the same respawn command (skips done IDs).
- **Hand repairs (wave-hand-0209):** IMP-0021 real `tools/plugin/longpath_fs.py` → SUCCESS:delivered.

## Resume instructions
- Read this file + `ovh-monitor/g1-repair-claude_2026-08-27.log` (append-only) +
  `g1-shards/*.result.json` (28.08 timestamps are this run's; 26.08 are the old Grok wave).
- Latest full census: `ovh-monitor/g1-local-full.jsonl` (27.08 12:12Z, 1043/964);
  prior-run remeasure appends live results to its own jsonl (see seed-stage/g1_remeasure_fails.py).
- Before measuring: verify no `g1_remeasure_fails.py`/`g1_remeasure_all.py` running in WSL
  (`wsl.exe bash -lc 'pgrep -af g1_remeasure'`); then `_g1_rsync.sh`; then measure with
  G1_WORKERS<=8.
- Fail-closed: green ONLY at full-census 2007/2007 + independent recount + 12-ID spot-check.

## Cloud orchestrator 02.09 (cloud-p2-orchestrator-0209, started 02.09 06:21 EEST, native Linux)
- **Where:** repo `Prekzursil/agent-skills-toolchain`, branch `p2/loop-to-green-2026-09-02` (from
  `handoff/cloud-agent-2026-09-02` @ f3a650220). The captured tree `harness/ast-integrate/` IS the
  workspace: no WSL, no rsync mirror, no Windows copy-back. Box: 8 vCPU, 47 GB RAM, Python 3.12.3.
- **Environment (recorded so it is reproducible):** `pip install --break-system-packages jsonschema
  referencing` (4.26.0); `p2_jsonschema_hook.py` + `sitecustomize_jsonschema.py` + `p2g1.pth` copied
  into the user site exactly as `_g1_boot.sh` does (`python3 -c 'import p2_jsonschema_hook'` → HOOK-OK).
- **Path adaptation (step 1):** new `seed-stage/_g1_paths.py` resolves ROOT/WIN/MON/LOG/CATALOG:
  `AST_INTEGRATE_ROOT` → Windows mirror layout when `/mnt/c/...` exists → else the repo tree the file
  lives in (`WIN == ROOT`, `NATIVE=True`). `_g1_remaining_fails.py`, `_g1_cluster_members.py`,
  `_g1_landscape.py`, `_g1_regen_par.py` now import it (owner's WSL flow unchanged when the mirror
  exists). `_g1_regen_par.py` additionally: `ALL` ids-file = whole catalog (a census as a wave),
  copy-back is a no-op when native, rows carry `ts`/`secs`/`cls` (same taxonomy as
  `g1_remeasure_all.one`). `_g1_sync_measure.sh` is not needed natively (its two halves are: edit in
  place, then `_g1_regen_par.py <ids> <wave> --no-regen`).
- **Overlay ordering fix:** in a git checkout every jsonl carries the checkout mtime, so the mtime
  sort in the overlay tools was arbitrary (measured: 692 fails by mtime order vs 668 by chronology —
  24 units flipped). `_g1_paths.overlay_sources()` now pins the legacy waves in ledger order
  (mod-pass1 → timeout-pass1 → batch6-predicate → wave-regen-listget → wave-regen-full →
  wave-regen-0209), then cloud waves `w0902-NN-*` by name.
- **Baseline reproduced (step 1, disk-verified):**
  - overlay WITHOUT `wave-regen-0209.jsonl` = **893 fails**, set-identical to
    `repair-claude/ids-remaining-0209.txt` (diff 0) — the 02:28 takeover figure.
  - `wave-regen-0209.jsonl` is COMPLETE in the capture (893 rows, 893 unique ids: 225 ok / 668 fail;
    the owner-side respawn loop finished before the 05:40 capture) → current overlay = **668 fails**
    (`python3 seed-stage/_g1_remaining_fails.py` → `total=2007 fails=668`).
  - Native single-unit measure works and reproduces landscape signatures byte-for-byte (IMP-0033
    `'tuple' object has no attribute 'get'`, ADV-0103 `CouncilSpecBuilder ... spec_id`, TST-0013
    `Result ... rejection_reason`); ~1.1–2.6 s per unit natively (vs ~40 s/unit under WSL).
  - Smoke wave `w0902-00-smoke` (5 ids, 5 workers): 2 ok / 3 fail, rows + log lines landed.
- **Commands (step 1):** `cd harness/ast-integrate/command-center/p2-wave/seed-stage && python3
  _g1_paths.py && python3 _g1_remaining_fails.py /tmp/ids.txt`; single unit: `cd harness/ast-integrate
  && python3 command-center/p2-wave/_measure_one_delivered.py <ID>`; wave: `G1_WORKERS=8 python3
  command-center/p2-wave/seed-stage/_g1_regen_par.py <ids|ALL> <w0902-NN-name> [--no-regen]`.
- **Parallelism:** sanctioned here (cloud VM, 47 GB free); 8 workers. Every repaired unit is
  re-measured by a wave row before it counts. Green stays fail-closed: full native census 2007/2007
  + independent recount + 12-ID spot-check.

### Step 2 (02.09 06:35–07:05 EEST): native full census + a correction the ledger must carry
- **Census `w0902-01-census-native`** (`G1_WORKERS=8 python3 seed-stage/_g1_regen_par.py ALL
  w0902-01-census-native --no-regen`, run in-tree): **2007/2007 measured, 1281 ok / 726 fail**, 1236 s
  wall (8 workers; median 1.8 s/unit, p90 5.0 s, max 315.7 s). Classes: probe-exit 707,
  probe-file-missing 12, ModuleNotFoundError 5, schema-ref 1, self-declared 1. Rows carry `ts`/`secs`/`cls`.
  vs the 668 overlay: 86 newly failing, 28 newly ok (delta list kept in the wave rows themselves).
- **Correction (disk-verified):** running probes IN the git tree is wrong here. Probes write receipts,
  fixtures, `deps/` vendoring, zip builds and even nested git repos into their own dirs and into
  `tools/` fixtures; `git add -A` swept **3,105 added files (2,730 under probes/*/deps), 12 embedded git
  repos as gitlinks, 205 probe-rewritten fixtures** into local commit `5ca049736`, and GitHub rejected
  the push (GH001: `probes/ADV-0024/_work/.../blob.bin` 2 GB, `probes/AUD-0090/deps/.../semgrep-core`
  242 MB). Neither `5ca049736` nor its local follow-up `da8f8558c` ever reached the remote; the branch
  was rebuilt from the remote head `970d7ba21` with ONE clean commit (`75e5b40fd`) holding only the
  intended paths (tree verified equal to the capture except ledgers/tools). Not a force-push, no
  published history changed. Rule from here: **never `git add -A`; add explicit paths only.**
- **Measurement now runs in a mirror, as on the owner's box:** `_g1_paths.py` has two roles —
  `WIN` = state of record (the git tree), `ROOT` = execution mirror `~/p2-g1` (`G1_MIRROR`);
  `COPY_BACK=True` so regen results (artifact + SUBAGENT-RETURN + MANIFEST) flow mirror → record exactly
  as `_g1_regen_par.py` did on WSL. Sync: `bash seed-stage/_g1_rsync.sh` (falls back to
  `_g1_mirror_sync.py`, an rsync-free size+mtime copier, because the VM has no rsync/sudo): 47,360
  files in 9 s. Persistent-mirror semantics (no delete), matching the owner's flow. `.gitignore` gained
  the capture's ExtraExcludeDirs names under `probes/*/` plus three probe-built git repos as a backstop.
  Smoke `w0902-02-smoke-mirror` (5 ids): identical verdicts to in-tree; repo tree untouched.
- **Environment classes seen in the 86 newly-failing (to be split, not guessed):** (a) probes that run
  `git` against the tree root or assert a fixture is NOT inside a repo — the in-tree run sat inside
  `/workspace/.git` (AUD-0010, AUD-0019); the mirror is outside any repo; (b) cross-unit side-effect
  dependencies (ADV-0018 reads `17-DECISION-LOG.md` that another unit's probe writes) — a persistent
  mirror satisfies these on the second pass; (c) load-sensitive timing probes (ARC-0032 queueing ratio);
  (d) live-tree fingerprint probes (ARC-0101 `files_parsed art=273 live=274`, ADV-0127) — regen refreshes
  them; (e) possible capture gaps (ADV-0011 `probes/CNF-0153/known-clean/package-lock.json`,
  ARC-0082 `blueprints/workflows/wf.research.archival.json`) → CAPTURE-GAPS.md once confirmed;
  (f) EOL-normalisation of the capture (`.gitattributes eol=lf`) vs probes that test EOL handling
  (ADV-0017) — to be measured before it is called a gap.
- Advisors launched 06:45 (council: skeptic/pragmatist/critic; gem-hunt: prune, meta, native, frontier,
  false-green) as read-only background subagents; verdicts land in P2-STATE/ADVISORS-0209.md when in.

### Step 3 (02.09 07:05–07:50 EEST): council pre-passes, tripwire, writers dispatched
- **Council verdict** (P2-STATE/ADVISORS-0209.md, `/tmp/council/*.md`): the 379-file denominator is
  wrong — root `marketplace/`, `plugin/`, `workflow_foundry/` are `__path__` shims so their 160 root
  placeholders are dead; root `council/` (72/79 placeholders) and `router/` (7/11) were real packages
  shadowing 128 + 26 real modules under `tools/`; `find_spec` over 5,936 probe imports resolves to
  ~92 live placeholders, 77 direct-importer units (66 FAIL / 11 OK); 634 failing units never touch a
  placeholder. All voices reject keeping the permissive `_NS` fallback.
- **Pre-pass 1 (resolution, commit c09477aa5):** `council/__init__.py` and `router/__init__.py`
  became shims (`__path__ = [tools/<pkg>, <root dir>]`; root kept second only for `council.builder`
  and `council.tests`, which exist nowhere else). All 7+3 real root files were re-exports or
  identical copies (diff-verified). `council.builder` now resolves to the real
  `tools/council/builder.py` module, so `council.builder.metrics` (IMP-0327) needs a real package.
- **Pre-pass 2 (tripwire, commit 46d698477):** `seed-stage/g1_placeholder_guard.py` — a meta-path
  finder installed by `g1_python.py`; `G1_PLACEHOLDER_MODE=trace` logs `unit\tmodule\torigin` for
  every generated module a probe loads (direct or transitive) → the exact dependency/regression set;
  `strict` raises `ImportError: G1-STRICT placeholder module ...` → the unit fails. Verified in a dev
  mirror: TST-0261 strict → fails on `council.tests`; ARC-0052 / IMP-0327 strict → SUCCESS.
  `_g1_regen_par.py --placeholder=trace|strict` writes `<wave>.trace.tsv`; rows carry `mode`.
  **Green is defined with STRICT on** (EVAL-G1-GREEN.md C2).
- **Gem-hunt TIER-0 adopted (commit e95f989d6), both measured verdict-neutral:** (1) the 180 s
  probe timeout SIGKILLed only `/bin/sh`; the Python probe survived as an orphan (one seen alive
  9 min after rc=124, still writing). `_measure_one_delivered.run_cmd` now starts the probe in its
  own session and `os.killpg`s it on timeout. (2) The container image zeroed source mtimes, so every
  interpreter start recompiled stdlib; `_g1_regen_par.py` now warms `PYTHONPYCACHEPREFIX=/dev/shm/g1-pyc`
  once (IMP-0021: 1.96 s → 0.56 s; census throughput 1.4 → 2.8 units/s in the light stretch).
- **Tools added:** `_g1_contract_excerpt.py` (per module: placeholder names, every importing probe /
  code file, imported names, using lines, unit verdicts — searches submodule imports and the code tree),
  `_g1_blast_radius.py` (static; superseded by TRACE for shimmed packages).
- **Census `w0902-04-census-trace`** (8 workers, mirror `~/p2-g1`, warm cache, trace mode) running;
  partial trace after ~380 units: 12 distinct placeholder files across 9 units — all under `tools/`.
- **Writers dispatched 07:45 (w1–w6, private mirrors `~/p2-w1..6`, contract in `/tmp/writer-common.md`
  — STRICT measurement of every dependent, no git, no probe edits, complete-file writes):**
  w1 ADV-0126 (`marketplace.revocation_list` ×3, `marketplace.ledger`, `bench.baseline_store`);
  w2 ADV-0096/ADV-0135 (`council.quota`); w3 ADV-0103 (`council.roles` init + templates, IMP-0280 regression);
  w4 ADV-0094 (`council.budget`) + ADV-0071 (`council.topology.jury`); w5 ADV-0031 (`foundry.runtime`);
  w6 ADV-0021 (`marketplace.crypto`) + ADV-0025 (`plugin.installer`).
- **Rule adopted (autoresearch discipline):** a writer's files are committed only after its dependents
  were measured STRICT in a mirror; a regression that is not "lost the fake" reverts the module
  (ledger row first). `probe-file-missing` candidates (12 in census 01) are held for the steady-state
  mirror census before any CAPTURE-GAPS.md entry is written.

### Step 4 (02.09 07:30– EEST): module repairs landing (one commit per module, STRICT-measured dependents)
| wave/writer | module(s) | dependents (STRICT, my mirror) | result | commit |
|---|---|---|---|---|
| w4 | `tools/council/budget/__init__.py` real init (4 real dials); root twins deleted | ADV-0094 IMP-0298 IMP-0299 IMP-0325 IMP-0352 | 5/5 OK (4 FAIL→OK, 1 vacuous OK→real OK) | 706239c65 |
| w3 | `tools/council/roles/__init__.py` + `roles/templates.py` (898 lines: template registry, custom-role authoring, escalation + drift detectors); root twins deleted | IMP-0360 IMP-0280 IMP-0281 ADV-0103 | 2/4 OK (IMP-0360 FAIL→OK; IMP-0280 vacuous→real OK); IMP-0281/ADV-0103 now fail on REAL-module drift: captured `tools/council/sdk.py` (6221 B) and `roles/guard.py` (2922 B) are later, smaller re-implementations than the originals both manifests pin (21107 B / 14048 B) — two units' deliverables overwrote the same files → union contract, writer w10 | 5998fbe0a |
| w2 | `tools/council/quota/__init__.py` + `quota/targets.py` (581 lines, CouncilSpec target evaluator); root twins deleted | ADV-0096 IMP-0301 ADV-0135 RES-0165 | 2/4 OK; ADV-0135 = probe-vs-own-generator conflict + `unique_ideas.py` captured degraded (IMP-0300 manifest 14829 B vs captured 8245 B); RES-0165 same family | 342a33a9e |
| w5 | `tools/foundry/runtime.py` (349 lines: typed workflow runtime) | ADV-0031 IMP-0209 IMP-0154 IMP-0155 IMP-0164 IMP-0254 WFA-0134 IMP-0177 CNF-0082 IMP-0193 WFA-0132 IMP-0175 | 8/12 OK (7 FAIL→OK, IMP-0177 stays); 4 now fail on `tools/foundry/scout.py` / `tournament.py` drift | 55c904100 |
| regen | `w0902-06-regen-nonph`: 640 non-placeholder fails, STRICT | — | 27 cleared by own `write_receipts.py`; 523/549 regens fail (they re-run the failing probes) | c2b23b9d5 |
| w4b | `tools/council/topology/jury.py` (805 lines: jury topology on the RecordingKernel turn-log protocol) | ADV-0071 IMP-0285 | 2/2 FAIL→OK | 61755a565 |
| w6 | `tools/marketplace/crypto.py` (236) + `tools/plugin/installer.py` (625); root twins deleted | ADV-0021 ADV-0025 IMP-0118 ADV-0061 IMP-0086 RES-0055 | 2/6 OK; IMP-0118 BLOCKED-BY `marketplace.features`; ADV-0061/IMP-0086 = `tools/marketplace/install.py` drift (batch s00); RES-0055 = env `referencing.exceptions` (also WFA-0140) | 1f88a794d |
| fix | measurer sets `AST_INTEGRATE_ROOT` unconditionally: the user-site `.pth` hook set it to `~/p2-g1` inside the measure process, so a probe measured in another mirror imported from the main mirror (false-green F4, reproduced: ADV-0021 showed the main mirror's placeholder). Wave driver was immune (`-s` + explicit env); manual verifications re-run hermetically, all landed modules re-verified green | — | — | 3f4433ab4 |
| w1 | `marketplace.revocation_list` (init, revocation.py 1047, degrade.py 301), `marketplace.ledger` (280), `bench.baseline_store` (414) | ADV-0126 IMP-0079 TST-0229 | 0/3 (import-clean; blocked by `work_claim.py`, 4 more revocation_list placeholders, `bench/runner.run_benchmark` → w1b) | a15cc68b0 |
| w8 | `council.stopping` init + `expr.py` (1081) + `spec_examples.py` (replaces a real-surface stub); root twins deleted | IMP-0308 IMP-0310 TST-0281 IMP-0309 TST-0264 TST-0283 | 3/6 OK (2 FAIL→OK); rest blocked by `minimum.py`, `evidence_saturation.py`, `owner_ask.build_packet`, `simulate.run_council` (→ w8b) | 80418b0e3 |
| p00-ADV | batch: `archive_extract.py` containment pre-pass, `installer.py` `on_extract` observer, 3 emitter regenerations | 12 ADV units | 5/12 OK; 2 CAPTURE-GAPs (ADV-0011, ADV-0016); 5 open loops (ADV-0004/0006/0009/0020/0033) | 629a84d72 |
| trace | `w0902-07-trace-ok`: 1312 OK units traced with BOTH stub markers | — | 34 OK units load a stub (22 files: 13 real-surface, 5 generated, 4 already replaced); 8 regen-cleared census-type units flapped back (BLD-0004 AUD-0057 RES-0107 AUD-0095 RES-0193 WFA-0133 ADV-0017 IMP-0264) — fingerprint probes drift as the tree changes → regenerate them LAST | (this commit) |
| w4b/w6/w1/w9/w10/w1b/w7/w13, p42-TST/p01-ADV | see per-commit messages (`git log --oneline handoff/cloud-agent-2026-09-02..HEAD`) | — | running total after these: **~75 units FAIL→OK under STRICT, 0 regressions**; shared fixes: jsonschema fragment `$ref` (p42), VENDOR-REGISTRY `cursor`+`mechanical` (orchestrator, after p01 found 355 emitters schema-rejected), measurer hermetic root | dfaf50184 … f3a20697f |
| efficiency step (owner 07:04) | `_g1_land.py` one-shot report verifier; batches re-cut at 20 units after census 09; all 10 subagent slots kept busy | — | census `w0902-09-census-strict` (record synced 07:1x, both markers STRICT, 6 workers) running to refresh the residue; a writer's own `w0902-08-census-strict` sweep (06:52–07:06, 1402 ok / 605 fail, mirror state unpinned) is informative only | (this commit) |
| stall recovery (10:30–11:05) | nine writers went silent for 70+ min with no processes; partial reports on disk were truthful (write-as-you-go) → landed via `_g1_land.py`: w11b 5/5, s00 6, w8b 5, p43 4, p22 11/11, p23 2, w13 21/24; w12's regenerations never left its mirror → w12b resumes from `~/p2-w12` | — | **running total ≈115 units FAIL→OK, 0 regressions**; census 09 STRICT = 1402/605 before these landings | 150d3f9bf…4534b7c88 |
| b3-p09-CNF / b3-p10-CNF (08:13–08:50) | CNF residue: emitters mirror `report.*` rows to the document root (TOPLEVEL-VS-REPORT class, 6 units), CNF-0018 image ships `id_normalize.py`, CNF-0101 CRLF fixtures re-seeded (+`.gitattributes -text`), 4 fingerprint units regenerated | 40 CNF units | 15/40 OK (10 + 5); 8 more CNF members of the class handed to class writer `c1-TOPLEVEL` (15 units incl. ADV/AUD/BLD/TST members); registers: CNF-0026/0112/0129 gaps, CNF-0027<->0033/0065 XDEP, CNF-0104 ENV, CNF-0021 vendor token | 71586259a, 396cf6c68 |
| fix (09:00) | `_g1_paths`: explicit `G1_MIRROR` beats a leaked `AST_INTEGRATE_ROOT` (a lander wave silently measured in another writer's mirror → 4 false disagreements); wave header prints `root=`; writers now set env inline per command | — | re-measure of b3-p09 in the right mirror: 10/10 agree | 71586259a |
| landings 09:05–09:20 | b4-p08-IMP 12/12 (8 real modules across agentspec/agentrail/workflow_foundry/marketplace/blueprint_contract/event-ledger, no artifact regenerated), b4-p10-IMP 4/12 (council.order/abort/antifail.participation/quota.unique_ideas), w12b 10/10 (router.inject/lexical/embed_model/semantic_matcher + pinned model), w-council-rs 8/27 (evidence_gate, vendor_error_correlation, 4 package inits), phase3-regen 15/18 owners (127-unit reader census re-measured: 103 OK, 0 knock-ons; leftover-fill victims 66→4) | 78 units | +36 FAIL→OK STRICT this block; every landing re-measured in `~/p2-dev` before commit | 54a9de421 76d6778b8 4a3c397dc 2f4fed3c3 738e164a8 |
| dispatch 09:20 | c1-TOPLEVEL (class, 15), b4-p04-CNF, b4-p15/16/17-RES (12 each), w-council-rs2 (8 stubs), w-council-rs3 (6 stubs incl. delphi) + b4-p09/p11/p12-IMP in flight = 10 slots | — | all briefs carry the inline-env rule | — |
| landings 09:20–09:50 | b4-p09-IMP 11/12 + b4-p11-IMP 4/12 (both writers cut off by a platform block; partials verified), b4-p04-CNF 9(+1 fp)/12, b4-p12-IMP 7/12, c1-TOPLEVEL 14(+1 fp)/16 (class closed), w-council-rs3 4/7, b4-p15-RES 8/12, b4-p16-RES 9/12, b4-p17-RES 9/12 | 107 units | +75 FAIL→OK STRICT this block; shared: `p2_jsonschema_hook._receipt_copy` keeps root keys (90-unit regression sample clean), `completion.sites` judge binding, marketplace lockfile schema real, `.gitattributes -text` for captures/snapshots; 5 CRLF captures restored sha256-verified, 6 unrecoverable (mixed EOL) → CAPTURE-GAPS | 893b1e7f7 … d19c48207 |
| dispatch 09:50 | s01-schema-shims (shared class: 241 shims with file:///C: $refs; 9 victims now), w-council-rs4 (nested/coc/tests/unanimity + 3 drift units), b4-p11b-IMP, b4-p18/p19-RES, b4-p21-SYN, b4-p23/24/25-TST + rs2 in flight = 10 slots | — | regenerate-last list: TST-0026 CNF-0168 CNF-0157 RES-0127(census mirror) RES-0049 RES-0064 RES-0099 RES-0126 ADV-0129 CNF-0117 CNF-0125 TST-0078 CNF-0105/0116/0128/0133 CNF-0072 IMP-0431 | — |
| landings 09:50–10:00 | w-council-rs2 8/8 (eight council modules real), b4-p11b-IMP 6/6 (router.rule_matcher rewrite + trigger table, NEW router.fusion/stages/corpus, council.prep), b4-p18-RES 6/12, b4-p19-RES 6/12 (agentspec.validate _Id dict-compatible) | 38 units | +26 FAIL→OK STRICT; council tree: 26 of the 27 rs-listed stubs are now real (delphi included); registers: 7 capture gaps, RES-0163 shim-presence conflict, RES-0167/0171 premises, `.gitattributes -text` for fixtures/sources + fixtures/snapshots | 91a9bee15 … cc4657297 |
| dispatch 10:00 | b4-p26/27/28/29-TST (12 each) + s01, rs4, b4-p21-SYN, b4-p23/24/25-TST in flight = 10 slots; queue left: p30-TST p31/32/33-WFA p02-BLD p14-REL p00-ARC p13-IMP p01-AUD p03-CC p06-CNL p05-CNF p20-RES p22-SYN | — | — | — |
| landings 10:00–10:50 | s01-schema-shims (class resolved: 230 shims regenerated portable, 0 regressions), b4-p23-TST 5/12, b4-p26 2/12 (blocked) + b4-p26b 7/10, b4-p25-TST 12/12, w-council-rs4 7/7 (council class closed: nested/coc written, root council/tests + RES-0080 shadow removed), b4-p28-TST 8/12 (three-way merge of simulate.py/unanimity.py), b4-p21-SYN 8/12 (shim definitions merged onto the portable shim), b4-p24-TST 7/12, b4-p27-TST 6/12, b4-p29-TST 8/12 (bench oracle real, 76 cases regenerated), b4-p30-TST 4/12 | 129 units | +78 FAIL→OK STRICT this block; 21 large DEFERRED units listed for a dedicated wave; every landing re-measured in `~/p2-dev` (2 fingerprint disagreements: TST-0124, SYN-0022 → re-emitted) | 1e6244f01 … 196751ad3 |
- Tooling this step: `_g1_rootkey.py` (re-key fails by file to touch: 712 fails → 11 shared keys / 615 per-unit
  probe-side exceptions or assertions + 3 `MISSING:pytest` + 3 TIMEOUT); `pytest` 9.1.1 installed (environment,
  like jsonschema: three units import it). Regen wave `w0902-06-regen-nonph` (640 non-placeholder fails, STRICT, 6
  workers) running: ~12 cleared of the first 314 (regeneration alone rarely helps here — the owner's regen wave had
  already run over these).
- Running total after w1–w8 + p00: **10 module groups + 1 batch, 28 units FAIL→OK under STRICT, 0 regressions.**
- **Second stub family (w8 finding):** 129 `# g1-mod: real-surface` files ("Import surface for X (probe-derived)": default-PASS `Result`, constant returns). `g1_placeholder_guard.py` now trips on both markers (`G1_PLACEHOLDER_MARKERS` narrows). Registers opened: `P2-STATE/CAPTURE-GAPS.md`, `P2-STATE/OPEN-LOOPS-0209.md` (fail-closed: entries stay FAIL).
- Writers in flight: w1 (marketplace.revocation_list ×3, ledger, bench.baseline_store), w2 (council.quota), w5
  (foundry.runtime, 11 dependents), w6 (marketplace.crypto, plugin.installer), w7 (council.protocol, 14 units, serial),
  w8 (council.stopping + expr), w9 (council.outcomes), w10 (sdk.py + guard.py union contract).
