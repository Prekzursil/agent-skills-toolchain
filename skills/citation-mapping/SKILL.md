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
2. Call `paper_citation_graph(doi=..., limit=N)` on the seed. This returns two edge sets: references (backward) and citing works (forward).
3. Read off the backward map (what the seed cites) and the forward map (what cites the seed). Note that depth and completeness depend on API coverage — neither Semantic Scholar nor OpenAlex is exhaustive, and some neighbors may lack ids.
4. (Optional) To go one hop deeper, pick the most relevant neighbors and call `paper_citation_graph` on each, or `paper_batch_resolve([...])` to enrich a batch of neighbor ids with metadata and access status.
5. Present the map. Group by direction (references vs cited-by), and where useful flag the high-degree or repeatedly-appearing nodes as likely-influential. State coverage caveats explicitly.

## Concrete examples

- Resolve a seed paper:
  `paper_resolve("10.1371/journal.pmed.0020124")` resolves to the title "Why Most Published Research Findings Are False".
- Resolve an arXiv seed:
  `paper_resolve("1706.03762")` resolves to the arXiv paper "Attention Is All You Need".
- Build the graph around a seed:
  `paper_citation_graph(doi="10.1371/journal.pmed.0020124", limit=50)` returns the references (backward) and citing works (forward) for that paper from Semantic Scholar / OpenAlex.
- Enrich neighbors in one call:
  `paper_batch_resolve(["10.1371/journal.pone.0000308", "1706.03762"])` returns a table of access status, OA links, and metadata for the listed neighbors, plus any unresolved items.

## Limitations

- Metadata-only: this skill never fetches full text or PDFs. It maps the citation graph from APIs.
- Coverage-bound: reference and cited-by completeness depend entirely on Semantic Scholar and OpenAlex coverage. Older works, non-indexed venues, and very recent papers may have sparse or missing edges.
- Depth is shallow by default: a single `paper_citation_graph` call gives one hop in each direction. Deeper maps require repeated calls and grow quickly.
- Some neighbors lack normalized ids and cannot be enriched or further expanded.

## Tested invocation

```
paper_resolve("10.1371/journal.pmed.0020124")
  -> resolved, title "Why Most Published Research Findings Are False"

paper_citation_graph(doi="10.1371/journal.pmed.0020124", limit=50)
  -> references (backward edges) + citing works (forward edges)
     from Semantic Scholar / OpenAlex
```
