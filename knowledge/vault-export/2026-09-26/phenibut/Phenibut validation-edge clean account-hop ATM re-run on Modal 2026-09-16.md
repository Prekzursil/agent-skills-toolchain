---
title: Phenibut validation-edge clean account-hop ATM re-run on Modal 2026-09-16
type: note
permalink: main/phenibut/phenibut-validation-edge-clean-account-hop-atm-re-run-on-modal-2026-09-16
tags:
- phenibut
- atm
- modal
- checkpoint
- account-hop
- snapguard
- paper-1
---

# Phenibut validation-edge clean account-hop ATM re-run on Modal (16.09.2026)

Paper 1's validation edge R_phenibut → arbaclofen_R failed its own acceptance gate (12/22 replicas silenced by the REMDSteps mod-5000 phase bug on the 2026-06-16 restored run). Scaleway account suspended, Civo read-only/quota-blocked; owner chose option B: Modal, hopping accounts, "as clean as" an uninterrupted fresh run. **COMPLETE 2026-09-16 04:23, gate PASS.** Code `D:/Research/projects/phenibut/compute/modal_scripts/valid_clean/`; receipts `compute/modal_ckpt_2026-09-15/valid_clean/`; data `compute/atm-data/work/valid_rerun_2026-09-15/`; full record `docs/OPEN_LOOPS_2026-09-15.md` B5.

## Result
- [fact] **ΔΔG = −1.890 ± 0.256 kcal/mol (naive UWHAM), ±0.368 autocorrelation-corrected (mean-g), ±0.713 worst-state-g**; legs +10.496 ± 0.178 (R-phenibut end) / +12.386 ± 0.184 (arbaclofen end); 3,528 pooled rows, 22 λ-states (152–167 each), 160/161 samples per replica. Experiment −1.6 to −2.0 → **the computed value sits INSIDE the measured range** (the withdrawn −2.61 ± 0.45 sat outside it).
- [fact] GATE PASS: 22/22 replicas healthy, all in phase, no empty and no thin state. Diagnostics: mean g 2.068, worst g 7.747, N_eff 2,503/3,528 (71%), worst adjacent overlap 0.156 (pair 15-16), 0 round trips vs 0.17 expected, 8.7/22 states visited.
- [fact] **Independently recomputed** on a second machine from the harvested files with the vendored UWHAM: −1.8898 ± 0.2561, differing from the container's number by 0.00025 kcal/mol.
- [fact] Cost ≈ $105.3 across 5 segments / 4 accounts (prekzursil1993 → andreivisalon2002 → prekzursil1993 → mariusvisalon70 → prekzursiltr), 00:06–04:23, ~0.97 samples/min on 8× H100.
- [decision] Propagated to RESULTS.md, Paper 1 (12 sites incl. Table 1, §3.1, Fig 1/5 captions, §2.3 hardware, §2.5 overlap list, §4.1, conclusion, SI-2, SI-5), figures 1/5/8 regenerated, `verify_numbers.py` new token group (Paper 1 111/111, Paper B 190/190), PDFs rebuilt and verified.

## The mechanism that made hopping clean
- [decision] A resume is admissible only from a snapguard snapshot: checkpoint set AToM declared valid (ckpt_is_valid mtime unchanged across the copy), per replica REMDSteps % 5000 == 0, REMDSteps == (RECycle-1)*5000, rows == REMDSteps/5000, frames == REMDSteps/50000 (a queued frame rebuilt from checkpoint positions with OpenMM labels step (k-1)*interval), REStateId a permutation of 0..21, sha256 on every file. Orphan rows/frames after the checkpoint are dropped (`orphan_rows_dropped=8` observed live in segment 1).
- [decision] Identical software on every account: image built only from an explicit conda lock (272 URLs with md5) + pip pin of AToM 9403e380; runtime fingerprint 278bc8dc… must match or HALT. OpenMM 8.5.2.dev-36a30cb, the same string as the August Scaleway runs.
- [fact] Every hop's restore matched exactly: pooled rows before launch == the locally verified snapshot's pooled rows (1392/1392, 2340/2340, 2568/2568). Planned verification hop: all 22 replicas advanced 3-4 cycles past restore, rows == REMDSteps/5000 on every replica.
- [fact] **Unattended crash recovery proven**: a container died mid-cycle-119 with no traceback; Modal re-ran the input 16 min later and `_production` restored snap_00038 by itself (~2 samples recomputed). Symptom: status.json frozen, snapshot gap, min samples going BACKWARDS, a second production_*.log on the volume.
- [fact] The mirror's sha256 gate fired live on a half-written archive (seq 35) and fell back to seq 34 — a partial archive can never become a resume point.

## Modal / AToM gotchas (verified in source or live)
- [fact] Modal 1.5.5 `FunctionCall.get(timeout=0)` on an unfinished call raises the BUILTIN TimeoutError (`_functions.py:334`), an OSError subclass — a classifier with an OSError/transient branch treats every healthy poll as a network error. Caught live 2 min after launch; stubbed unit tests could not see it. **Poll a real call once before trusting any classifier.**
- [fact] `FunctionCall.cancel()` defaults terminate_containers=False (container + children keep billing until scale-down); use cancel(terminate_containers=True). `get_current_stats().num_total_runners` counts idle warm containers — use backlog + num_running_inputs to detect a live writer. `app stop` on a stopped app exits non-zero with "already stopped". `modal volume get <dir> <missing local path>` collapses files onto one path — mkdir first.
- [fact] AToM logs one "Worker using Reference OpenMM platform" per start: the compute=False service worker (openmm_async_re.py:482-484, ommworker.py:248-249), not a compute node; canonical seed-1 logs show the same pattern.
- [fact] run_valid.py had LIG2N="S_phenibut" despite claiming byte-identity with run_enantio except JOBNAME; fixed to arbaclofen_R before launch. Exact smoke check: pdb L2 − arbaclofen_R.sdf translation == DISPLACEMENT [59.78, 10.83, 22.92] to 9.6e-5 Å (a centroid heuristic falsely failed at 3.26 Å = the docked-pose centroid gap).
- [decision] Improvement for the next run: the fixed $8 hop floor fired at 157/160 samples, forcing a full hop for ~3 samples while the remaining $7.80 was ≈15 min of runtime. Hop when the remaining budget cannot cover estimated remaining work; keep the fixed floor as fallback.

## Relations
- relates_to [[Modal remaining is 42.50 usage cap not 30 credits]]
- relates_to [[Databricks SQL GPN autopsy splice break + ECC protocol 2026-09-13]]
