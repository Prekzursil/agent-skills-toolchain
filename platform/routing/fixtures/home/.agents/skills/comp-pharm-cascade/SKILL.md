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

### Canonical phase pipeline
### Substrate & ops (hard-won)
### Worked reference — phenibut (2026-07-04)
