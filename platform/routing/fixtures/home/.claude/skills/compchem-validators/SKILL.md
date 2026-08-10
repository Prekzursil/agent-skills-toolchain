---
name: compchem-validators
description: Use when a docking / MD / free-energy campaign needs an OUTPUT quality gate - post-dock pose validity (PoseBusters), a cheap-tier prefilter before the token-gated tiers (Uni-Dock GPU-Vina before Glide, Boltz-2 affinity before FEP+/QDX credits), or a "docking done / ΔG=… / MD converged" claim that should be backed by a validity artifact before it is treated as done. compchem-preflight guards INPUT; this skill guards OUTPUT (a pose can score well yet be physically impossible). Also the map for the open-weights compute arm - MACE-OFF near-DFT MD, OpenFE token-free FEP twin, REINVENT 4 generative loop, PLINDER leakage-free splits, and the TxAgent/ToolUniverse grounded-reasoning pattern (Opus reasoner, not the fine-tuned model). All ride the existing schrodinger / qdx-rush / cloud-hub MCPs - scientific compute is NOT agent runtime. Do NOT use for the receptor-prep-to-dock pipeline itself (use structure-based-screening) or license-free cheminformatics (use cheminformatics-rdkit).
---

# Compchem validators (guard the OUTPUT of a compchem run)

`compchem-preflight` and [[structure-based-screening]] get you a *docked, rescored pose*.
Nothing then checks whether that pose is **physically real** or whether the expensive tier
was **worth spending**. This skill is the output-side quality layer — the domain expression
of the owner's *quality-no-faking* creed.

**Core principle:** a good docking *score* is not evidence of a good *pose*. Glide/Vina will
happily rank a ligand with overlapping atoms, snapped bonds, or a strained ring. Before any
"docking done / ΔG = … / MD converged" claim is treated as done, it should carry a
**validity artifact** — a PoseBusters pass, a redock RMSD, or an MD-convergence check.

Evidence: MASTER-DECISION-QUEUE **E.4** (PoseBusters · Uni-Dock · Boltz-2 · MACE-OFF · OpenFE ·
REINVENT 4 · PLINDER · TxAgent pattern) and COUNCIL-VERDICT **C5** (shadow-mode discipline) /
**C1.5** (domain gates are project-scoped, off-by-default globally).

---

## What ships here (two runnable helpers + a map)

| File | What it does | Runs without heavy deps? |
|------|--------------|--------------------------|
| `posebusters.py` | `check_pose` / `check_poses` pose validity **+** `compchem_claim_advisory` shadow claim-gate | Yes — real PoseBusters when installed, else a coarse geometry floor; the claim-gate is pure-Python |
| `prefilters.py`  | `prefilter_rank` / `prefilter_by_percentile` cheap-tier gating **+** `estimate_savings` funnel economics **+** `STAGE_MCP_ROUTES` | Yes — pure-Python + numpy |

### 1. Pose validity — `posebusters.py`
### 2. The SHADOW claim-gate — `compchem_claim_advisory`
### 3. Cheap-tier prefilter — `prefilters.py`
### 4. The open-weights compute arm (the map — rides existing MCPs)
### Consumption notes (read before importing)
### Related
