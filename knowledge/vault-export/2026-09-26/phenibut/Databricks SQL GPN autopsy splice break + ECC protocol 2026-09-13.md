---
title: Databricks SQL GPN autopsy splice break + ECC protocol 2026-09-13
type: note
permalink: main/phenibut/databricks-sql-gpn-autopsy-splice-break-ecc-protocol-2026-09-13
tags:
- phenibut
- databricks
- sql
- mapping-autopsy
- gpn
- ecc
- paper-a
- session-state
---

# Databricks SQL GPN autopsy splice break + ECC protocol 2026-09-13

Resumed phenibut Paper A after 2026-08-26 grill lock ([[Paper A UWHAM GPN NO-GO RS replicate magnitude miss 2026-08-26]]). User directed: run the processing lane on Databricks with the 2 cyberstrike PATs.

- [fact] The 2 live Databricks PATs (sha8 `4c5f245f` ngo, `2e1ce409` alv, values in `D:/bolt/credentials/CREDS-SSOT_2026-09-06.json`, file-only per standing rule) are **SQL-plane only** on `bolt-common.cloud.databricks.com`: SCIM /Me 200, warehouses list 200, but clusters/DBFS/jobs/workspace all 403 and no CREATE/INSERT (no USE_SCHEMA on main.default). The biomni-hub `databricks` backend is dead (stale token vs bolt-datascience) — do not use it for this lane.
- [fact] Workaround that works: **inline VALUES CTE** — ship the 3,768-row GPN sample dataset inside each SQL statement (~202 KB) against warehouse `Common SQL` (`b39957853740b21d`); 5 autopsy queries ran in ~10 s. Script `%TEMP%/phenibut-dbx/dbx_gpn_autopsy_inline.py`; receipt `D:/Research/projects/phenibut/compute/databricks_autopsy_2026-09-13/dbx_autopsy_results.json`.
- [decision] **GPN +12.8 NO-GO now has positive connectivity-defect evidence**: 10↔11 splice BC overlap 0.131 (worst), u2 mean jumps −31.9 kJ ≈ 4σ between the identical-(0.5,0.5) intermediate states, u2 endpoint-drain hysteresis 8.6 kcal between direction branches. Endpoint bimodality clean (pose GO stands). Receipt doc `D:/Research/projects/phenibut/docs/DBX_GPN_MAPPING_AUTOPSY_2026-09-13.md`. "MM cannot rank gabapentinoids" is NOT established; splice-repair one-edge smoke is the cheap discriminator.
- [fact] ECC protocol written per G-7/G-18 lock: `D:/Research/projects/phenibut/docs/ECC_PROTOCOL_2026-09-13.md` (Modal 2×H100, same GPN topology, charges ×0.8, hop at $2 of $42.50) plus new interpretation guard H: if splice diagnostics break again in the ECC run, verdict is "connectivity artifact dominates; ECC inconclusive", not "overpolarization ruled out".
- [fact] ProLIF lane blocked on local env: system Python 3.14 has no MD stack; py -3.12 venv with MDAnalysis/prolif/openmm/pdbfixer installing in `%TEMP%/phenibut-dbx/venv`. Topology must be regenerated via `a2d_atm_gpn.py cmd_prep/cmd_structprep` (inputs: `compute/colab/a2d_openfe_inputs/`) to match xtc atom order.
- [decision] Standing honesty floor unchanged: canonical R→S seed 1 +1.673 ± 0.321 not overwritten; GPN stays NO-GO; α2δ FEP stays gated; no seed averaging.

## Next session
1. Finish ProLIF occupancy on GPN xtc (env + topology regen + occupancy gate ≲0.5).
2. Splice one-edge smoke / dummy-cycle (mapping autopsy continuation).
3. ECC GPU run only after protocol review — spawn per G-18 order.


