---
name: protein-interaction-network-analysis
description: "Use when analyzing protein interaction networks, confidence scores, functional enrichment, or structural context with STRING, BioGRID, and SASBDB."
---

# Protein Interaction Network Analysis

Comprehensive protein interaction network analysis using ToolUniverse tools. Analyzes protein networks through a 4-phase workflow: identifier mapping, network retrieval, enrichment analysis, and optional structural data.

## Domain Reasoning: Interaction Type Clarification

When asked about protein interactions, ask: physical interaction (do they bind?) or functional interaction (do they affect the same pathway)? STRING combines both — a high combined_score does not mean physical binding. For physical binding evidence, check the experimental score (`escore`) specifically. A high `tscore` (text mining) or `dscore` (database) with a low `escore` suggests co-annotation or co-citation, not direct binding.

LOOK UP DON'T GUESS: protein interaction scores, experimental evidence types, and whether two specific proteins have known co-crystal structures. Use STRING `escore` and BioGRID experimental data — do not infer binding from pathway co-membership alone.

## Databases Used

| Database | Coverage | API Key | Purpose |
|----------|----------|---------|---------|
| **STRING** | 14M+ proteins, 5,000+ organisms | Not required | Primary interaction source |
| **BioGRID** | 2.3M+ interactions, 80+ organisms | Required | Fallback, curated data |
| **SASBDB** | 2,000+ SAXS/SANS entries | Not required | Solution structures |

## 4-Phase Workflow

1. **Identifier Mapping** — `STRING_map_identifiers()`: validate protein names, get STRING IDs
2. **Network Retrieval** — `STRING_get_network()` (primary); `BioGRID_get_interactions()` (fallback, requires API key)

### Parameters
### Confidence Score Guidelines
### Network Edge Fields (STRING)
### Extended Analysis Tools
### Tool-Specific Notes
### IntAct Interaction Data
### BioGRID Chemical Interactions
### IntAct `protein_name` Alias
### Domain Reasoning: Multimeric Assemblies & Binding Valency
### Calculating Multimer Valency from Binding Data
