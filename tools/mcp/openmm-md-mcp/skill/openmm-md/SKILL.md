---
name: openmm-md
description: Run FREE, open-source, Windows-native GPU molecular dynamics via the openmm-md MCP (OpenMM + CUDA on the local NVIDIA GPU). Use for protein / protein-ligand MD when you want a free stack or are on Windows without a Schrodinger license. Covers the full workflow (prepare, solvate, minimize, equilibrate, production, analyze, mmgbsa) AND an honest decision guide vs Schrodinger Desmond, including how to run Desmond legitimately on Linux or a cloud GPU with a real license. This is a deliberately LESSER free alternative and does NOT replace the schrodinger MCP tools. Do NOT use it to pick a free tool when a validated FEP+, WaterMap, IFD-MD, or Prime MM-GBSA result is actually required.
---

# OpenMM MD (free, Windows-native GPU molecular dynamics)

`openmm-md` is a FREE / open-source (MIT) molecular-dynamics MCP that runs **natively on
Windows with CUDA** on the local NVIDIA GPU (verified on an RTX 4050). It is the free lane
for MD work; it is **explicitly a lesser alternative** to Schrodinger Desmond, which stays
the preferred engine whenever a legitimate license is available.

## When to use which engine (decision guide)

| Situation | Use | Why |
|---|---|---|
| On Windows, no Schrodinger license, need MD now | **openmm-md (this)** | Only native-Windows GPU MD option; free; runs on the local RTX 4050 |
| Quick stability / RMSD / Rg / H-bond check of a pose | **openmm-md** | Fast, free, good enough for triage |
| Ranking a congeneric ligand series roughly, no budget | **openmm-md** `openmm_mmgbsa` | Free relative ranking (approximate) |
| You need validated **FEP+**, **WaterMap**, **IFD-MD**, **Prime MM-GBSA (VSGB2.1)** | **Schrodinger** (`mcp__schrodinger__*`) | OpenMM has no validated equivalent |
| Publication-grade / regulatory binding free energies | **Desmond / FEP+** on a licensed host | More-validated force fields + workflows |
| You have a **legit** Schrodinger license + a Linux box | **Desmond on Linux** | The `mcp__schrodinger__desmond_*` tools work there |
| You want a big GPU / no local install | **Desmond on a licensed Linux cloud GPU** | Scale out with a real license |

**Golden rule:** if the science needs a validated commercial method, use Schrodinger. Use
openmm-md when free + Windows-native + "good enough" is the right trade. openmm-md does NOT
replace the 35 `mcp__schrodinger__*` tools; they stay intact and preferred.

## Honest OpenMM vs Desmond trade-offs

OpenMM (free) is a genuinely excellent MD **engine**, but as a **workflow** it is a lesser
alternative to Desmond/Maestro:

- **Force fields**: OpenMM here uses AMBER **ff14SB** (protein) + **OpenFF Sage** or GAFF
  (ligand). Desmond ships OPLS4, extensively validated for drug discovery.
- **Ligand charges (Windows caveat)**: AmberTools has **no native-Windows build**, so there
  is **no antechamber / sqm AM1-BCC** and **no GAFF** here. Charges come from **NAGL** (a
  GNN AM1-BCC surrogate, if installed) or **RDKit Gasteiger** (lower fidelity). Both are
  clearly labelled. OpenEye/sqm AM1-BCC quality is not reproduced.
- **Free-energy / analysis**: no FEP+, no WaterMap, no IFD-MD. `openmm_mmgbsa` is an HONEST
  OBC2/GBSA single-trajectory approximation (no entropy, generic radii) -- good for ranking,
  NOT absolute affinities, and materially weaker than Prime MM-GBSA.
- **Polish**: no Maestro GUI, trajectory clustering, or event analysis suite. You get MDTraj
  metrics (RMSD/RMSF/Rg/H-bonds/contacts).

## Running Desmond legitimately (the better option when licensed)

This project will **not** install, crack, or facilitate a pirated Schrodinger suite. To use
Desmond properly:

1. **Get a legitimate license.** Academic/non-commercial Desmond is **free from D. E. Shaw
   Research** (deshawresearch.com) for non-commercial use; commercial use needs a Schrodinger
   license. Academic Maestro/Schrodinger licenses are available to universities.
2. **Desmond on Linux.** Desmond's MD engine is Linux-only. Install the licensed suite on a
   Linux workstation, set `$SCHRODINGER`, and the existing `mcp__schrodinger__desmond_setup`
   / `desmond_md` / `desmond_trajectory_analysis` tools drive it there.
3. **Desmond on a cloud GPU.** Put a legit-licensed Linux install on a cloud GPU instance
   (e.g. via the cloud-hub RunPod / Modal / Lightning GPU tools), copy the license, and run
   Desmond remotely. Shape only -- provision the box, install YOUR licensed suite, run.

## The openmm-md workflow

Tools chain through a `job_dir` on disk. Typical protein-ligand run:

1. **`openmm_status`** -- verify CUDA is live on the GPU (run this first).
2. **`openmm_prepare`** -- `protein` = PDB path or 4-char RCSB id; optional `ligand_file`
   (a **docked** SDF/MOL2 pose -- preferred) or `ligand_smiles` (arbitrary conformer).
   PDBFixer cleanup + ff14SB + OpenFF ligand params. Returns the `job_dir`.
3. **`openmm_solvate`** -- TIP3P box (`box_shape` cube|dodecahedron|octahedron) + neutralizing
   ions (PME). `hydrogen_mass_amu=4.0` for HMR / 4 fs.
4. **`openmm_minimize`** -- energy minimization on CUDA.
5. **`openmm_equilibrate`** -- NVT then NPT (barostat), optional heavy-atom restraints.
6. **`openmm_production`** -- production MD. **Non-blocking**: returns a handle; poll with
   `openmm_production(job_dir, poll=True)` or Read `prod_status.json`. Writes `prod.dcd`.
   Use `blocking=True` only for short runs.
7. **`openmm_analyze`** -- MDTraj RMSD / RMSF / Rg / H-bonds / protein-ligand contacts +
   ligand binding-site RMSD (stability).
8. **`openmm_mmgbsa`** -- approximate free binding dG (ranking only; read `fidelity_note`).

### Sensible defaults / tips

- **GPU memory (6 GB RTX 4050)**: keep systems modest (small-to-medium proteins, ~1.0 nm
  padding). Large systems may OOM -- reduce padding or trim the system.
- **Timestep**: 2 fs default (HBond constraints). 4 fs only with HMR (`hydrogen_mass_amu=4.0`).
- **Ligand pose**: for binding studies pass a **docked** pose via `ligand_file` (e.g. from
  Glide `mcp__schrodinger__glide_dock`); a bare SMILES has no bound pose.
- **Long runs**: leave production non-blocking and poll; the detached worker keeps writing
  `prod.dcd` + `prod_status.json` even across MCP calls.
- **Honesty**: label OpenMM results as free-stack / approximate; when a decision hinges on
  absolute affinity or validated methods, escalate to Schrodinger.

## Registration

MCP server: `C:\Users\Prekzursil\source\repos\openmm-md-mcp\server.py`, run with the conda
env Python `D:\micromamba\envs\openmm-md\python.exe` (the server self-configures the Windows
CUDA DLL path, so no activation wrapper is needed). See the repo README for the exact
`~/.mcp.json` block and how to install this skill into a skills directory.