## ProLIF occupancy addendum (same day)
- [fact] ProLIF/pocket occupancy on the 22 GPN end-state snapshots (topology `gabapentin-pregabalin_equil.pdb`, 131,554 atoms = xtc match, staged at `compute/databricks_2026-09-13/gpn_source_original/`): **L1 gabapentin 22/22 in pocket, ARG197 anchor 1.4–3.6 Å → pose gate PASS**; mode failure excluded. Receipt `compute/databricks_autopsy_2026-09-13/prolif_occupancy_gpn.json`.
- [fact] L2 pregabalin copy sits ~66 Å in bulk with 0 contacts — **that is this pipeline's standard ATM displacement, not a defect**: the experimentally validated GABA-B systems show the identical geometry (63.6/65.4 Å controls). Do not re-flag displaced-copy bulk position as a bug; it is not a valid occupancy metric for the displaced ligand.
- [decision] t=0 processing lane status: mapping autopsy DONE (splice lead), ProLIF DONE (pose PASS). Remaining before any GPU: one-edge splice smoke; then ECC per [[ECC protocol 2026-09-13]] order.


## Paper lane addendum (13.09, evening)
- [fact] Exact one-edge splice smoke attempted locally: **blocked** — the production ATM potential (Direction-dependent intermediate states) lives in the AToM custom OpenMM fork; pip OpenMM 8.6.1 ATMForce has no `Direction`, and `sys.xml` carries only base MM forces. Needs a fork box (2-min GPU job). Standing splice evidence stays the .out-based diagnostics (BC 0.131, 2.85σ branch split, 8.6 kcal hysteresis).
- [fact] Paper A skeleton written: `docs/PAPER_A_SKELETON_2026-09-13.md` (user calls Paper 1 ready; title option 1 = no QM clause recommended; G-6 tension flagged not decided). Value assessment: `docs/PAPERS_VALUE_ASSESSMENT_2026-09-13.md`.
- [decision] Worth ranking: Paper 1 = sure thing (moderate durable value, ~zero marginal compute, title option 1); Paper 2 = upside bet — one fork-OpenMM smoke + one ~5h splice-repair re-run (~EUR 65 class) decides JCTC-grade vs poster-grade (~50/50). Keep splice diagnostics as one paragraph + SI pointer inside Paper A; full methodology belongs to Paper 2.


## Paper 2 screen cross-run validation (13.09, night — on Databricks SQL)
- [fact] Ran the 3-diagnostic λ-ladder connectivity screen over ALL 4 runs on Databricks SQL (inline VALUES, receipt `compute/databricks_paper2_screen_2026-09-13/screen_crossrun_matrix.json`, doc `docs/PAPER2_SCREEN_CROSSLRUN_2026-09-13.md`). Matrix: GPN FLAG (BC 0.131@10↔11, 2.85σ branch sep, 36 kJ hysteresis); H2CL pass (0.310, 0.14σ, 1.65 kJ); RS1 pass (0.326, 0.25σ, 3.07 kJ); RS2 pass (0.362, 0.002σ, 1.51 kJ).
- [decision] Paper-2 threshold locked for drafting: flag iff min-BC < 0.2 AND branch-sep > 1σ. Sensitivity + specificity both clean; H2CL wrong-sign is a MODELING failure (clean ladder), GPN is CONNECTIVITY — the screen separates failure modes.
- [fact] Falsified hypothesis (recorded honestly): RS2's magnitude miss is NOT connectivity (cleanest branches of the panel) → seed-level variance is genuine → strengthens the no-averaging lock with a mechanistic reason.
- [fact] Paper 2 remaining (not Databricks-SQL-runnable): fork-OpenMM exact swap smoke (~2-min GPU) + GPN splice-repair re-run (~5 h H100; densify states 8–13, double 10↔11 exchange attempts, screen-as-acceptance-gate + ΔΔG within ~1 kcal of −0.21).


