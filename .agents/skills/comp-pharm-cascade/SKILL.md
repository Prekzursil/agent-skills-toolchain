---
name: comp-pharm-cascade
description: >-
  Use when ranking/prioritizing a congeneric small-molecule series against a
  protein target (binding-affinity SAR, hit triage, mechanism-of-action), or
  when scoping such a campaign. Routes the work through a cost-escalating
  cascade — experimental-anchor data → license-free ML (Boltz-2) breadth +
  pose → licensed Schrödinger physics (FEP/MM-GBSA/BPMD) for the headline
  ΔΔG → QM (EXESS) mechanism → figures — with consensus checks at the two
  gates that are catastrophic when silently wrong (pose, and the published
  number). NOT for a single one-off docking (use schrodinger-maestro-driver /
  structure-based-screening) or pure knowledge lookup (use tooluniverse).
---

# comp-pharm-cascade

Orchestration skill: how a target + ligand series flows through the available
compute stack to a defensible affinity/mechanism result. This is a **routing
law over executor skills**, not a new engine. Reference implementation: the
phenibut α2δ-1 / GABA_B campaign (worked numbers at the bottom).

## Core principle — a cascade with two guarded gates

Escalate cost only when the cheaper tier can't answer. But a naive cascade is
**brittle where campaigns actually break**: it trusts each tier and escalates
upward, so a wrong pose makes MM-GBSA, FEP, and QM all rank garbage *equally*.
So spend redundancy surgically at the **two checkpoints where being wrong is
catastrophic and silent**, single-track everywhere else.

- **Gate 1 — Pose.** A pose is trusted only when independent methods agree
  (Boltz-2 co-fold ipTM/PAE ∩ Glide/IFD ∩ BPMD stability). Cheap ensemble at
  the known failure point. Never rescore an unvalidated pose.
- **Gate 2 — The published number.** The one headline ΔΔG gets FEP **plus** one
  orthogonal corroborator (Boltz affinity *or* QM decomposition) **plus** the
  experimental value. Everything else in the SAR runs single-method, flagged
  lower-confidence.

## Tier map (cheap → expensive)

| Tier | Capability | Executor | Note |
|------|-----------|----------|------|
| **0 — Anchor** ⭐ | Experimental Ki/IC50/EC50, the y-axis | ChEMBL MCP / GtoPdb / `tooluniverse` pharmacology | **Run FIRST.** No ground truth → no rankable claim (see Gate 0). |
| **1 — Cheminfo** | descriptors, pKa/protonation, filters | `cheminformatics-rdkit`, Inductive Bio, Epik/`jaguar_pka` | Zwitterion state decides GB desolvation — get it right. |
| **2 — ML structure+affinity** | co-fold + affinity, license-free | Boltz-2 MCP (`boltz_*`) / `qdx-rush` `boltz_fold` | Breadth ranking + pose gate. Minutes, no license. |
| **3 — Physics endpoint** | MM-GBSA, BPMD pose-stability | `schrodinger-maestro-driver` (`prime_mmgbsa`, `thermal_mmgbsa`), `mcp__schrodinger__*` | Fast, but endpoint scoring often fails on flexible/charged ligands. |
| **4 — Physics free-energy** | alchemical FEP+, MD, WaterMap | `mcp__schrodinger__fep_plus/desmond_md/watermap` | Gold standard for the headline. Cloud GPU. |
| **5 — QM** | interaction-energy / QM-MM mechanism | `qdx-rush` (`exess_interaction_energy`, `exess_qmmm`) | Captures salt-bridge/polarization MM underestimates. |
| **6 — Deliverables** | figures, methods, unit/error math | BioRender, Mermaid, protocols.io, `pymol_render`, Wolfram | Automate the write-up. |

## Canonical phase pipeline

- **Gate 0 — Verify the anchor (do this before any compute).** Pull the full
  experimental affinity ladder (ChEMBL target ID → all Ki/IC50/Kd with
  `pchembl_value`; dedup to one row/compound by max pChEMBL). **Measure its
  dynamic range.** If the congeners span <~2 log or the subjects are unmeasured,
  the *maximum achievable* rank correlation is ~0 — reframe the claim
  (binding-mode/mechanism) instead of burning compute on an unwinnable metric.
  This gate is cheap and repeatedly pays for itself.
