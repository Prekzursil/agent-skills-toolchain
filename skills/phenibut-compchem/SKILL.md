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

## MCP: `schrodinger` (server at `C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py`)

After editing the server, **reconnect the MCP / restart Claude Code** to reload it.

Tested, ready: `schrodinger_version`, `backend_info`, `smiles_to_3d`, `molecule_properties`,
`convert_structure`, `ligprep`, `qikprop_admet`, `glide_grid`, `glide_dock`, `prepwizard`,
`prime_mmgbsa`, `run_schrodinger_python`, **`pdb_fetch`**, **`qikprop_parse_results`**, **`pymol_render`**.
Implemented-untested (verify first live run): **`sitemap`**, **`jaguar_pka`**, **`epik_enumerate`**.
Roadmap (Phase 2, async/GPU — spec in `schrod_cards/_mcp_expansion.md`): job-queue +
`ifd_dock`, `fep_plus_rbfe`, `desmond_md_*`, `watermap_run`, `phase_pharmacophore`,
`autoqsar_*`, `prime_homology`, glide XP/constrained variants.

## Standard structure-based pipeline (GABA-B + analogs)

1. `pdb_fetch('7eb2'|'7c7q'|'6uo8', out_dir)` — GABA-B cryo-EM structure.
2. `prepwizard(pdb, prepped.mae, ph=7.0)` — clean receptor → QC with `pymol_render`.
3. `sitemap(prepped.mae, ...)` — locate orthosteric + cryptic pockets (verify first run).
4. `smiles_to_3d` / `ligprep` (+ `epik_enumerate` for the zwitterion at pH 7.4) — prep ligands.
5. `jaguar_pka(ligand.mae, ...)` — confirm protonation state (load-bearing for binding mode).
6. `glide_grid(prepped.mae, grid.zip, center=...)` → `glide_dock(grid.zip, ligands.mae, 'SP'|'XP')`.
7. `prime_mmgbsa(pv.maegz)` — rescore dG_bind; `qikprop_admet` + `qikprop_parse_results` — ADMET/BBB.
8. `pymol_render([prepped.mae, pv.maegz], fig.png, highlight_selection='polymer within 5 of hetatm')`
   — publication pose figure.
9. (Phase 2) IFD-MD for the flexible VFT; FEP+ for <2 kcal/mol analog ranking; Desmond for dynamics.

## Biomedical & literature MCP layer — ToolUniverse + direct MCPs (PREFER over external installs)

Most "gap" capabilities are already callable **in-session** — no desktop install. Reach for an
external tool only when no MCP can do it (the short list below).

**ToolUniverse** (`mcp__tooluniverse__*`, 2,206 tools/511 categories, globally registered; 5 compact
tools). Workflow: `find_tools`/`grep_tools` → `get_tool_info(detail_level='full')` → `execute_tool`.
Map each phenibut question to its tools:

| Need | Q | ToolUniverse tools |
|---|---|---|
| Bioactivity / Ki / IC50 / targets (SAR table) | A,B,D | `ChEMBL` (29), `bindingdb`, `gtopdb` (IUPHAR — has GABA-B), `drugcentral`, `pubchem_bioassay` |
| GPCR target data (GABA-B = class-C GPCR) | A,B | `gpcrdb`, `gtopdb`, `uniprot` |
| ADMET / BBB / CNS | D | `ADMETAI_predict_BBB_penetrance`, `SwissADME_calculate_adme` (49 props), `admetai` (9) — ADMET-AI v1 vs v2 predictions differ (v2 = Chemprop-v2, retrained): re-run or version-label any existing phenibut ADMET number; pin the exact version in every receipt |
| Off-target panel (dopamine puzzle) | B | `swiss_target` (SwissTargetPrediction), `stitch`, `dgidb`, `pharos` |
| Pathway / network (GABA-B→VTA, neuroadaptation) | B,E | `reactome`, `kegg`, `wikipathways`, `string_network`, `omnipath` (ligand-receptor) |
| Drug-drug interactions (phenibut + amphetamine/alcohol/benzo) | C | `DailyMed_parse_drug_interactions` (CYP/P-gp), `sider`, `DrugSynergy_calculate_loewe`, `synergxdb`, `dose_response` |
| Structures (no install) | all | `rcsb_pdb` (39), `pdbe`, `alphafold`, `swissmodel`, `esmfold` |
| Literature beyond the corpus | all | `EuropePMC`, `pubmed`, `semantic_scholar`, `OpenAlex`, `unpaywall`, `biorxiv`/`medrxiv` |
| Free docking cross-check | B | `swissdock` |
| Enzyme/inhibition kinetics math | C,D | `EnzymeKinetics_calculate`, `DrugSynergy_calculate_loewe` |

**Direct MCPs in-session** (often richer than ToolUniverse's wrapper):
`mcp__claude_ai_ChEMBL__*`, `mcp__claude_ai_PubMed__*`, `mcp__claude_ai_bioRxiv__*`,
`mcp__claude_ai_Clinical_Trials__*`, `mcp__rdkit__*` (74 descriptor tools),
`mcp__scholarly-access__*` (OA PDF resolve/fetch — corpus expansion). See the `tooluniverse` and
`consensus-tooluniverse-research` skills; the `bionlp` workspace (`Downloads/bionlp/`) has the full setup.

## Still needs an external install (no MCP covers it)

- **PBPK brain kinetics** (phenibut vs baclofen CNS exposure) → **PK-Sim + MoBi** (free, OSP Suite).
- **VTA disinhibition circuit** model (the dopamine puzzle's *circuit* answer) → **NEURON/Brian2** + ModelDB (free).
- **All-atom MD** as a free Desmond backup / cross-validation → **GROMACS / OpenMM**.
- **Protein-ligand co-folding** for novel analogs (no PDB template) → **Boltz-2** (`pip install boltz`); structure-only is covered by ToolUniverse `alphafold`/`esmfold`.
- **SAR-cliff / MMP visual analysis** → **DataWarrior** (free).

## Gotchas

- The MCP never imports `schrodinger` in-process; everything goes through `$SCHRODINGER/run.exe`.
  The `.mcp.json` env block pins `SCHRODINGER=D:\Program Files\Schrodinger 2026-2` (authoritative).
- IFD-MD, FEP+, Desmond, WaterMap-MD, DeepAutoQSAR are **GPU / Linux-host**; don't expect them to run
  synchronously on the Windows box — they need the job-queue (async) pattern.
- Run PyMOL as a **separate subprocess** from the Schrodinger Python runtime (interpreter conflict).