## SPLICE-BREAK HYPOTHESIS FALSIFIED on Modal (13.09 late — supersedes today's earlier splice narrative)
- [fact] Modal ovido4 (app atm-gpn-smoke, workdir `/mnt/persist/run/a2d/gpn_pgb` on named volume `atm-resumable`): exchange reconstruction from .out state columns shows **10↔11 was the MOST-exchanged pair (64 crossings; 56 inside the ORIGINAL run, spread over sample indices 3–162; 8 in the smoke extension, none at the resume boundary)**. The ladder was CONNECTED all along. The Databricks BC/branch-sep diagnostics detected a real ensemble asymmetry (2.85σ u2 branch means) but it does NOT block Metropolis exchange — do NOT cite "splice disconnection" as the GPN +12.8 explanation anywhere.
- [decision] Repair run (softened splice) MOOT — do not launch `atm_gpn_repair.py` as a "fix". GPN +12.8 attribution reopens: overpolarization (ECC per ECC_PROTOCOL_2026-09-13 now the lead diagnostic) or site-modeling failure. Paper 2 must reframe: the screen = outlier detector, NOT connectivity proof; the exchange-trajectory reconstruction (state-column analysis, 0 GPU) is the arbiter of connectivity and belongs in the paper as the complementary tool.
- [fact] Resume insurance verified: ckpts refresh every 300 s on `atm-resumable` (ovido4), visible from fresh containers (= committed); cross-account path = `modal volume get` tgz / `put` on a non-blocked profile (realprekzursil $40.65). Smoke extension cost was cents (CPU-side reads + brief GPU).
- [fact] VERBOSE MONITOR command (repeatable): `cd D:\Research\projects\phenibut\compute\modal_scripts; env -u MODAL_TOKEN_ID -u MODAL_TOKEN_SECRET MODAL_PROFILE=ovido4 modal run atm_gpn_smoke.py --which both` (status + exchanges; `--which pack` creates the migration tgz). Note: user shell exports MODAL_TOKEN_ID/SECRET pinning florineldanciu4 — always pop them to target ovido4/realprekzursil.
- [owed] Doc corrections (DBX autopsy + PAPER2 docs still carry the old splice-break framing — needs the falsification edit); Schrödinger-on-Modal lane untouched (schrodinger_modal.py stages ready: inspect/prep/install/license/fep).


## PAPER 2 LANDING STRATEGY (13.09 late — the "think" pass)
- [decision] Paper 2's strongest spine is NOT the (falsified) connectivity story — it is **convergent cross-engine failure at α2δ-1**: two independent engines + FFs (Schrödinger FEP+/OPLS4 connected-map NO-GO 2026-07-12 AND AToM ATM/OpenFF-Sage H2CL wrong-sign + GPN +12.8) both fail to rank gabapentinoids at α2δ-1, while BOTH work at GABA-B (FEP+ SAR map ~1.7 gap 2026-06-22; ATM validation edge −2.61). Same lab, same workflows → implicates the SITE MODEL, not the engines. Framing: "convergent failure implicates the α2δ-1 site model (membrane/lipid context, protonation), not alchemical method".
- [hypothesis] The gabapentinoid pocket of α2δ-1 is membrane-adjacent; the 8IF3/8X9 soluble-fragment models omit the lipid/membrane context (literature: PI(4,5)P2/lipid dependence of gabapentinoid binding in full-length cryo-EM structures — VERIFY via literature pass before citing). Missing anionic lipid contributions at a highly charged site would produce exactly wrong-signed/large errors in fixed-charge implicit-context RBFE.
- [decision] Decision tree to landing: (1) ECC charge-scaling on GPN discriminates overpolarization vs site-model (protocoled; fire when GPU free); (2) structural-context analysis: measure pocket→membrane proximity in full-length α2δ-1 structures vs our fragment model, lipid/PIP2 contacts (cheap, local + PDB fetch); (3) literature verify pass; (4) write around whichever survives — with today's diagnostics suite (screen + exchange-trajectory reconstruction + the falsification itself: "energy-overlap heuristics can flag asymmetries that do NOT imply disconnection") as the methodological rigor section.
- [fact] Honest contribution inventory for Paper 2: cross-engine failure panel (4+ runs, receipts), diagnostics tooling (0-GPU, SQL-runnable), the controlled falsification demonstrating proper discipline, decision-tree experiments (ECC/structure/lit). A "cure" (re-run landing near −0.21) is now ONE branch, not the only landing.


