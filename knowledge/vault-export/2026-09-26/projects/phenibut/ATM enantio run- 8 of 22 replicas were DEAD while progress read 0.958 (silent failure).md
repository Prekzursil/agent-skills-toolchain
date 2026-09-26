---
title: 'ATM enantio run: 8 of 22 replicas were DEAD while progress read 0.958 (silent
  failure)'
type: note
permalink: main/projects/phenibut/atm-enantio-run-8-of-22-replicas-were-dead-while-progress-read-0.958-silent-failure
tags:
- phenibut
- atm
- fep
- scaleway
- failure-mode
- verification
---

# ATM R→S enantio edge: the run that reported 95.8% done had 8/22 replicas producing nothing

**Measured 2026-08-18.** This overturns the premise the Scaleway H100 rental was justified on.

## The finding

Per-replica row counts in `r*/R_phenibut-S_phenibut.out` (field 1 of each row IS the λ-state index — verified because `stat.txt`'s Lambda/Lambda1/Lambda2/Alpha/Uh/W0 triples match `.out` fields 4-8 for the state named in field 1):

```
healthy (117 rows each) : 0 1 2 6 7 8 9 10 14 15 16 17 18 19   (14 of 22)
DEAD    (0 rows)        : 11 12 13 20 21                        ( 5 of 22)
STALLED (exactly 1 row) : 3 4 5                                 ( 3 of 22)
```

The four empty λ-states (11, 13, 20, 21 — **21 is λ=1.000, the S endpoint**) are the *downstream symptom*, not the disease. All four are direction −1 (leg 2), and the replicas that would have sampled them are in the dead/stalled set.

## Why "more cycles" is the WRONG remedy (this is the load-bearing correction)

A replica emitting **zero rows per cycle** does not start emitting them because you add cycles. `run_enantio.py`'s gate previously prescribed *"run more cycles / raise --max-samples"* for every coverage failure. Applied here that reproduces the identical hole at full GPU price. Fixed: the gate now reports a **replica-health verdict** (`DEAD_REPLICAS` / `NOTHING_RAN` / `UNDERSAMPLED` / `OK`) and only `UNDERSAMPLED` gets the more-cycles advice.

## Transfer truncation is RULED OUT (the obvious competing explanation)

Two mirrors of this run, copied at different times, hold **byte-identical** counts for the failing replicas — exactly `0` and exactly `104` bytes for the same eight — while the other 14 grew ~312 B → ~12,100 B between the snapshots. A truncated download does not truncate the same eight files to the same byte counts twice.
- `compute/atm-data/work/enantio/` (earlier snapshot)
- `compute/phenibut_fetch/_local_enantio/work/enantio/` (later snapshot)

## The dangerous part: the failure is SILENT

`stat.txt` showed **every** replica at cycle 116/117 and `progress` read **0.958** while 8/22 had never written a row. The framework's progress counter advanced without the work being done.

**⇒ `progress` is NOT a coverage signal and must never be the stop condition.** The stop condition is per-state coverage plus replica health.

Also: `ckpt_is_valid` said "Checkpoint files are valid" and all 22 `_ckpt.xml` were ~25 MB — **a valid checkpoint does not imply a productive replica.** That specific inference is what justified the rental and it is false.

## NOT known (stated so it is not re-asserted as fact)

The **cause** is unidentified. The per-worker `cntxt_localhost_2_*/` logs **rotate** — 28 segments retained out of ~1,600 actually run — so the scheduling history is gone, and no driver log or ATM config survives in either mirror. Workers that did run looked healthy (~29 ns/day, ~298-300 K, zero error-shaped lines). GPU/VRAM exhaustion or a replica-enumeration fault is **plausible (55-80%), not established**. Capture `cntxt_*` logs LIVE next time.

Note the earlier 8 worker contexts (`cntxt_localhost_2_0..7`). Related but NOT the same stack: [[scaleway-schrodinger-fresh-box-local-jobserverd-ignores-hosts-file-gpu-config-4-gpu-spread-wall]] is about Schrödinger's `jobserverd` dropping `CUDA_VISIBLE_DEVICES`; AToM-OpenMM's async_re is a different code path, so do not transplant that root cause without evidence.

## The gate that now prevents it

`compute/scaleway/preflight_gate.sh` — run ON the box in the first minutes. Captures a per-replica baseline at launch (necessary because a RESUME starts with prior rows, so comparing against zero makes dead replicas look alive), then requires every replica to have advanced. exit 0 continue / 1 abort / 2 too early.

Abort cost ~EUR 11-20 vs up to EUR 250 for discovering it at the end of a long run.

Relates to [[compute-monitor-preference-verbose-accurate-live-eta-user-standing-request]].
