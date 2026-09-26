---
title: Paper A UWHAM GPN NO-GO RS replicate magnitude miss 2026-08-26
type: note
permalink: main/phenibut/paper-a-uwham-gpn-no-go-rs-replicate-magnitude-miss-2026-08-26
tags:
- phenibut
- atm
- uwham
- gpn
- replicate
- jaguar
- fep-nogo
---

valid_as_of: 2026-08-26

UWHAM done locally (~16 s, Python AToM uwham, no R). Analyzer validated: canonical GABA-B drain reproduced +1.673 ± 0.257 exactly.

## GPN gabapentin→pregabalin — FEP NO-GO
ΔΔG = **+12.846 ± 0.449** (autocorr mean-g). Experiment ≈ −0.21. Kill in a2d_atm_gpn.py (ΔΔG > +1 favors gabapentin) fired. Coverage PASS. Do **not** start α2δ FEP. Pose GO 0.600 Å does not rescue this.
Harvest: D:/Research/projects/phenibut/compute/atm_gpn_harvest_2026-08-26/ (uwham_result.json + trajectories/ 22 xtc from ovido4).

## GABA-B R→S replicate — sign OK, magnitude miss
ΔΔG = **+0.633 ± 0.302**. Seed 1 remains **+1.673 ± 0.321**. Judge window [+1.35, +1.99] missed. Experimental floor +1.42 missed. Do not overwrite RESULTS canonical; do not average. Trajectories from realprekzursil.

## Jaguar 7009 — vacuum retry NOT opportune
SCF diverged (DIIS 4.94E+02 monomer A) on vacuum zwitterion+Arg+2Asp wB97X-D3/def2-TZVP. Launch omitted protocol SCF hardening. nops=1 prints a non-converged energy. Remaining path is QM/MM, not vacuum nops=1.

Receipt: docs/ATM_UWHAM_TRAJ_JAGUAR_2026-08-26.md
