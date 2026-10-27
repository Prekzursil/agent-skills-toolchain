# Schrodinger MCP — live validation record

Host: Schrodinger Suite **2022-4** (`D:\Program Files\Schrodinger 2022-4`), Windows, 2026-06-06.
Reproduce with the two committed scripts (each writes to a throwaway temp dir; nothing
license-bearing is committed):

```
.venv\Scripts\python.exe _e2e_test.py                          # cheminformatics + qikprop
set PIPE_PDB=<path to 3PTB.pdb> & .venv\Scripts\python.exe _pipeline_test.py   # full docking chain
```

## 1. `_e2e_test.py` — warfarin SMILES -> 3D -> QikProp ADMET  (PASS, rc 0)
- `smiles_to_3d` warfarin (`CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O`) -> `warfarin.mae`, **39 atoms**.
- `qikprop_admet` -> `warfarin.CSV`, **returncode 0**. CSV header (first fields):
  `molecule,#stars,#amine,#amidine,#acid,#amide,#rotor,...,QPlogPo/w,QPlogS,QPlogHERG,QPPCaco,QPlogBB,QPPMDCK,QPlogKp,...,HumanOralAbsorp`

## 2. `_pipeline_test.py` — full structure-based chain on PDB **3PTB** (trypsin + benzamidine)  (PASS, rc 0 each)
| Step | Tool | Result |
|------|------|--------|
| 1 | `prepwizard(3PTB.pdb -> receptor_prep.maegz)` | rc 0 |
| 2 | locate co-crystal ligand (BEN) via `run_schrodinger_python` | molecule #2 |
| 3 | `glide_grid(receptor_prep.maegz, grid.zip, ligand_molnum=2)` | rc 0, `grid.zip` (box centers on + excludes BEN) |
| 4 | `ligprep(benzamidine.smi -> lig_prepped.mae)` | rc 0 |
| 5 | `glide_dock(grid.zip, lig_prepped.mae, "SP")` | rc 0, `glide_dock_job_pv.maegz` (poses) |
| 6 | `prime_mmgbsa(glide_dock_job_pv.maegz)` | rc 0, `glide_dock_job-out.csv` |

**MM-GBSA result:** `benzamidine`, `r_psp_MMGBSA_dG_Bind = -19.6792651260257` kcal/mol.

## Lessons baked into the tools (each found by THIS live run, not by static checks)
- `ligprep` rejects an absolute `-omae`; pass the basename + run in the output dir.
- `glide_grid` must EXCLUDE the co-crystal ligand (use `ligand_molnum`); centering on bare
  coordinates while the ligand stays in the receptor -> `NO GOOD POSES FOUND`.
- `glide_dock` writes `POSE_OUTTYPE poseviewer` so `prime_mmgbsa` gets the receptor+pose complex.
- `prime_mmgbsa` drops the `_pv` suffix: input `<job>_pv.maegz` -> output `<job>-out.csv`.
