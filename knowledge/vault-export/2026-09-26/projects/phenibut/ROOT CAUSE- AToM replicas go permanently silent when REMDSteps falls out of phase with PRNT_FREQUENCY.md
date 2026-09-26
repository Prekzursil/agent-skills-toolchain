---
title: 'ROOT CAUSE: AToM replicas go permanently silent when REMDSteps falls out of
  phase with PRNT_FREQUENCY'
type: note
permalink: main/projects/phenibut/root-cause-ato-m-replicas-go-permanently-silent-when-remdsteps-falls-out-of-phase-with-prnt-frequency
tags:
- phenibut
- atm
- openmm
- fep
- root-cause
- failure-mode
- scaleway
---

# AToM-OpenMM: a replica knocked out of step-phase is silent FOREVER

**valid_as_of: 2026-08-18.** Supersedes the "cause unidentified" section of
[[atm-enantio-run-8-of-22-replicas-were-dead-while-progress-read-0.958-silent-failure]].

## The mechanism (CONFIRMED, 0/22 mispredictions)

```
local_openmm_transport.py:234   if mdsteps % job['nprnt'] == 0: ommreplica.save_out()
```

`mdsteps` grows by exactly `PRODUCTION_STEPS` per completed cycle, and `openmm_async_re.py:65` enforces `PRNT_FREQUENCY % PRODUCTION_STEPS == 0`. So **`mdsteps % nprnt` is invariant** under the per-cycle increment. A replica knocked out of phase — by an interrupted cycle recording a partial step count — can never become congruent again.

It then goes silent **forever**: on any hardware, with **no error**, while the framework keeps launching it, exchanging its state, advancing its cycle counter, and raising `progress`.

## The measurement

The counter is the **`REMDSteps` attribute of the `<Parameters>` element** inside each `r<N>/<basename>_ckpt.xml`:

```
writing (14) : 630000, 635000, 650000 ...   remainder 0
silent   (8) : r3 623000, r4 623000, r5 627000,
               r11 r12 r13 r20 r21 all 622000   remainder 3000 / 2000
```

Phase predicts silence for all 22 with zero mispredictions. It explains everything at once: why the same eight indices failed on completely different hardware, why they launched and exchanged states normally, why nothing was ever logged, and why `progress` read 0.958 while a third of the run produced nothing.

## ⚠ The field trap that made me refute this wrongly

**Do NOT read `stepCount` on the `<State>` root element.** That is OpenMM's own integrator counter — it was uniformly **850000** across all 22 replicas, silent and writing alike. I used it, got a clean uniform answer, and declared the phase hypothesis REFUTED. It was correct all along. A probe pointed at the wrong field yields a confident, clean, wrong verdict; the two counters are different quantities that both look like "steps".

## Remedy

Clearing the checkpoints so every counter restarts at 0 (hence in phase). **`RE_SETUP=YES` alone does NOT do this** — `ommreplica.__init__` calls `load_checkpoint()` unconditionally and it restores any `r<N>/*_ckpt.xml` that exists, ignoring RE_SETUP. Also, `load_checkpoint()` raises `ValueError('Bad checkpoints')` when the `ckpt_is_valid` sentinel is missing, which is what a mid-write kill leaves; that means "cannot prove safe", not "corrupt".

Use `compute/scaleway/fresh_start.sh` (backs up and verifies 22/22 before deleting anything). Confirmed: after clearing, all 22 replicas write, 0 at zero.

## The free check that prevents recurrence

`run_enantio.py` → `phase_check()` / `print_phase_check()`, wired into the `states` gate. Reads REMDSteps out of the checkpoints and names any doomed replica **before a single GPU-second is spent**. Verified with a both-states test (`test_phase_check.sh`): FIRES on the June checkpoints naming all 8 with exact remainders, quiet on the fresh run. An earlier version was **inert** — it printed nothing in either state because its upload had been silently skipped — and only the both-states test caught that.

## Operational notes earned the hard way

- `nvidia-smi` sampled between MD segments reads **0%**. Sample repeatedly: real utilization is 76–97%.
- `pkill -f <pattern>` run inline over ssh matches the ssh command line itself and kills your own session (exit 255). Keep the pattern in a script file — see `stop_run.sh`.
- AToM workers call `setproctitle("AToM worker")`, so `pgrep -f atom_openmm` matches **nothing** while four of them hold GPU contexts.
- Scaleway: `server-type list` "available" is DATACENTER STOCK, not account quota. H100-SXM-8-80G listed available while the account was **0/0**. Landed on H100-SXM-4-80G at EUR 12.771/h.
