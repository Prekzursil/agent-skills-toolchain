---
title: Phenibut study computational toolkit + Schrodinger/PyMOL config fixes (2026-06-15)
type: report
permalink: main/projects/phenibut/phenibut-study-computational-toolkit-schrodinger-py-mol-config-fixes-2026-06-15
tags:
- phenibut
- schrodinger
- pymol
- mcp
- computational-chemistry
- config
---

# Phenibut study — computational toolkit + config (2026-06-15)

Deep-research (17-agent workflow) over the licensed `D:\Program Files\Schrodinger 2026-2` suite +
`D:\Program Files\PyMOL`, plus config verification and an MCP expansion. Authoritative doc:
`proof_empty/SCHRODINGER_TOOLKIT.md`. Reusable skill: `~/.claude/skills/phenibut-compchem/SKILL.md`.

## Observations
- [owned] Full Schrodinger Drug Discovery Suite, local-entitlement license to 2050-01-01, customer HPDX2300, 145 features (126 drug-discovery): Glide, IFD/IFD-MD, FEP+, Desmond, Jaguar/QSite, Prime+STA_GPCR, QikProp, Phase, SiteMap, WaterMap, Epik, MacroModel, Canvas, AutoQSAR, AutoDesigner #owned
- [decision] Buy NOTHING for the structural/chemistry/ADMET/MD/QM layer — Maestro is sufficient for that ~30-40% of the program #tooling
- [gap] The mechanistic "why" (dopamine puzzle, withdrawal, prosocial effect) is neurobiology/systems pharmacology, not docking — covered by FREE tools: PK-Sim+MoBi (PBPK), STRING/Cytoscape (network), NEURON/Brian2 (circuit), Boltz-2 (co-folding), GROMACS (MD backup), DataWarrior (SAR viz) #gap
- [fix] Config: .mcp.json schrodinger env + server.py default + User env var all set to 2026-2 (was stale 2022-4 which broke the MCP with FileNotFoundError) #config
- [fix] PyMOL headless was silently running a 30-day eval (watermarked figures). Fixed by copying the valid entitlement D:\Program Files\PyMOL\pymol.lic to %USERPROFILE%\.pymol\license.lic, overwriting the auto-generated eval token. Verified watermark-free render of GABA-B 7EB2 #config
- [mcp] schrodinger MCP (C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py) expanded 12->18 tools: added pdb_fetch + qikprop_parse_results + pymol_render (no-license, TESTED) and sitemap + jaguar_pka + epik_enumerate (implemented, untested vs live run). Async/GPU suite (ifd_dock/fep_plus/desmond/watermap/autoqsar + job-queue) deferred to Phase 2 per honesty (untested speculative CLI). Spec: schrod_cards/_mcp_expansion.md #mcp
- [gotcha] schrodinger-mcp .venv base python (C:\Python314) is missing; validate with `py -3.14` + PYTHONPATH=.venv\Lib\site-packages #gotcha
- [pending] User must reconnect schrodinger MCP / restart Claude Code to reload the expanded server.py + 2026-2 env #action

## Relations
- part_of [[Phenibut mechanistic research program]]
- documented_in [[SCHRODINGER_TOOLKIT.md]]
