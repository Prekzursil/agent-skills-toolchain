---
name: schrodinger-maestro-driver
description: Use when driving the local schrodinger MCP server for structure-based
  drug discovery on a Schrodinger Suite install - SMILES to 3D, LigPrep, Protein Preparation
  Wizard, Glide grid generation, Glide docking, Prime MM-GBSA binding free energy,
  QikProp ADMET, structure format conversion, RDKit descriptors, or the run_schrodinger_python
  escape hatch. Covers SCHRODINGER environment setup and the license-token-free vs
  token-consuming split. NOT for the whole prep-to-rescore campaign (use structure-based-screening).
permalink: dqverify-repo-20261013/skills/schrodinger-maestro-driver/skill
---

# Schrodinger / Maestro Driver

## Overview

The `schrodinger` MCP server is a thin, security-conscious wrapper over a local Schrodinger Suite install. It NEVER imports the `schrodinger` package in-process; every tool builds an argv list and hands it to a single internal `_exec()` chokepoint that runs WITHOUT a shell. Client-supplied paths are validated by `_safe_path()` (rejects empty/flag-like values, normalizes to absolute) before reaching any argv, so there is no shell or argument injection. The `run_schrodinger_python` tool is an intentional arbitrary-code escape hatch - this server is for local, single-user use only.

- Source: `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py` (+ `_sch_helper.py`, which runs INSIDE the Schrodinger interpreter where both `schrodinger` and a bundled `rdkit` are importable).
- Validation boundary: the core pipeline was live-tested on Schrodinger 2022-4, build 79134. The expanded 67-tool surface targets 2026-2 and is statically verified, with live-box smoke testing still pending.

## Environment Setup

The server reads `SCHRODINGER` from the environment; it defaults to the Windows path `D:\Program Files\Schrodinger 2026-2` and on POSIX you must set it.

- MCP registration (canonical stdio target):
  - command: `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\.venv\Scripts\python.exe`
  - args: `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py`
  - env: `SCHRODINGER` = `D:\Program Files\Schrodinger 2026-2`
- Cross-platform note: the server resolves `run.exe`/driver `.exe` on Windows and falls back to the extension-less `run`/driver names on POSIX. On POSIX, export `SCHRODINGER` to your suite root (e.g. `/opt/schrodinger/suites/2026-2`).
- Sanity check first: call `schrodinger_version` (wraps `run -v`) and `backend_info` (suite build + bundled RDKit version visible to the backend). If these fail, fix `SCHRODINGER` before anything else.

## The 67 Tools

The core structure and docking pipeline is documented in detail first. The
expanded workflows are grouped afterward so you can route directly to the typed
tool instead of falling back to arbitrary Python.

### Core structure and docking pipeline

License-token-FREE (fast, no `-WAIT` driver):

- `schrodinger_version()` - suite version + resolved environment from `run -v`.
- `backend_info()` - suite build + bundled RDKit version + install path the backend sees.
- `smiles_to_3d(smiles, out_path, title="")` - SMILES to a 3D `.sdf` or `.mae` file. 3D via RDKit ETKDGv3 + MMFF; the output extension picks the format (`.mae` for Glide/Prime downstream, `.sdf` for portability).
- `molecule_properties(smiles)` - drug-likeness panel: formula, MW, logP, HBD/HBA, TPSA, rotatable bonds, rings, QED, Lipinski pass/fail (RDKit).
- `convert_structure(src, dst)` - convert a structure file between formats (`.sdf`, `.mae`, `.pdb`) via `schrodinger.structure`.
- `run_schrodinger_python(code, timeout_s=300)` - escape hatch: run a Python snippet inside the Schrodinger interpreter (has both `schrodinger` and `rdkit`). Returns returncode + truncated stdout/stderr. Use this only when the typed tools do not cover the task (custom analysis, batch scripting, computing a binding-site centroid).

Token-CONSUMING product drivers (synchronous `-WAIT`; each call holds a license token until it finishes). Listed in pipeline order:

