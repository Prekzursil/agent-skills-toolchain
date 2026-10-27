---
name: citation-mapping
description: Use when you need to build a citation or reference map for a paper, tracing backward references and forward cited-by works from metadata APIs like Semantic Scholar and OpenAlex
---

# Citation Mapping

This skill traces both directions of a paper's citation network — backward (the references it cites) and forward (the works that cite it) — from Semantic Scholar and OpenAlex via the Scholarly Access MCP. It is metadata-only: it maps the graph, it does not retrieve full text.

## When to use

- You want to see what a paper cites (its reference list / backward edges).
- You want to see who cites a paper (its citing works / forward "cited-by" edges).
- You want to expand outward from a seed paper to build a small literature network.
- You want to identify influential or highly-connected works around a topic before doing a full review.

Do NOT use this skill to fetch PDFs or full text — use the OA-PDF tools of the Scholarly Access MCP for that. This skill stops at the metadata graph.

## The MCP tools it uses

The tools it relies on:

- `paper_resolve(identifier)` — resolve a DOI, PMID, arXiv id, or title to canonical metadata and normalized ids (doi, pmid, arxiv, openalex) with a confidence score. Use this first to pin down the seed paper.
- `paper_citation_graph(identifier|doi, limit)` — return the references and citing works for a paper, sourced from Semantic Scholar and OpenAlex. This is the core tool of the skill.
- `paper_batch_resolve(identifiers[])` — optional, to enrich a list of neighbor ids (references or citing works) with metadata and access status in one call.

## Workflow steps

1. Resolve the seed paper with `paper_resolve(identifier)`. Confirm the title and confidence look right; capture the normalized ids (prefer the DOI or OpenAlex id for the next step).

### Concrete examples
### Limitations
### Tested invocation
