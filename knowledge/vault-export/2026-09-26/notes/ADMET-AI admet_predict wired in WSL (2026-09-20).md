---
title: ADMET-AI admet_predict wired in WSL (2026-09-20)
type: note
permalink: main/notes/admet-ai-admet-predict-wired-in-wsl-2026-09-20
tags:
- admet-ai
- compchem
- wsl
- wiring
- phenibut
---

# ADMET-AI (admet_predict CLI) local wiring

- [fact] admet-ai 2.0.1 installed in its own conda env `admet_ai` (Python 3.11.16) at `/home/prekzursil/miniforge3/envs/admet_ai` in WSL Ubuntu (sibling of biomni_e1/mdanalysis). Stack: torch 2.14.0+cpu (CPU-only, installed from the pytorch CPU index first to avoid CUDA wheels), chemprop 2.3.1, rdkit 2026.3.6, lightning 2.6.6, numpy 2.4.6, pandas 3.0.6. Launcher: `/home/prekzursil/bin/admet_predict`.
- [fact] Endpoint count settled at first run: **52 endpoints** (11 physchem/RDKit incl. QED, TPSA, PAINS/BRENK/NIH alerts + 41 TDC ADMET models: BBB_Martins, CYP*, hERG, Caco2_Wang, LD50_Zhu, VDss_Lombardo, ...). Output CSV = smiles + 52 value columns + 52 `_drugbank_approved_percentile` columns = 105 columns; manifest `resources/data/admet.csv` = 53 lines (header + 52).
- [fact] Weight auto-download REFUTED for 2.0.1: the 10 ensemble checkpoints (5x admet_classification 1,320,249 B + 5x admet_regression 1,300,041 B, ~13.1 MB) are BUNDLED in the PyPI wheel at `site-packages/admet_ai/resources/models/`; zero http refs in non-web package code; first run needed no network. CLI is offline-capable.
- [fact] Runtime ~13 s for 2 molecules on CPU (10 checkpoints, `--num_workers 0`). Sanity correct: phenibut MW 179.219 / BBB_Martins 0.732; caffeine MW 194.194 / BBB 0.982.
- [decision] CLI unit — no MCP server to register; `agents.json` untouched. Receipts at `C:\Users\Prekzursil\.agents\tmp\admet-ai\` (smiles_test.csv, preds_first_run.csv, admet_predict_wrapper.sh).
- [fact] WSL-bridge quoting lessons (this install): `wsl -d Ubuntu -- bash -c "..."` mangles `VAR=...`/`$VAR`, embedded double quotes, globs, AND backslash escapes (`tr -d \r` arrived as `tr -d r` and stripped every letter r). Working pattern: absolute paths, no vars, no nested quotes, no escapes; `wsl -- <program> args` direct exec is the most robust. Write tool emits LF (CRLF-strip unnecessary).

Related: [[phenibut-compchem]] (local ADMET screen for phenibut analogs now available), [[biomni-local]] (sibling conda env pattern).