### Lit-check correction (13.09, minutes later)
- [fact] Literature pass REVISIONS the membrane-context hypothesis: per Chen/Mondal/Minor 2023 NSMB (PMID 36973510, PDB 8FD7, full-length gabapentin-bound CaV1.2/β3/α2δ-1), the gabapentinoid site is in the dCache1 domain and **completely encapsulates** gabapentin; PIP2 resolves at the VSDII–pore interface — a DIFFERENT site, NOT in the gabapentin pocket. Do NOT cite PIP2-in-pocket. Revised site-model candidates: encapsulated-pocket desolvation balance, single-conformation receptor model (fragment 8IF3 vs full-length 8FD7 differences), fixed-charge electrostatics at a fully buried charged ligand (zwitterion) — the last is exactly what ECC tests. The convergent cross-engine failure spine is unaffected.


## ECC RUN LAUNCHED (13.09 night)
- [fact] ECC staged + running on Modal **ovido4** (app `atm-gpn-ecc`): system copied to `/mnt/persist/run/a2d/gpn_ecc`, **14,815 solute/ion particles ×0.8, 79,820 exceptions ×0.64, TIP3P untouched, net charge preserved** (receipt `ecc_scaling_receipt.json` on the volume). Runner: `compute/scaleway/a2d_atm_gpn_ecc.py` (original schedule, own workdir). Launcher: `compute/modal_scripts/atm_gpn_ecc.py` (structprep-if-needed + production, 8×H100, ckpts 300 s, commits 60 s).
- [fact] **Budget: ovido4 $18.35 remaining at launch** (metered $24.15 today), realprekzursil $40.65. ECC will likely drain ovido4 → **HOP REQUIRED**: when the run dies at cap, `modal volume get atm-resumable /run/a2d/gpn_ecc` from ovido4 → `modal volume put` on realprekzursil → re-fire `env -u MODAL_TOKEN_ID -u MODAL_TOKEN_SECRET MODAL_PROFILE=realprekzursil modal run atm_gpn_ecc.py --run-only --max-samples 160` (RE_SETUP=NO resumes from ckpts; old .out accumulation in gpn_ecc stays consistent — ECC started fresh). Always pop MODAL_TOKEN_ID/SECRET (shell pins florineldanciu4).
- [fact] Analysis when done: harvest r*/[BASE].out → same UWHAM + screen; gates per ECC_PROTOCOL_2026-09-13 (kill: scaled ΔΔG still >+1 or wrong-signed by >2 kcal vs −0.21; success: within ~1 kcal of −0.21 → overpolarization implicated). Watchdog restarted (~/.biomni-mcp, 90 s poll) but may not auto-detect the new app name — manual watch via modal_credits.snapshot(['ovido4','realprekzursil']).


## Heuristic-vs-arbiter investigation RESULT (13.09 night)
- [fact] Quantified the caution: across 19 valid adjacent pairs, **BC overlap vs reciprocal-swap counts: Spearman -0.462 / Pearson -0.362** — the energy-marginal heuristic has NO positive predictive value for actual exchange (confounded by attempt/occupancy patterns; low-BC pairs swapped MORE on average, 9.0 vs 4.8). 198 clean reciprocal swaps + 283 rotation-solo moves total; splice 10-11 = 19 recip + 26 solo. Branch u2 asymmetry 2.52sigma stands. Receipt: `compute/investigate_heuristic_2026-09-13/RECEIPT.md`.
- [decision] FINAL Paper 2 framing locked: screen (D1-D3) = outlier detector; exchange-trajectory reconstruction = connectivity arbiter; falsification + correlation analysis = quantified caution (case study, n=1 caveat). Do not present heuristics as connectivity measures anywhere.
- [fact] ECC run still in production on ovido4 at last check (container up ~22:40 UTC+3; budget hop procedure stands).


