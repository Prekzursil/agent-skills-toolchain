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

### Conflict Resolution
### Common Mistakes
### Related Skills