- **Phase 1 — Pose (Gate 1).** Boltz-2 co-fold target+ligands (prefer a holo
  template when a co-crystal exists; else sequence-only with the known anchor
  residue as pocket condition / reference ligand). Confirm the conserved
  anchor contact. Keep only poses where Boltz ∩ BPMD agree.
- **Phase 2 — ML breadth rank.** Boltz-2 affinity over the whole ladder →
  Spearman(score, experimental pChEMBL). Method is validated for the series
  iff the correlation holds on the real dynamic range.
- **Phase 3 — Physics headline (Gate 2).** FEP+ on 3–5 ladder-spanning edges +
  the subject edge; QM decomposition of the key contact; require
  FEP ∩ Boltz ∩ QM agreement before publishing the number.
- **Phase 4 — Predict.** Apply the validated method to any unmeasured subject;
  label it a computational hypothesis, not an experimental value.
- **Phase 5 — Deliverables.** Mechanism panel, pipeline DAG, methods, error math.

## Substrate & ops (hard-won)

- **Local vs cloud.** Schrödinger prep/dock/MM-GBSA/QM-setup run locally if a
  Windows license is valid; FEP/Desmond MD need a real GPU (≥16–40 GB) → cloud
  (Lightning/Modal A100) or license-free **AToM-OpenMM**. A laptop GPU
  (e.g. 6 GB) cannot do FEP. Never bypass a license verifier.
- **Boltz-2 free tier.** Orgs hold ~$5, run **~1 job concurrent** (excess
  startup-times-out → `stopped` at 0, $0 cost), OAuth token expires on long
  runs, and **switching orgs orphans in-flight jobs** (workspace-scoped → 404
  from the new org). Some orgs are pathologically slow (progress bursts near the
  end, not incrementally). Pattern: **one small solo job → collect immediately
  (results paginate 100/page via `after_id`) → then move.** Screen caps 500
  mol/call; the default SMARTS filter silently drops ~15–20%. ~$0.025/molecule.
- **Verify the account before a paid call** (`boltz_get_account_context`) and
  **re-estimate cost** (`boltz_estimate_*`) — never assume credits.
- **Honesty gates.** State whether a contrast is matched (same ligands, same
  assay) or qualitative (broad set vs narrow). Distinguish equilibrium score
  from kinetic effects (a co-fold score won't capture off-rate selectivity).
  Log every silent cap (SMARTS-filtered, truncated, unmeasured).

## Worked reference — phenibut (2026-07-04)

- **Gate 0 caught a dead metric:** α2δ-1 (ChEMBL CHEMBL1919) — only gabapentin
  (27 nM) and pregabalin (19 nM) measured, ~0.15 log apart; phenibut/baclofen
  **unmeasured** in ChEMBL. Real ground truth = Zvejniece 2015 (PMID 26234470,
  [³H]gabapentin rat-brain, subtype-unresolved): gabapentin 0.05 µM, R-phenibut
  23 µM, S-phenibut 39 µM, baclofen 156 µM.
- **Tier 2 win:** Boltz-2 co-fold vs α2δ-1 (P54289, pocket Arg241/Asp452/Asp491,
  mirogabalin ref) → **Spearman(binding_confidence, pChEMBL) = +0.48, n=486**
  (stable: +0.54@212 → +0.48@369 → +0.48@486). Recovers the breadth ranking the
  **MM-GBSA/FEP endpoint could not** (≈0 on the narrow β-aryl-GABA set). Core-6:
  potent gaba/prega separate from weak phenibut/baclofen; R-phe > S-phe correct
  (matches 23 < 39 µM) — independent of the ladder join.
- **Tier 4 headline:** GABA_B FEP ΔΔG(baclofen→phenibut) = **+1.74 vs exp +1.62**
  (0.12 kcal/mol); ChEMBL confirms the baclofen 6 µM leg.
- **Honest framing:** the +0.48 (broad) vs MM-GBSA ≈0 (narrow) is a *qualitative*
  contrast, not a matched head-to-head; α2δ endpoint failure is MM-specific, not
  "computation can't rank α2δ."

Full audit trail: `D:/Research/projects/phenibut/docs/COMPUTE_STACK_GRILL.md`.