- `prepwizard(input_file, output_mae, ph=7.0, fill_sidechains=True, timeout_s=1800)` - Protein Preparation Wizard: clean a raw receptor (`.pdb`/`.mae`) - add hydrogens, assign bond orders, optionally fill missing side chains, set protonation at `ph` via PROPKA. Output is a prepared `.mae` ready for `glide_grid`. (The driver lives in `$SCHRODINGER/utilities`; `_driver()` resolves it there.)
- `ligprep(input_file, output_mae, timeout_s=1200)` - LigPrep prepared 3D ligand states (ionization/tautomers/stereo). Input flag is auto-selected from the extension: `-ismi` for `.smi`, `-isd` for `.sdf`/`.sd`, else `-imae`. So LigPrep can take a `.smi` directly - `smiles_to_3d` is an ALTERNATIVE 3D entry point, not a mandatory predecessor.
- `glide_grid(receptor_mae, out_grid_zip, center="", ligand_molnum=0, inner_box=10, outer_box=30, timeout_s=1800)` - generate the Glide docking grid (`.zip`) from a prepared receptor. Define the box EITHER with explicit `center="x,y,z"` coordinates OR with `ligand_molnum` (1-based molecule number of a co-crystallized ligand already in the receptor file). This is the step `glide_dock` needs.
- `glide_dock(grid_file, ligands_mae, precision="SP", timeout_s=3600)` - Glide docking of prepared ligands into a grid `.zip` (from `glide_grid`). `precision` must be `HTVS`, `SP`, or `XP`. Writes a `glide_dock_job.in` and returns the `*_pv.maegz` pose-viewer path.
- `prime_mmgbsa(pose_viewer, timeout_s=3600)` - Prime MM-GBSA binding free-energy (dG bind) rescoring of docked poses; input is the `*_pv.maegz` from `glide_dock`. Returns the `-out.csv` (with `r_psp_MMGBSA_dG_Bind`) + `-out.maegz`. Far more reliable than the raw Glide score.
- `qikprop_admet(structure_file, timeout_s=900)` - QikProp ADMET/physchem prediction on a 3D structure (`.mae`/`.sdf`). Returns the result `.CSV` path + first 3 lines.

### Expanded workflow surface

- **Diagnostics and structure I/O (4):** `backend_doctor`,
  `structure_properties_extract`, `pdb_fetch`, `install_cure`.
- **Prep, docking, and pose workflows (10):** `prep_target`, `ensemble_dock`,
  `al_dock`, `dock_triage`, `induced_fit_docking`, `covalent_docking`,
  `pose_validity`, `pose_interaction_fingerprint`, `pose_viewer_split`,
  `pymol_render`.
- **Screening, properties, and analogs (12):** `qikprop_parse_results`,
  `sitemap`, `confgen`, `shape_screen`, `canvas_fingerprints`,
  `canvas_descriptors`, `phase_pharmacophore`, `phase_screen`, `ligfilter`,
  `propfilter`, `analog_scan`, `reaction_enumerate`.
- **MD and free energy (14):** `desmond_setup`, `desmond_md`,
  `desmond_trajectory_analysis`, `desmond_interactions`,
  `desmond_membrane_setup`, `thermal_mmgbsa`, `fep_plus`, `fep_map_build`,
  `fep_parse_results`, `fep_absolute_binding`, `watermap`, `bpmd`,
  `bpmd_ladder`, `openmm_from_prepared`.
- **QM, advanced modeling, and ML (10):** `jaguar_pka`, `jaguar_qm`,
  `epik_enumerate`, `epik_pka`, `qm_cluster_extract`,
  `macromodel_confsearch`, `residue_scanning`, `qsite_qmmm`,
  `autoqsar_build`, `autoqsar_predict`.
- **Job and GPU operations (5):** `job_server_control`, `job_status`, `job_wait`,
  `job_restart`, `schrodinger_gpu_pool`.

## Typical Workflow (end-to-end structure-based screening)

1. `backend_info` / `schrodinger_version` - confirm the suite and `SCHRODINGER` resolve.
2. Receptor side - `prepwizard("receptor.pdb", "receptor_prep.mae")` then `glide_grid("receptor_prep.mae", "grid.zip", center="x,y,z")`.
3. Ligand side - either `smiles_to_3d(smiles, "lig.mae")` then `ligprep("lig.mae", "lig_prepped.mae")`, OR feed SMILES straight to `ligprep("lig.smi", "lig_prepped.mae")`.
4. Dock - `glide_dock("grid.zip", "lig_prepped.mae", "SP")` -> `*_pv.maegz`.
5. Rescore + triage - `prime_mmgbsa("..._pv.maegz")` for dG bind; `qikprop_admet("lig_prepped.mae")` and/or `molecule_properties(smiles)` for ADMET/descriptors.
6. Convert poses/structures as needed - `convert_structure("out.maegz", "out.sdf")`.

The `structure-based-screening` skill spells out this full pipeline with the centroid trick and license-token notes.

## Full pipeline is now in-server (receptor prep -> grid -> dock -> rescore)

