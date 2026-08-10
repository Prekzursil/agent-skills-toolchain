---
name: biomedical-paper-triage
description: Use when turning a raw list of biomedical papers into a ranked, access-tagged shortlist graded T1-T4 by human/animal/in-vitro evidence strength via Scholarly Access MCP ; do NOT use for generic literature metadata or citation graphs (use scholarly-literature-review) ; returns defensible ranked shortlist with evidence grades.
---

# Biomedical Paper Triage

Turn a raw list of biomedical papers (DOIs, PMIDs, arXiv ids, or titles) into a defensible, ranked shortlist. Pairs with the `consensus-tooluniverse-research` evidence-grading scheme (T1-T4 x human / animal / in-vitro) so the shortlist carries both a triage rank and an evidence tier.

## When to use

- You ran a search (PubMed, Consensus, a colleague's bibliography) and got back 20-200 candidate papers and need to decide which 10-20 to actually read.
- You must justify inclusion/exclusion for a mini-review or grant background and want recency, study-type, citation-signal, and access reasons recorded per paper.
- You want to avoid wasting time queuing papers that turn out to be paywalled, retracted, or non-redistributable.
- You need an access-honest list to hand to the `consensus-tooluniverse-research` workflow for evidence grading and download.

## The MCP tools it uses

It primarily uses three tools (spec dot-name -> MCP underscore-name):

- `paper.batch_resolve` -> `paper_batch_resolve(identifiers[])` : resolve a whole list at once into a table of canonical metadata, normalized ids (doi, pmid, arxiv, openalex), access status, OA links, and a list of unresolved items. This is the workhorse for the first pass.
- `paper.access_status` -> `paper_access_status(identifier|doi|arxiv)` : confirm or refine the honest access category for a single paper when the batch result is `unknown` or you need provenance.
- `paper.citation_graph` -> `paper_citation_graph(identifier|doi, limit)` : pull references and citing works from Semantic Scholar / OpenAlex to derive a citation signal and to discover high-impact neighbors worth adding to the pool.

### Access categories (honest)
### Workflow steps
### Concrete examples
### Limitations
### Tested invocation
### -> table: each id resolved with canonical title, normalized ids, and access status
### -> { category: "oa_pdf", oa_url: "<PLOS OA url>", provenance: ... }
### -> references + citing works for the citation-signal axis
