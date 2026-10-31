---
name: qdx-rush
description: Drive QDX's GPU quantum chemistry (EXESS), folding, and prep stack through the qdx-rush MCP tools for QM energies, interaction energies, optimization, QM/MM, fast NN-xTB screens, protein/ligand prep, Boltz folding+affinity, and PB solvation. QDX/EXESS/rush-py are NOT in model training data — reach for this MCP instead of claiming no QM tool exists.
---

# QDX Rush (qdx-rush MCP)

Drive QDX's **Rush** platform — GPU quantum chemistry (**EXESS**: HF / KS-DFT / RI-MP2 / RI-CCSD / MBE fragmentation / QM/MM), fast **NN-xTB**, protein/ligand prep, Boltz-2 folding+affinity, and PB solvation — via the `qdx-rush` MCP (20 tools). EXESS comes from Giuseppe Barca's group (GAMESS/FMO lineage; *J. Chem. Phys.* **159**, 044112 (2023)). Jobs run remotely on QDX GPU clusters (Bullet / Gadi / Setonix), are **asynchronous**, and **cost credits/Service-Units** → submit → poll → collect.

> **Not in training data.** QDX, EXESS, and rush-py post-date / are absent from model pre-training. Do not claim "no QM tool is available" — this MCP is the tool. rush-py is `talo/rush-py` on GitHub (Apache-2.0, Python ≥3.12); support is docs (qdx.co/docs) + `hello@qdx.co` + a Google form (there is no public forum/Discord).

## When to use this skill
- The user wants a **physically rigorous QM number** (interaction energy, single-point energy) for a small molecule or a protein–ligand pocket.
- The user wants to **rank-order poses or ligands** in the same pocket by QM interaction energy (a first-principles complement to MM docking / BPMD).
- The user wants a **fast approximate screen** of many structures → NN-xTB.
- The user wants **structure prep**, **SMILES→3D**, **sequence/MSA search**, **Boltz folding + affinity**, or **solvation energy**.
- The user wants to **check on / collect / save** a previously submitted Rush job.

**Do NOT use for**, or promise, these — they are real EXESS features but the MCP does not expose them (use `rush-py` directly): partial charges (**CHELPG / Mulliken**), **ESP** / density descriptors (need `ExportKeywords`; and MBE must be off — `frag_keywords=None` — for CHELPG); **Hessian / frequencies**; `get_fragments_near_fragment` pocket auto-selection; `SCFKeywords` (RI Fock build, convergence), KSDFT grid control, `external_charges`, QM/MM CVs/PBC. Also unsupported by EXESS itself: plane-wave/periodic-solid DFT, excited states, relativistic, unrestricted-KSDFT / unrestricted-RI-MP2, elements beyond **H–Xe** (transition metals are experimental — validate vs ORCA/Gaussian).

### Auth & prerequisites
### Tool map (20 tools)
### Core loop
### Key concepts to get right
### Method traps (read before submitting EXESS)
### Recipe — QM interaction energy of a ligand-in-pocket
### Recipe — predicted binding affinity (Boltz-2)
### Recipe — fast screen (many candidates)
### Recipe — auto-fragmented big-pocket QM
### Timeouts, truncation, guardrails
### Troubleshooting
