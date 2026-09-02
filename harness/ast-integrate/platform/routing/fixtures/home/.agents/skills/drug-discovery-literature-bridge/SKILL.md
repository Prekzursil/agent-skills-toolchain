---
name: drug-discovery-literature-bridge
description: Use when extracting molecules, targets, assays, and clinical context from a paper (via the Scholarly Access MCP paper_* tools) to seed the drug-discovery stack — ToolUniverse DDI/ADMET/target-validation/mechanism tools and the RDKit MCP — keeping DOI provenance on every extracted entity.
---

# Drug Discovery Literature Bridge

Connects findings in scholarly papers to the drug-discovery toolchain.

## When to use

- You have a DOI, PMID, arXiv id, or title and want to mine its molecules, targets, assays, or clinical context for downstream modeling.
- You want to seed a ToolUniverse query (drug-drug-interaction, ADMET, target validation, drug mechanism) from what a paper actually reports.
- You want to hand a SMILES or compound name from a paper into an RDKit MCP descriptor/property workflow.
- You are building an evidence trail that links a downstream result back to its source DOI.

## The MCP tools it uses

This skill is a consumer of the Scholarly Access MCP. It primarily uses:

- `paper_resolve(identifier)` — DOI/PMID/arXiv/title to canonical metadata, normalized ids (doi, pmid, arxiv, openalex), and a confidence score. Use first to lock the identifier.
- `paper_fetch_metadata(identifier)` — metadata plus abstract plus references where legally available. This is the primary extraction surface.
- `paper_summarize(identifier or doi)` — a structured digest assembled from legally available metadata and abstract. The agent writes the prose; the tool supplies the fields.
- `paper_batch_resolve(identifiers)` — when a reference list or candidate set needs status and OA links in one pass.

Downstream it hands entities to the drug-discovery stack: ToolUniverse skills (for example tooluniverse-drug-drug-interaction, tooluniverse-admet-prediction, tooluniverse-drug-target-validation, tooluniverse-drug-mechanism-research, tooluniverse-pharmacovigilance, tooluniverse-clinical-trial-matching) and the RDKit MCP for molecule descriptors and property calculation.

### Workflow steps
### Concrete examples
### Limitations
### Tested invocation
### -> resolved; title "Why Most Published Research Findings Are False"
### -> subscription / free_to_read_not_redistributable
