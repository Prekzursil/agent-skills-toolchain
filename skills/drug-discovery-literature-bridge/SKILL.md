---
name: drug-discovery-literature-bridge
description: Use when a paper or DOI should feed the drug-discovery stack and you need to pull molecules, targets, assays, DDI-ADMET-CYP, and clinical context from lawful literature metadata and hand them to ToolUniverse and RDKit MCP workflows
---

# Drug Discovery Literature Bridge

Connects findings in scholarly papers to the drug-discovery toolchain. It resolves an identifier through the lawful Scholarly Access MCP, extracts structured biomedical entities from the legally available metadata and abstract, and routes those entities (molecules, targets, assays, DDI/ADMET/CYP signals, clinical context, DOIs) into ToolUniverse and RDKit MCP workflows. No paywall content is ever circumvented; the bridge works only from metadata that the lawful server returns honestly.

## When to use

- You have a DOI, PMID, arXiv id, or title and want to mine its molecules, targets, assays, or clinical context for downstream modeling.
- You want to seed a ToolUniverse query (drug-drug-interaction, ADMET, target validation, drug mechanism) from what a paper actually reports.
- You want to hand a SMILES or compound name from a paper into an RDKit MCP descriptor/property workflow.
- You are building an evidence trail that links a downstream result back to its source DOI.

## The MCP tools it uses

This skill is a consumer of the Scholarly Access MCP. It primarily uses:

- `paper_resolve(identifier)` — DOI/PMID/arXiv/title to canonical metadata, normalized ids (doi, pmid, arxiv, openalex), and a confidence score. Use first to lock the identifier.
- `paper_fetch_metadata(identifier)` — metadata plus abstract plus references where legally available. This is the primary extraction surface.
- `paper_summarize(identifier or doi)` — a structured digest assembled from legally available metadata and abstract. The agent writes the prose; the tool supplies the legal fields.
- `paper_access_status(identifier or doi or arxiv)` — confirms whether full text is lawfully reachable before you over-promise depth (`oa_pdf`, `free_to_read_not_redistributable`, `subscription`, `unavailable`, `unknown`).
- `paper_batch_resolve(identifiers)` — when a reference list or candidate set needs status and OA links in one pass.

Downstream it hands entities to the drug-discovery stack: ToolUniverse skills (for example tooluniverse-drug-drug-interaction, tooluniverse-admet-prediction, tooluniverse-drug-target-validation, tooluniverse-drug-mechanism-research, tooluniverse-pharmacovigilance, tooluniverse-clinical-trial-matching) and the RDKit MCP for molecule descriptors and property calculation.

## Workflow steps

1. Resolve and confirm. Call `paper_resolve` on the identifier; record the canonical DOI and confidence. If a title resolves below confidence or comes back unresolved, ask for a DOI or arXiv id rather than guessing.
2. Check lawful reach. Call `paper_access_status` so you know how deep the legal text goes. If the category is `subscription` or `free_to_read_not_redistributable`, work only from the abstract and metadata and cite the landing page — never attempt a bypass.
3. Pull legal metadata. Call `paper_fetch_metadata` (and optionally `paper_summarize`) to get the title, abstract, authors, and references that are legally available.
4. Extract entities from the returned text only. Identify, from the abstract/metadata: molecules and any SMILES or compound names, protein/gene targets, assay types and readouts, DDI / ADMET / CYP signals (for example CYP3A4 inhibition, hepatotoxicity flags), and clinical context (indication, phase, population). Tag every extracted entity with the source DOI.
5. Route into the stack:
   - Targets and indications go to ToolUniverse target-validation, drug-mechanism, or gene-disease association tools.
   - Compound names / SMILES go to the RDKit MCP for descriptors and properties, and to ToolUniverse chemical-compound retrieval.
   - DDI / ADMET / CYP signals go to ToolUniverse drug-drug-interaction, admet-prediction, and pharmacovigilance tools.
   - Clinical context goes to ToolUniverse clinical-trial-matching or clinical-data-integration tools.
6. Preserve provenance. Carry the source DOI and the access category through every downstream call so any result can be traced back to lawfully obtained literature.

## Concrete examples

- Resolve a landmark methods paper before extraction: `paper_resolve("10.1371/journal.pmed.0020124")` resolves to "Why Most Published Research Findings Are False" — use the canonical DOI it returns as the provenance tag on every extracted entity.
- Confirm an open-access target before promising full-text depth: `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS OA URL, so the full text is lawfully available for entity extraction; pull it with `paper_fetch_metadata` and feed targets to tooluniverse-drug-target-validation.
- Respect a paywalled clinical paper: `paper_access_status(doi="10.1056/NEJMoa2034577")` returns subscription / free_to_read_not_redistributable — it is NOT downloaded and there is no bypass, so extract clinical context from the abstract only and cite the publisher landing page before handing the indication to tooluniverse-clinical-trial-matching.
- Resolve an arXiv preprint for a chemistry/ML method: `paper_resolve("1706.03762")` returns the arXiv record "Attention Is All You Need"; use `paper_find_oa_pdf(arxiv="1706.03762")` then `paper_download_oa_pdf(url)` only when a local copy of the lawful OA PDF (about 2.1 MB, with sha256) is genuinely needed.

## Limitations

- Extraction depth is bounded by what the lawful server returns. When access is `subscription` or `free_to_read_not_redistributable`, you have only the abstract and metadata; do not infer full-text detail you cannot read.
- A too-vague title may resolve below the similarity threshold and come back unresolved — supply a DOI or arXiv id in that case.
- The bridge does not parse PDFs for chemistry on its own; SMILES and structures come from the metadata/abstract text or from a lawfully downloaded OA PDF that you then process with chemistry tools.
- Citation-graph and reference coverage depend on the upstream metadata APIs and may be incomplete for a given DOI.

## Safety / access policy

Hard policy, enforced in the server's `policy.py` and not merely documented: no Sci-Hub, LibGen, SciDownl, scihub.py, shadow-library, or mirror scraping, ever; no paywall bypass; no fake "open access" classification; no silent fallback to unauthorized sources. `paper_download_oa_pdf` only fetches a URL whose host is on the OA allowlist and whose bytes are a real `%PDF`; a pirate, off-allowlist, or non-PDF URL is refused. This bridge consumes only lawful sources — Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless), CORE (keyed), DOAJ, PubMed/NCBI E-utilities, Zenodo, institutional repositories, OA publishers, and the Elsevier entitled-fulltext API with a valid key. Access categories are honest: `oa_pdf` is downloadable OA; `free_to_read_not_redistributable` is readable on a publisher/PMC page but not legally fetchable (cite, do not circumvent); `subscription` is paywalled (cite only); `unavailable` means no legitimate full text; `unknown` means it could not be determined. API keys are read by env-var NAME only (UNPAYWALL_EMAIL, CORE_API_KEY, NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY, ELSEVIER_API_KEY) and never hard-coded.

## Tested invocation

```
paper_resolve("10.1371/journal.pmed.0020124")
# -> resolved; title "Why Most Published Research Findings Are False"

paper_access_status(doi="10.1371/journal.pone.0000308")
# -> oa_pdf, PLOS OA url  (lawful full text available for extraction)

paper_access_status(doi="10.1056/NEJMoa2034577")
# -> subscription / free_to_read_not_redistributable
#    (NOT downloaded, no bypass — extract from abstract + cite landing page)
```