As of the `prepwizard` / `glide_grid` / `prime_mmgbsa` addition, the whole structure-based chain is callable from this MCP - no Maestro GUI step required:

1. `prepwizard("raw_receptor.pdb", "receptor_prep.mae")` - clean/protonate the receptor.
2. `glide_grid("receptor_prep.mae", "grid.zip", center="x,y,z")` - build the docking box. Center it on explicit coordinates, or on a co-crystallized ligand via `ligand_molnum`. To derive a centroid from a co-crystal ligand, use `run_schrodinger_python` to average that ligand's atom coordinates.
3. `glide_dock("grid.zip", "lig_prepped.mae", "SP")` - dock.
4. `prime_mmgbsa("..._pv.maegz")` - rescore with binding free energy.

`glide_dock` still requires a grid `.zip` - but `glide_grid` now produces it, so a true `receptor.pdb + SMILES -> docked, rescored pose` flow is possible end-to-end. The grid box still needs a sensible center (the binding site); surface that choice to the user rather than guessing blindly.

## Multi-GPU pool on a cloud box (Linux) - and the BPMD/JobDJ "No job found" download gotcha

On a multi-GPU Linux box (e.g. a 4xH100 node) a SINGLE shared `jobserverd` strips `CUDA_VISIBLE_DEVICES` from its subjobs, so every job piles onto GPU 0. The working pattern (see `schrod-gpu-pool.sh`, toolchain PR #79) is one CVD-pinned `jobserverd` per GPU, with each launch routed to its GPU's server via `jsc local-server-dir --set <pool>/js_gpu<g>` at submit time. FEP+ is the exception - it self-parallelizes, so use `multisim -maxjob N` instead of the pool.

- GOTCHA (cost real re-runs): a driver that ends with a JobDJ `jsc download` - BPMD (`binding_pose_metadynamics.py`), and any `-WAIT` driver that downloads its own results - FAILS the download step when the pool restores the default jobserver after launch. The compute RAN fine on the pinned GPU, but the driver's final `jsc download <jobid>` queries the RESTORED default server, which has no record of the job -> `No job found for JobId`. This is a silent partial failure: GPU work done, results never collected.
- FIX (validated): give each concurrent driver its OWN isolated `HOME` (e.g. `export HOME=/root/bpmd_iso_<ligand>`) BEFORE routing. Then inside that HOME: `jsc local-server-dir --set <pool>/js_gpu<g>`, `export CUDA_VISIBLE_DEVICES=<g>`, and run the driver `-HOST localhost -SUBHOST localhost:1 -WAIT`. The isolated HOME pins the driver's `~/.schrodinger` jobserver config for its WHOLE lifecycle, so submit AND the final JobDJ download resolve against the SAME per-driver server. Shared-HOME pool BPMD failed every download; isolated-HOME BPMD produced `-out.maegz` + CompScore cleanly.
- Extract BPMD scores from the driver's real output: `proplister -c bpmd_<L>-out.maegz` (CompScore/PoseScore properties) - do NOT `head` the per-frame `-out.csv`, which is trajectory data, not the summary.

## Common Mistakes

- Treating `smiles_to_3d` as a required step before `ligprep` - LigPrep accepts SMILES (`.smi`) directly.
- Calling `glide_dock` without first running `glide_grid` (it needs the grid `.zip`); or calling `glide_grid` with no box center (pass `center="x,y,z"` or `ligand_molnum`).
- Running `prepwizard` and expecting the top-level driver - it lives in `$SCHRODINGER/utilities` (the server resolves it; a hand-rolled call to `$SCHRODINGER/prepwizard` will miss).
- Forgetting that product drivers consume license tokens, often with long default timeouts. Concurrent driver calls compete for tokens.
- Passing flag-like or relative paths and assuming they pass `_safe_path` - they are normalized to absolute and rejected if they start with `-`.
- Expecting `convert_structure`/`smiles_to_3d` (.mae path) to work if the suite cannot import `schrodinger.adapter`/`schrodinger.structure` - those run inside the suite interpreter via `_sch_helper.py`.

## Related Skills

- [[structure-based-screening]] - the end-to-end receptor-prep -> grid -> dock -> MM-GBSA pipeline that chains these tools, with the centroid trick and license-token notes.
- `mechanistic-ddi-pipeline` - combine this server's structure tools with ToolUniverse CYP/DDI knowledge for a DDI verdict.
- `cheminformatics-rdkit` - standalone RDKit MCP for descriptors/fingerprints/similarity/scaffolds (no Schrodinger license needed).