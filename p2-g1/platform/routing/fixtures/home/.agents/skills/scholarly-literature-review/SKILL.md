---
name: scholarly-literature-review
description: Use when given DOIs, PMIDs, arXiv ids, or paper titles and needing canonical metadata, access-status tables, citation/reference expansion, or structured summaries from legally available abstracts via Scholarly Access MCP ; do NOT use for biomedical evidence ranking (use biomedical-paper-triage) or PDF downloading (use oa-pdf-retrieval) ; returns metadata, access classification, and citation graph.
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

### Access categories (honest)
### Workflow steps
### Concrete examples
### Limitations
### Tested invocation
