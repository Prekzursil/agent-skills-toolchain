---
name: drug-discovery-literature-bridge
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

## Workflow steps

1. Resolve and confirm. Call `paper_resolve` on the identifier; record the canonical DOI and confidence. If a title resolves below confidence or comes back unresolved, ask for a DOI or arXiv id rather than guessing.
2. Call `paper_access_status` so you know how deep the text goes.
3. Pull metadata. Call `paper_fetch_metadata` (and optionally `paper_summarize`) to get the title, abstract, authors, and references that are legally available.
4. Extract entities from the returned text only. Identify, from the abstract/metadata: molecules and any SMILES or compound names, protein/gene targets, assay types and readouts, DDI / ADMET / CYP signals (for example CYP3A4 inhibition, hepatotoxicity flags), and clinical context (indication, phase, population). Tag every extracted entity with the source DOI.
5. Route into the stack:
   - Targets and indications go to ToolUniverse target-validation, drug-mechanism, or gene-disease association tools.
   - Compound names / SMILES go to the RDKit MCP for descriptors and properties, and to ToolUniverse chemical-compound retrieval.
   - DDI / ADMET / CYP signals go to ToolUniverse drug-drug-interaction, admet-prediction, and pharmacovigilance tools.
   - Clinical context goes to ToolUniverse clinical-trial-matching or clinical-data-integration tools.
6. Preserve provenance.

## Concrete examples

- Resolve a landmark methods paper before extraction: `paper_resolve("10.1371/journal.pmed.0020124")` resolves to "Why Most Published Research Findings Are False" — use the canonical DOI it returns as the provenance tag on every extracted entity.

## Limitations

- A too-vague title may resolve below the similarity threshold and come back unresolved — supply a DOI or arXiv id in that case.
- Citation-graph and reference coverage depend on the upstream metadata APIs and may be incomplete for a given DOI.

## Tested invocation

```
paper_resolve("10.1371/journal.pmed.0020124")
# -> resolved; title "Why Most Published Research Findings Are False"

paper_access_status(doi="10.1371/journal.pone.0000308")

paper_access_status(doi="10.1056/NEJMoa2034577")
# -> subscription / free_to_read_not_redistributable
```
