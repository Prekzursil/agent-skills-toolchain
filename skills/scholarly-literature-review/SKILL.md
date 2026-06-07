---
name: scholarly-literature-review
---

# Scholarly Literature Review

It is the compliant replacement for any Sci-Hub style MCP.

## When to use

- You have a citation, DOI, PMID, arXiv id, or a paper title and want canonical metadata.
- You have a list of identifiers and want a single access-status table across all of them.
- You want to know, per paper, whether the full text is a downloadable open-access PDF, only free-to-read on a publisher or PMC page, behind a subscription, or unavailable.
- You want to explore a paper's references and the works that cite it.
- You want a structured summary built only from legally-available metadata and abstracts.

For a single quick factoid lookup, resolving one identifier may be enough. For broad topical reviews you may layer this with domain-specific ToolUniverse skills.

## The MCP tools it uses

Primary tools for this skill (spec dot-name maps 1:1 to the MCP underscore-name):

- `paper.batch_resolve` -> `paper_batch_resolve(identifiers[])` : resolve a list of identifiers into a table of access status, OA links, metadata, plus any unresolved items.
- `paper.summarize` -> `paper_summarize(identifier|doi)` : structured digest from legally-available metadata and abstract; the agent writes the prose.
- `paper.citation_graph` -> `paper_citation_graph(identifier|doi, limit)` : references and citing works from Semantic Scholar and OpenAlex.

Supporting tools also available on the same server when you need them:

- `paper.resolve` -> `paper_resolve(identifier)` : single identifier to canonical metadata, normalized ids (doi, pmid, arxiv, openalex), and confidence.
- `paper.fetch_metadata` -> `paper_fetch_metadata(identifier)` : metadata plus abstract and references where legally available.

## Access categories (honest)

- `subscription` : paywalled; cite only.
- `unavailable` : no available full text exists.
- `unknown` : access could not be determined.

## Workflow steps

1. Gather the identifiers you have: DOIs, PMIDs, arXiv ids, or titles. Titles use a similarity threshold and a too-vague title may come back unresolved.
2. For a set of papers, call `paper_batch_resolve` to get one consolidated table of metadata, access status, OA links, and unresolved items. For a single paper, use `paper_resolve` or `paper_access_status`.
3. Read the access category per paper.
4. To expand a topic, call `paper_citation_graph` to pull references and citing works, then loop those new identifiers back through `paper_batch_resolve`.
5.

## Concrete examples

- Resolve a landmark methods paper: `paper_resolve("10.1371/journal.pmed.0020124")` returns the resolved record with title "Why Most Published Research Findings Are False".
- Resolve a preprint by arXiv id: `paper_resolve("1706.03762")` returns the arXiv record "Attention Is All You Need".
- Classify an open-access paper: `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS OA url.

## Limitations

- Title resolution uses a similarity threshold of 0.55; a too-vague title may be reported as unresolved.
- `free_to_read_not_redistributable` items are intentionally not downloaded; open the landing page instead.
- Citation graph depth depends on Semantic Scholar and OpenAlex coverage for the given DOI.
- An API key that is missing only causes that one source to be skipped, never an error.

## Tested invocation

```
paper_access_status(doi="10.1371/journal.pone.0000308")
-> category: oa_pdf
-> provenance: PLOS open-access url
```

This is one of the verified live end-to-end checks. The server's test suite covers 22 offline policy/gate tests and 10 live end-to-end checks, and lists 8 tools over MCP stdio.
