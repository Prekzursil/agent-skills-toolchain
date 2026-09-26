---
title: Paper A ATM productions done UWHAM still required 2026-08-26
type: note
permalink: main/phenibut/paper-a-atm-productions-done-uwham-still-required-2026-08-26
tags:
- phenibut
- atm
- gpn
- replicate
- uwham
- modal
---

valid_as_of: 2026-08-26

Both Paper A ATM GPU legs finished and harvested. ΔΔG is NOT computed. Production finishing is not GO/NO-GO.

## Done
- GPN gabapentin→pregabalin on **ovido4** call fc-01M0XQAEFMB16WQ1TZ7DEA4NFD rc=0. progress 0.99375, cycles 161–162, 22× .out 171–172 lines. Harvest: D:/Research/projects/phenibut/compute/atm_gpn_harvest_2026-08-26/
- GABA-B R→S independent replicate on **realprekzursil** call fc-01M0XPN9QMTYHRK9GVTTS7P7CX rc=0 re_setup=NO. progress 0.99375, 22× .out 159–162 (r18–r21=159). Harvest: D:/Research/projects/phenibut/compute/atm_rs_harvest_2026-08-26/
- Leftover 8×H100 boxes stopped; volumes kept. Trajectories still on those volumes.
- Pose vs 8X9 still GO 0.600 Å.
- Receipt: docs/ATM_POST_PRODUCTION_STATUS_2026-08-26.md

## Still required (CPU, minutes)
UWHAM on both harvests. Expected GPN ΔΔG ≈ −0.21 (wrong-signed ⇒ do not FEP). R→S judge vs +1.673 ± 0.321 / [+1.35, +1.99]. Canonical RESULTS.md stays +1.673 until this replicate UWHAM. Harvest is flat rN.out; analyzers expect rN/JOB.out. Local Windows has no atom_openmm (SETUP.md).

## Do not
- Start α2δ FEP until GPN ΔΔG returns and is not wrong-signed.
- Steal GPUs (none live).
- Treat mariusvisalon70 / darias-grama FAILED mid-run notes as current job homes.
- Use OVERRIDE_SAFECHECKPOINT as a standing keyword.

## Unchanged canonical
GABA-B H→Cl −2.61; GABA-B R→S +1.673 ± 0.321 (one seed); α2δ H→Cl −0.805 wrong-signed; Jaguar triad SCF ERROR 7009; FEP+ CSV still outstanding.


## Superseded — UWHAM now run (2026-08-26)
See `phenibut/paper-a-uwham-gpn-no-go-rs-replicate-magnitude-miss-2026-08-26`. GPN +12.846 NO-GO. R→S replicate +0.633 (canonical stays +1.673). Trajectories harvested.
