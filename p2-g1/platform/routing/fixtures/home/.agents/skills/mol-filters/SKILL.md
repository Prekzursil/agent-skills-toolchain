---
name: mol-filters
description: "Use when mol filters is needed. Synthetic-accessibility SA_Score plus PAINS/BRENK/NIH structural-alert filtering (RDKit FilterCatalog) for a SMILES or SDF. Use when triaging docking or virtual-screening hits, flagging pan-assay-interference / problematic scaffolds, or scoring how hard a molecule."
license: MIT
---

# mol-filters — SA_Score + medicinal-chemistry structural alerts

Fills a real gap: the `rdkit` MCP server exposes descriptors/fingerprints but NOT Ertl's
synthetic-accessibility score or RDKit's `FilterCatalog` (PAINS/BRENK/NIH alerts). This skill
adds both as a small CLI, so you can triage screening/docking hits without a Schrodinger license.

## Run

Use the interpreter that has RDKit — the rdkit MCP server's venv:

```
"C:\Users\agentuser\source\repos\rdkit-mcp-server\.venv\Scripts\python.exe" \
  C:\Users\agentuser\.agents\skills\mol-filters\scripts\mol_filters.py <INPUT> [--json]
```

Input modes:
- single SMILES:  `... mol_filters.py "CC(=O)Oc1ccccc1C(=O)O"`
- one-per-line:   `... mol_filters.py --smiles-file mols.smi`  (blank / `#` lines skipped; `<SMILES> <name>` ok)
- SDF library:    `... mol_filters.py --sdf library.sdf`
- add `--json` for machine-readable output.

## What it reports (per molecule)

1. **SA_Score** — Ertl & Schuffenhauer (2009) synthetic accessibility, **1 = easy … 10 = hard**
   to synthesize. Loaded from RDKit's Contrib tree; if a wheel omits Contrib the score degrades
   to `null` with a note and the alert filters still run.
2. **Structural-alert hits** across `PAINS_A/B/C`, `BRENK`, `NIH`, `ZINC` — each hit names the
   catalog and the matched alert (e.g. `PAINS_B: rhod_sat_A(33)`). Zero hits = "Alerts: none".

Invalid SMILES are flagged `[INVALID]` and skipped, never crash the run.

## Acceptance (verified 2026-07-04, rdkit 2026.03.3)

- `"CC(=O)Oc1ccccc1C(=O)O"` (aspirin) → SA_Score ≈ **1.58**, no alerts.

### Notes
