---
name: phenibut-compchem
description: "Use when planning or running phenibut computational pharmacology with Schrodinger and PyMOL, including GABA-B docking, SAR, ADMET, MD, FEP+, QM pKa, or publication figures."
metadata:
  type: project
---

# Phenibut Computational Pharmacology — Tool Routing & Pipeline

Companion to `proof_empty/RESEARCH_PLAN.md` and `proof_empty/SCHRODINGER_TOOLKIT.md`
(the authoritative capability map + gap analysis). Read those for the full module/feature detail.

## Ground truth

- **You own the full Schrodinger Drug Discovery Suite** (2026-2, licensed to 2050): Glide, IFD/IFD-MD,
  FEP+, Desmond, Jaguar/QSite (QM), Prime+STA_GPCR, QikProp, Phase, SiteMap, WaterMap, Epik,
  MacroModel, Canvas, AutoQSAR, AutoDesigner. **Buy nothing for the structural/chemistry layer.**
- **PyMOL 3.1.7** (Incentive) is the only figure tool. Headless: `Scripts\pymol.exe -cq script.pml`.
  License lives at `%USERPROFILE%\.pymol\license.lic` (must be the real entitlement, not the
  auto-generated eval token — else figures get a watermark).
- **The mechanistic "why" questions (dopamine puzzle, withdrawal, prosocial effect) are
  neurobiology/systems pharmacology, not docking.** Corpus synthesis + free tools (PK-Sim,
  STRING/Cytoscape, NEURON/Brian2) are the main engine; computation tests falsifiable sub-hypotheses.

## MCP: `schrodinger` (server at `C:\Users\agentuser\source\repos\schrodinger-mcp\server.py`)

After editing the server, **reconnect the MCP / restart Claude Code** to reload it.

Tested, ready: `schrodinger_version`, `backend_info`, `smiles_to_3d`, `molecule_properties`,
`convert_structure`, `ligprep`, `qikprop_admet`, `glide_grid`, `glide_dock`, `prepwizard`,
`prime_mmgbsa`, `run_schrodinger_python`, **`pdb_fetch`**, **`qikprop_parse_results`**, **`pymol_render`**.

### Standard structure-based pipeline (GABA-B + analogs)
### Still needs an external install (no MCP covers it)
### Gotchas
