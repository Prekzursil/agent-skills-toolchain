---
name: mechanistic-ddi-pipeline
description: Use to orchestrate a full mechanistic drug-drug interaction verdict by combining two MCP stacks - ToolUniverse CYP/UGT/transporter and DDI knowledge plus FDA-label evidence with Schrodinger structure tools (SMILES to 3D, descriptors, ADMET, optional docking). Use when a DDI question needs both biomedical knowledge-base lookups and structure-level computation fused into one perpetrator-victim verdict with severity, mechanism, and management.
---

# Mechanistic DDI Pipeline (cross-stack orchestrator)

## Overview

This skill is the GLUE between two servers. It fuses ToolUniverse knowledge (CYP/UGT/transporter roles, DDI records, FDA labels, literature) with Schrodinger structure-level computation (3D generation, drug-likeness descriptors, QikProp ADMET, optional Glide docking) into one perpetrator-victim DDI verdict. It does not replace the deep `tooluniverse-drug-drug-interaction` skill - it adds the structure layer.

Stacks used:

- `tooluniverse` MCP (knowledge) - see the `ddi-admet-research` and `tooluniverse-drug-drug-interaction` skills for routing and tool details.
- `schrodinger` MCP (structure) - see the `schrodinger-maestro-driver` skill for the 12 tools, the license-token split, and the full prep -> grid -> dock -> MM-GBSA pipeline (`glide_grid` builds the grid in-server).

## When to Use

- A DDI question where mechanism must be backed by both pathway knowledge AND molecular evidence (descriptors, ADMET, or a docking pose into a CYP/target structure).
- A novel or under-documented compound (limited DDI records) where structure-derived properties inform the prediction.
- A case where you must reconcile a knowledge-base claim with computed physchem/ADMET (e.g., does the structure support the proposed CYP-substrate role).

If the question is purely knowledge-based, use `ddi-admet-research` instead - do not spin up structure tools unnecessarily.

## Orchestrated Workflow

1. Frame the pair with the perpetrator-victim model (who changes whom). Apply the CYP/UGT reasoning from `tooluniverse-drug-drug-interaction` BEFORE any tool call.
2. Knowledge pass (ToolUniverse): resolve identifiers, then query CYP/transporter roles (`ChEMBL_get_drug_mechanisms`), known interactions (`drugbank_get_drug_interactions_by_drug_name_or_id`), FDA label evidence (`DailyMed_get_spl_by_setid`), and literature (`PubMed_search_articles`).
3. Structure pass (Schrodinger): for each drug, compute the drug-likeness panel (`molecule_properties(smiles)`); generate 3D where needed (`smiles_to_3d`); run `qikprop_admet` on a prepared structure for ADMET/physchem that supports or challenges the predicted pathway.
4. Optional docking corroboration: prep the receptor (`prepwizard`) and build a grid (`glide_grid`) for a CYP isoform/target, then dock the perpetrator/victim with `glide_dock` to test the proposed binding/inhibition hypothesis, optionally rescoring with `prime_mmgbsa`. No receptor structure on hand = skip docking (see `structure-based-screening`).
5. Synthesize the verdict: combine mechanism (PK via CYP/UGT/transporter, PD overlap), severity (Contraindicated/Major/Moderate/Minor), direction (inhibitor up / inducer down), and structure-derived support into a single ranked conclusion with management + monitoring.
6. Grade every claim: FDA label (★★★) > clinical study (★★☆) > theoretical/structure-inferred (★☆☆). Mark structure-derived inferences as supporting, not definitive.

## Conflict Resolution

- Knowledge says interaction, structure says implausible (e.g. descriptors/ADMET inconsistent with the claimed pathway): report both, flag the conflict, prefer the FDA-label/clinical-study tier and note the structural caveat.
- Structure suggests a pathway with no DDI record: label it theoretical (★☆☆); recommend monitoring, not a hard verdict.

## Common Mistakes

- Letting this skill duplicate `tooluniverse-drug-drug-interaction` - delegate the knowledge reasoning, add only the structure layer.
- Calling `glide_dock` without first running `glide_grid` - it needs the grid `.zip` (and `glide_grid` needs a box center: coords or `ligand_molnum`).
- Treating computed ADMET/descriptors as clinical evidence - they are supporting (★☆☆), never override FDA labels.
- Burning license tokens on Schrodinger drivers (`ligprep`/`qikprop_admet`/`glide_dock`, long `-WAIT` timeouts) when the knowledge pass already answers the question.

## Related Skills

- `ddi-admet-research` - knowledge-only ToolUniverse front-end / router.
- `schrodinger-maestro-driver` - the structure MCP details and the full docking pipeline.
- `tooluniverse-drug-drug-interaction` - the deep DDI reasoning framework this orchestrator delegates to.