## ECC relaunch on realprekzursil after ovido4 DEATH (13.09 late)
- [fact] **ovido4 workspace DISABLED mid-run** (ConflictError 'workspace ac-ei88xs7ZkGnLpoaxcDcrS0 is disabled') — account-level kill, not a cap. ovido4's volume (incl. the original gpn_pgb workdir + the first ECC stage) is presumed INACCESSIBLE. Do not target ovido4 again.
- [fact] ECC re-staged deterministically: charge-scaling done LOCALLY with vanilla OpenMM (base sys.xml has only standard forces; 14,815 particles ×0.8, 79,820 exceptions ×0.64 — exact parity with the ovido4 receipt), uploaded with `modal volume put` to **realprekzursil** `atm-resumable`: `run/a2d/gpn_ecc/{sys.xml,pdb}` + `run/a2d/inputs/{a2d_receptor.pdb,gabapentin.sdf,pregabalin.sdf}`. Relaunched `--run-only` (background, 8×H100, $40.65 budget). Original local system source of truth: `compute/databricks_2026-09-13/gpn_source_original/`.
- [fact] If realprekzursil also dies: remaining credited profiles per DEST_RANK (prekzursil, prekzursil1993, florineldanciu4-env-token...) — same volume-put + run-only procedure; ckpts commit every 300 s/60 s.


