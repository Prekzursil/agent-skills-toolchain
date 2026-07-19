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
`glide_grid` needs a box center. Pick by whether a co-crystal ligand is still in the receptor:

- **Co-crystal ligand present → use `ligand_molnum` (PREFERRED).** It both centers the box on that
  molecule AND **excludes it from the receptor grid**, leaving the pocket open. Find its 1-based
  molecule number with `run_schrodinger_python`:
  ```python
  code = (
    "from schrodinger import structure\n"
    "st=structure.StructureReader.read(r'receptor_prep.mae')\n"
    "mn=[i for i,m in enumerate(st.molecule,1) if any(a.pdbres.strip()=='BEN' for a in m.atom)]\n"  # ligand resname
    "print('MOLNUM %d'%mn[0] if mn else 'NO_LIG')\n"
  )
  ```
  then `glide_grid(prep, "grid.zip", ligand_molnum=<n>)`.
- **No bound ligand (apo / known site) → `center="x,y,z"`** explicit coordinates.

**Gotcha (learned the hard way):** centering on the ligand's *centroid coordinates* while the
ligand is still in the receptor file does NOT exclude it — the pocket stays occupied and Glide
returns `NO GOOD POSES FOUND` even for the native ligand. Use `ligand_molnum` (or strip the
ligand first). Never guess a center blindly — surface the binding-site choice to the user.

## Gotchas (learned from a live trypsin/3PTB run)
- **`ligprep` output must be under the cwd.** The server passes a basename + runs in the output
  dir; if you call the driver by hand, an absolute `-omae` (esp. with an 8.3 `PREKZU~1` short
  path) fails its "not under the current working directory" check.
- **License tokens are serial + long.** Defaults: prepwizard/glide_grid/ligprep ~1800s,
  glide_dock/prime_mmgbsa ~3600s. Concurrent driver calls compete for tokens — run the chain
  sequentially.
- **Grid center is mandatory** — `glide_grid` errors without `center` or `ligand_molnum`.
- **MM-GBSA input is the pose-viewer**, not the grid — feed `prime_mmgbsa` the `*_pv.maegz` that
  `glide_dock` emits. `glide_dock` sets `POSE_OUTTYPE poseviewer` so the `*_pv.maegz` (receptor +
  pose) exists; Prime then DROPS the `_pv` suffix, writing `<job>-out.csv` (the server resolves
  both names so you don't have to).
- **Validated live END-TO-END on this host:** prepwizard -> glide_grid(ligand_molnum) -> ligprep ->
  glide_dock -> prime_mmgbsa on 3PTB (trypsin + benzamidine) → MM-GBSA `dG_Bind` approx -19.7
  kcal/mol; `qikprop_admet` on warfarin → full ADMET CSV. All six drivers returned rc 0.

## Related
- [[schrodinger-maestro-driver]] - per-tool reference, signatures, security model, setup.
- `cheminformatics-rdkit` - license-free descriptors/similarity if you don't need docking.
- `mechanistic-ddi-pipeline` - fold structure evidence into a ToolUniverse DDI verdict.
