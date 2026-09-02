---
name: ddi-admet-research
description: Use as the front-end/router for biomedical research via the tooluniverse MCP server (Harvard Zitnik lab, 2206 tools) - drug-drug interactions, ADMET/physchem prediction, CYP450 enzyme roles, target research, FDA drug labels, drug repurposing, and pharmacovigilance. Routes to the detailed tooluniverse-* skills. Use when a question needs biomedical knowledge-base lookups.
---

# DDI / ADMET Research (ToolUniverse front-end)

## Overview

This skill is a THIN ROUTER over the `tooluniverse` MCP server and the already-installed `tooluniverse-*` deep skills. Do NOT re-implement DDI/ADMET reasoning here - dispatch to the specialized skill, then call ToolUniverse tools.

- Server: ToolUniverse (Apache-2.0, Harvard Zitnik lab), 2206 biomedical tools covering DDI, ADMET, CYP, targets, FDA labels, repurposing, and pharmacovigilance.
- Registration (verified, stdio): command `uvx`, args `tooluniverse==1.2.4`, env `PYTHONIOENCODING` = `utf-8`. The stdio entry point is `tooluniverse.smcp_server:run_default_stdio_server`.
- Cross-platform: `uvx` works on Windows and POSIX identically; no path edits needed.

## Route to the Right Installed Skill

Deep, ready-made skills already live at `~/.agents/skills` (on Windows: `C:\Users\Prekzursil\.agents\skills`). Pick by intent:

- Drug-drug interactions, polypharmacy, CYP/UGT mechanisms -> `tooluniverse-drug-drug-interaction`
- ADMET / physicochemical / drug-likeness prediction -> `tooluniverse-admet-prediction`
- Hazard, GHS, handling, exposure -> `tooluniverse-chemical-safety`
- Target identification / validation -> `tooluniverse-target-research`
- Repositioning / new indications -> `tooluniverse-drug-repurposing`
- Adverse events, signal detection, post-market safety -> `tooluniverse-pharmacovigilance`
- Mechanism of action -> `tooluniverse-drug-mechanism-research`

Invoke the matching skill first; this front-end only handles routing + the connection.

## Real ToolUniverse Tools (verified in use)

Only call tools you can confirm exist. Confirmed from the installed DDI skill:

- `ChEMBL_get_drug_mechanisms` - mechanism / CYP substrate-inhibitor-inducer data.
- `drugbank_get_drug_interactions_by_drug_name_or_id` - known DDI / transporter interactions.
- `DailyMed_get_spl_by_setid` - FDA label (SPL) text, highest evidence tier.
- `PubMed_search_articles` - clinical literature.

For the full set, list the server's tools at runtime rather than guessing from the 2206 catalog.

## Quick Workflow

1. Identify intent and route to the matching `tooluniverse-*` skill (table above).
2. Confirm the `tooluniverse` MCP server is connected (`claude mcp get tooluniverse`).
3. Resolve drug/target names to standard identifiers (ChEMBL/DrugBank) before querying.
4. Query in the order the routed skill prescribes; grade evidence (FDA label > clinical study > theoretical).
5. Produce the report the routed skill specifies; cite data sources.

## Common Mistakes

- Duplicating the deep `tooluniverse-*` skill logic here instead of routing to it.
- Enumerating or inventing tool names from the 2206 catalog - call only verified tools or list them at runtime.
- Skipping identifier resolution and querying by free-text drug names.
- Using this for local structure work - that is the `schrodinger-maestro-driver` and `cheminformatics-rdkit` skills.

## Related Skills

- `mechanistic-ddi-pipeline` - the cross-stack orchestrator that fuses ToolUniverse CYP/DDI knowledge with Schrodinger structure into a single DDI verdict.
- `cheminformatics-rdkit` - local RDKit descriptors/similarity for chemistry questions.