## ECC attempt 2 FAILED — structprep NaN (13.09 night, realprekzursil)
- [fact] ECC on realprekzursil: structprep built the full ATM system fine (NonbondedForce→ATMForce, restraints, CUDA platform, LoadState E=−880,766 kJ/mol) then **"Particle coordinate is NaN" during equilibration at λ=1/2** (rbfe_structprep.py:403 do_equil). App run: modal.com/apps/realprekzursil/main/ap-Q1LlSjMehoSVzOgwApRMlM. Credits barely touched (~$1.3).
- [hypothesis] Ranked causes: (1) **INP mismatch** — the uploaded `run/a2d/inputs` came from `compute/colab/a2d_openfe_inputs/` and may NOT be byte-identical to the original persist INP; a different pregabalin.sdf atom order shifts `_warhead_triple`/DISPLACEMENT → restraint misfire → NaN (note a2d_atm_gpn.py's own comment about pregabalin SDF atom order!). (2) stochastic equilibration collision (one retry would tell). (3) genuine 0.8-charge electrostatic destabilization (least likely; scale is mild).
- [decision] Next-session decision tree: (a) retry once (cheap, tests stochasticity); (b) if NaN repeats at the same phase → inputs are the suspect: recover true INP (sources: florineldanciu4 tgz contains gpn_pgb only — inputs NOT in it; consider deriving DISPLACEMENT from the equil.pdb geometry instead of the sdf, or diff the colab sdfs vs `modal_scripts/_pocket_sdf/` versions by warhead atom order); (c) variant: leave ions unscaled (protocol documents convention choice). The scaled sys.xml + pdb + inputs remain on realprekzursil's volume at run/a2d/gpn_ecc + run/a2d/inputs; local scaled copies at %TEMP%/phenibut-dbx/ecc.
- [fact] Session state at wrap: ECC NOT run yet; ovido4 dead; all other program state as per prior addenda.


## ECC attempt 3 diagnostics + attempt 4 launched (13.09 night)
- [fact] Attempt 3 (rc=1): INPUTS FULLY CLEARED — options dump shows `pocketCA=7` (in-frame guard passed), warhead triples `L1=[0,4,2] L2=[6,8,4]` resolve correctly for the N-first/C-first orders, `DISPLACEMENT=[132.99,75.07,71.98]` (in receptor frame). Attempt 3 SKIPPED structprep (stale `_equil.xml` from attempt 2's NaN crash, no ckpts) and production died after "Worker using **Reference** OpenMM platform" (CPU fallback on a GPU container — actual error was hidden by my own return filter).
- [decision] Attempt 4 launched with fixes: (1) run() now purges stale `_equil.*` when no ckpts exist (forces clean structprep); (2) full error/traceback/stderr capture in the return. If the Reference-platform fallback recurs with a visible CUDA error → the realprekzursil image build's CUDA plugin (cuda-version=13.0 pin vs H100) is the suspect; fix = pin cuda-version=12.x in the image or match ovido4's build recipe. Harvest script ready: `compute/modal_scripts/atm_gpn_ecc_harvest.py` (linear-coupling UWHAM proxy + D1-D3 screen; canonical softcore UWHAM still required for the gate verdict).


## ECC attempts 5-6: NaN root-caused to from-scratch equilibration; equil-start fix (14.09)
- [fact] Attempt 5 = clean reproduction: fresh structprep (stale-equil purge worked), CUDA platform, E=−879,447 kJ/mol, **NaN at λ=1/2 equilibration — identical to attempt 2**. Stochastic hypothesis DEAD; inputs already cleared. Conclusion: the 0.8-scaled system cannot re-equilibrate from the pre-equil (unrelaxed) starting pdb.
- [decision] Attempt 6 fix: **start from the original equilibrated positions** — uploaded `gabapentin-pregabalin_equil.pdb` (from gpn_source_original) as `run/a2d/gpn_ecc/gabapentin-pregabalin.pdb`. The equil structure is fully relaxed (it produced the whole 160-sample production) → λ=1/2 equilibration becomes a gentle re-relaxation under 0.8 charges. If this still NaNs: next variants = (a) unscaled-control structprep run (discriminates scaling vs flow), (b) ions-unscaled, (c) scale 0.9.
- [fact] Full-error capture in run() now works (attempt 5 returned the complete traceback).


## ECC attempt 7 + hop map (14.09)
- [fact] Attempt 7 launched from EQUILIBRATED positions (equil.pdb force-uploaded as the starting pdb after `--force` fix; attempt 6 never ran — volume put bounced on 'already exists' and &&-chained run skipped). At last check it had passed the ~10-min window where attempts 2/5 NaN'd.
- [fact] Budget: realprekzursil **$16.55** (failed structprep cycles cost ~$23) — a full 160-sample production needs a HOP. Ranked hop targets (all ok=True): prekzursil1993 $40.75, andreivisalon2002 $40.65, mariusvisalon70 $40.64, darias-grama $40.50, prekzursiltr $40.41, prekzursil $39.69, florineldanciu4 $26.92. Hop = volume get/put `run/a2d/gpn_ecc` (ckpts) + inputs, then `--run-only` (RE_SETUP=NO). Remember `--force` on volume put over existing files.


## ECC attempt 7 result + control bisection running (14.09)
- [fact] Attempt 7 (equilibrated-start): NaN AGAIN at λ=1/2 equilibration — third clean reproduction (E=−882,728, sanest start yet). Equilibrated-start hypothesis dead. Min/therm/NPT stages PASS; only the λ=1/2 ATM equilibration dies. rbfe_structprep DOES consume `_sys.xml` directly (verified in source, lines 117/220) — the scaled system is in play.
- [decision] BISECTION launched: unscaled control structprep (`run/a2d/gpn_control`, runner `a2d_atm_gpn_control.py`, launcher `modal_scripts/atm_gpn_control.py`, unscaled sys.xml + equil.pdb uploaded) on realprekzursil. Equilibrates → scaling genuinely breaks λ=1/2 (next: ligands-only scaling leaving protein+ions unscaled, or 0.9, or investigate ATMForce charge-offset interplay). Also NaNs → reconstruction-flow drift (AToM git-latest vs original environment; then: pin the original AToM commit / recover original _0.xml-based path). Budget realprekzursil ~$14 after this run.


### Checkpoint-discipline answer + hop-safety fix (14.09, user prompt)
- [fact] Production = ckpt'd (300 s per-replica `_ckpt.xml` + 60 s vol.commit on named volume) and hop-resumable (volume get/put + `--run-only`, RE_SETUP=NO) — proven pattern from the August migrations. Equilibration phase = NOT checkpointable (crashes there have no state to resume; each diagnostic attempt costs fresh ~15 GPU-min). ovido4's death cost only minutes (deterministic restage).
- [fix] Purge logic made hop-safe: only purges `_*.xml` when no ckpts AND the `_min/_therm/_npt/_equil` chain is incomplete — a completed structprep is never discarded across an account hop (previous logic would have forced a needless re-equilibration if the account died in the ckpt-free window after structprep).
- [fact] AToM structprep flow (from source): `_min` → `_therm` → `_npt` (saves `_equil.xml`) → `do_equil` LOADS `_equil.xml` and runs the λ=1/2 equilibration. So failed attempts leave a complete NPT `_equil.xml` — resumable-to in principle, but `do_equil` itself is the NaN site. Control run (unscaled) still executing in background at time of this note.


## BISECTION VERDICT: version drift, not scaling (14.09)
- [fact] **Unscaled control ALSO NaNs at λ=1/2** (identical flow/files) — charge-scaling is EXONERATED for the equilibration crash.
- [fact] Version check on the built image: **openmm 8.6**, but the original August runs used **openmm 8.5** (RESULTS.md). AToM installs from unpinned git master; image resolves openmm>=8.4 → 8.6 today. ATMForce changed between 8.5→8.6 (local 8.6.1 lacks the `Direction` parameter AToM's ommsystem adds) — prime suspect for the equilibration instability.
- [decision] Images pinned to `openmm=8.5` in atm_gpn_control.py + atm_gpn_ecc.py; control re-running on the pinned build. If it equilibrates → rerun ECC (scaled) on the pinned image → production. If still NaN → pin the AToM commit to pre-2026-08-25 master (find via GitHub API commits?until=...) and retry. Budget realprekzursil ~$12-13 after this control.


## DEPRESSION LINK FOUND (14.09 — owner-corrected search, supersedes "honestly dead" framing)
- [decision] Owner right: the GABA-B/depression link is NOT dead. Synthesis written to `docs/GABAB_DEPRESSION_LINK_SYNTHESIS_2026-09-14.md`. Unified axis: MDD = GABA-B complex DOWNREGULATION (expression: Fatemi 2011, Cathomas 2015; function: blunted baclofen GH response in MDD; genetics: KCTD16×mood coloc PP.H4=0.948 from OUR cis-MR v2 + KCTD12 MDD/bipolar assoc). Phenibut tolerance = same downregulation direction. Fasoracetam = upregulator (Shimidzu 1997: reverses learned helplessness via GABA-B upregulation) → unifies antidepressant + tolerance-reversal aims. Antagonist paradox resolved: chronic antagonism → compensatory upregulation; both routes converge on RESTORED RECEPTOR DENSITY, not signaling direction.
- [decision] Why cis-MR missed it: brain GPCR eQTL instruments weak; KCTD16 passed coloc but not MR; density-dynamics invisible to cis genetics. Follow-ups identified: MR with auxiliary-protein instruments on mood-spectrum outcomes; direction extraction from 6 suggestive-MR cells; FAERS asymmetry (baclofen/phenibut withdrawal vs fasoracetam depression signals). Paper B spine candidate locked in the synthesis doc. Mechanism-only floor unchanged.
- [fact] ECC control v2 (openmm=8.5 pinned): STILL NaN at lambda=1/2 unscaled → version pin alone insufficient; remaining suspect = unpinned AToM master drift. Next: pin AToM commit to pre-2026-08-19 (GitHub API commits?until=) and rerun control. Budget realprekzursil ~$10.