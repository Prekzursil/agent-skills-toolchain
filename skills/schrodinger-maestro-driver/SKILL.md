---
name: schrodinger-maestro-driver
description: Use when driving the local schrodinger MCP server for structure-based drug discovery on a Schrodinger Suite install - SMILES to 3D, LigPrep ligand preparation, Glide docking, QikProp ADMET, structure format conversion, RDKit descriptors, or the run_schrodinger_python escape hatch. Covers the SCHRODINGER environment setup, the license-token-free vs token-consuming tool split, and the precomputed Glide grid prerequisite.
---

# Schrodinger / Maestro Driver

## Overview

The `schrodinger` MCP server is a thin, security-conscious wrapper over a local Schrodinger Suite install. It NEVER imports the `schrodinger` package in-process; every tool builds an argv list and hands it to a single internal `_exec()` chokepoint that runs WITHOUT a shell. Client-supplied paths are validated by `_safe_path()` (rejects empty/flag-like values, normalizes to absolute) before reaching any argv, so there is no shell or argument injection. The `run_schrodinger_python` tool is an intentional arbitrary-code escape hatch - this server is for local, single-user use only.

- Source: `C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py` (+ `_sch_helper.py`, which runs INSIDE the Schrodinger interpreter where both `schrodinger` and a bundled `rdkit` are importable).
- Verified install: Schrodinger 2022-4, build 79134, at `D:\Program Files\Schrodinger 2022-4`.

## Environment Setup

The server reads `SCHRODINGER` from the environment; it defaults to the Windows path `D:\Program Files\Schrodinger 2022-4` and on POSIX you must set it.

- MCP registration (verified, stdio):
  - command: `C:\Users\Prekzursil\source\repos\schrodinger-mcp\.venv\Scripts\python.exe`
  - args: `C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py`
  - env: `SCHRODINGER` = `D:\Program Files\Schrodinger 2022-4`
- Cross-platform note: the server resolves `run.exe`/driver `.exe` on Windows and falls back to the extension-less `run`/driver names on POSIX. On POSIX, export `SCHRODINGER` to your suite root (e.g. `/opt/schrodinger/suites/2022-4`).
- Sanity check first: call `schrodinger_version` (wraps `run -v`) and `backend_info` (suite build + bundled RDKit version visible to the backend). If these fail, fix `SCHRODINGER` before anything else.

## The 9 Tools (grouped by license cost)

License-token-FREE (fast, no `-WAIT` driver):

- `schrodinger_version()` - suite version + resolved environment from `run -v`.
- `backend_info()` - suite build + bundled RDKit version + install path the backend sees.
- `smiles_to_3d(smiles, out_path, title="")` - SMILES to a 3D `.sdf` or `.mae` file. 3D via RDKit ETKDGv3 + MMFF; the output extension picks the format (`.mae` for Glide/Prime downstream, `.sdf` for portability).
- `molecule_properties(smiles)` - drug-likeness panel: formula, MW, logP, HBD/HBA, TPSA, rotatable bonds, rings, QED, Lipinski pass/fail (RDKit).
- `convert_structure(src, dst)` - convert a structure file between formats (`.sdf`, `.mae`, `.pdb`) via `schrodinger.structure`.
- `run_schrodinger_python(code, timeout_s=300)` - escape hatch: run a Python snippet inside the Schrodinger interpreter (has both `schrodinger` and `rdkit`). Returns returncode + truncated stdout/stderr. Use this for anything the 9 tools do not cover (protein prep, grid generation, custom analysis).

Token-CONSUMING product drivers (synchronous `-WAIT`; each call holds a license token until it finishes):

- `ligprep(input_file, output_mae, timeout_s=1200)` - LigPrep prepared 3D ligand states (ionization/tautomers/stereo). Input flag is auto-selected from the extension: `-ismi` for `.smi`, `-isd` for `.sdf`/`.sd`, else `-imae`. So LigPrep can take a `.smi` directly - `smiles_to_3d` is an ALTERNATIVE 3D entry point, not a mandatory predecessor.
- `qikprop_admet(structure_file, timeout_s=900)` - QikProp ADMET/physchem prediction on a 3D structure (`.mae`/`.sdf`). Returns the result `.CSV` path + first 3 lines.
- `glide_dock(grid_file, ligands_mae, precision="SP", timeout_s=3600)` - Glide docking of prepared ligands into a PRECOMPUTED grid (`.zip`). `precision` must be `HTVS`, `SP`, or `XP`. Writes a `glide_dock_job.in` and returns the `*_pv.maegz` pose-viewer path.

## Typical Workflow

1. `backend_info` / `schrodinger_version` - confirm the suite and `SCHRODINGER` resolve.
2. Build 3D ligands - either `smiles_to_3d(smiles, "lig.mae")` then `ligprep("lig.mae", "lig_prepped.mae")`, OR feed SMILES straight to `ligprep("lig.smi", "lig_prepped.mae")`.
3. Dock - `glide_dock(grid_file="grid.zip", ligands_mae="lig_prepped.mae", precision="SP")`. SEE THE GRID PREREQUISITE BELOW.
4. ADMET triage - `qikprop_admet("lig_prepped.mae")` and/or `molecule_properties(smiles)` for the quick descriptor panel.
5. Convert poses/structures as needed - `convert_structure("out.maegz", "out.sdf")`.

## CRITICAL: glide_dock needs a precomputed grid these 9 tools do NOT generate

`glide_dock` docks into an EXISTING receptor grid `.zip`. None of the 9 MCP tools produces a grid - there is no `glide_grid` tool and no protein-preparation tool. You must generate the grid out-of-band before `glide_dock` is callable:

- In the Maestro GUI (Receptor Grid Generation), OR
- Via `run_schrodinger_python` driving Glide grid generation / Protein Preparation Wizard inside the suite, OR
- By any prior pipeline that already produced a valid `<receptor>_grid.zip`.

Do not claim an end-to-end `SMILES -> docked pose` flow without this step; surface the grid requirement to the user.

## Common Mistakes

- Treating `smiles_to_3d` as a required step before `ligprep` - LigPrep accepts SMILES (`.smi`) directly.
- Calling `glide_dock` without a precomputed grid `.zip` (see above).
- Forgetting that the three drivers consume license tokens and run synchronously with long default timeouts (LigPrep 1200s, QikProp 900s, Glide 3600s). Concurrent driver calls compete for tokens.
- Passing flag-like or relative paths and assuming they pass `_safe_path` - they are normalized to absolute and rejected if they start with `-`.
- Expecting `convert_structure`/`smiles_to_3d` (.mae path) to work if the suite cannot import `schrodinger.adapter`/`schrodinger.structure` - those run inside the suite interpreter via `_sch_helper.py`.

## Related Skills

- `mechanistic-ddi-pipeline` - combine this server's structure tools with ToolUniverse CYP/DDI knowledge for a DDI verdict.
- `cheminformatics-rdkit` - standalone RDKit MCP for descriptors/fingerprints/similarity/scaffolds (no Schrodinger license needed).
