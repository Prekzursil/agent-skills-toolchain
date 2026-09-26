---
title: MDAnalysis 2.10.0 + ProLIF 2.2.2 + RDKit env (WSL mdanalysis)
type: note
permalink: main/notes/mdanalysis-2.10.0-pro-lif-2.2.2-rdkit-env-wsl-mdanalysis
tags:
- mdanalysis
- prolif
- rdkit
- wsl
- conda
- env-receipt
---

MDAnalysis trajectory-analysis env installed in WSL Ubuntu (workflow adoptable-wiring unit 4, 2026-09-20).

- [fact] Env: conda env `mdanalysis` at `/home/prekzursil/miniforge3/envs/mdanalysis` in WSL Ubuntu; python 3.11.16, mamba 2.9.0; interpreter path `~/miniforge3/envs/mdanalysis/bin/python` (invoke from Windows as `wsl -d Ubuntu -- bash -lc "~/miniforge3/envs/mdanalysis/bin/python ..."`).
- [fact] Versions measured: MDAnalysis 2.10.0 (conda-forge), rdkit 2026.03.6 (conda-forge), prolif 2.2.2 (PyPI wheel — conda-forge only has 2.2.1). Installed via `mamba create -n mdanalysis -c conda-forge python=3.11 mdanalysis=2.10.0 rdkit -y` then `pip install prolif==2.2.2` (pip pulled gemmi, multiprocess, dill, psutil).
- [fact] ProLIF 2.2.2 API notes: `Ligand`/`Protein` classes are GONE — use `prolif.Molecule` with `.from_rdkit(mol)` / `.from_mda(atomgroup)` (no `.from_smiles`). `plf.datafiles` is a MODULE with `TOP`/`TRAJ`/`WATER_TOP`/`WATER_TRAJ` path attributes (a bundled protein+LIG complex, not the old vina mol2).
- [fact] ProLIF from_mda requires explicit hydrogens in the MDAnalysis topology (MDAnalysis RDKit converter raises otherwise) — strip-H universes need `force=True`.
- [decision] No MCP registration for this unit — it is a compute env, not an MCP server; `.agents/agents.json` and `~/.claude.json` untouched.
- [fact] End-to-end proof: Fingerprint over bundled TOP complex gave IFP dataframe shape (1, 21) with non-zero interactions; probe script kept at `C:\Users\Prekzursil\.claude\tmp\mdanalysis_env_probe.py`.

Related: [[biomni-local]], [[claude-science-local]]
