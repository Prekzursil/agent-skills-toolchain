---
name: structure-based-screening
description: Use when running a structure-based drug-discovery / molecular-docking campaign on the local schrodinger MCP - taking a receptor (PDB) and one or more ligands (SMILES or files) all the way to docked, MM-GBSA-rescored, ADMET-profiled poses. Covers the full prepwizard to glide_grid to ligprep to glide_dock to prime_mmgbsa to qikprop chain, grid-box centering (explicit coordinates or a co-crystal ligand centroid), license-token sequencing, and the path gotchas.
---

# Structure-based screening (end-to-end Schrodinger pipeline)

Chains the `schrodinger` MCP's tools into the full receptor-prep -> dock -> rescore -> profile
flow. Tool mechanics, the security model, and per-tool signatures live in
[[schrodinger-maestro-driver]]; this skill is the **pipeline** and its decision points.

## Core principle
A docking result is only as good as the **prepared receptor** and the **grid box**. Prep the
protein, place the box on the real binding site, dock, then **re-rank with MM-GBSA** (the raw
Glide score is a coarse filter, not a binding-energy estimate). Every product driver consumes a
license token and runs synchronously — sequence them, don't fan them out.

## The pipeline
| # | Step | Tool call | Output |
|---|------|-----------|--------|
| 1 | Prepare receptor | `prepwizard("receptor.pdb", "receptor_prep.mae")` | clean, protonated `.mae` |
| 2 | Place the box | `glide_grid("receptor_prep.mae", "grid.zip", center="x,y,z")` | `grid.zip` |
| 3 | Prepare ligand(s) | `ligprep("ligs.smi", "ligs_prepped.mae")` (or `smiles_to_3d` first) | prepared `.mae` |
| 4 | Dock | `glide_dock("grid.zip", "ligs_prepped.mae", "SP")` | `*_pv.maegz` poses |
| 5 | Rescore | `prime_mmgbsa("..._pv.maegz")` | `-out.csv` with `dG_Bind` |
| 6 | ADMET triage | `qikprop_admet("ligs_prepped.mae")` / `molecule_properties(smiles)` | ADMET CSV / panel |

Steps 1-2 (receptor) and step 3 (ligand) are independent — do either order, but both must finish
before step 4.

## Centering the grid box (the one real decision)

### Gotchas (learned from a live trypsin/3PTB run)
### Related
