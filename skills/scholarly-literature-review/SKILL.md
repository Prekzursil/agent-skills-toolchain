---
name: scholarly-literature-review
description: Use when you need to find academic papers across OpenAlex Semantic Scholar Crossref PubMed arXiv and Unpaywall, classify lawful access for each paper, trace citation graphs, and summarize legally-available content as the general literature-search entry point.
---

# Scholarly Literature Review

The general-purpose entry point for lawful academic literature work. Use this skill to find papers by DOI, PMID, arXiv id, or title across the major scholarly metadata sources; to honestly classify whether each paper's full text is lawfully accessible; to walk references and citing works; and to produce structured digests from legally-available metadata and abstracts.

It is backed by the **Scholarly Access MCP**, a lawful retrieval server whose hard policy is enforced in code (`policy.py`), not merely documented. It is the compliant replacement for any Sci-Hub style MCP.

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
- `paper.access_status` -> `paper_access_status(identifier|doi|arxiv)` : classify lawful access for one paper, with provenance.
- `paper.summarize` -> `paper_summarize(identifier|doi)` : structured digest from legally-available metadata and abstract; the agent writes the prose.
- `paper.citation_graph` -> `paper_citation_graph(identifier|doi, limit)` : references and citing works from Semantic Scholar and OpenAlex.

Supporting tools also available on the same server when you need them:

- `paper.resolve` -> `paper_resolve(identifier)` : single identifier to canonical metadata, normalized ids (doi, pmid, arxiv, openalex), and confidence.
- `paper.fetch_metadata` -> `paper_fetch_metadata(identifier)` : metadata plus abstract and references where legally available.
- `paper.find_oa_pdf` -> `paper_find_oa_pdf(identifier|doi|arxiv)` : a legal OA PDF url on an allowlisted host, with license and per-candidate evidence including any denied shadow url.
- `paper.download_oa_pdf` -> `paper_download_oa_pdf(url, dest_dir, filename, license, source)` : hard-gated download that refuses anything off-allowlist, pirate, or non-PDF.

## Access categories (honest)

- `oa_pdf` : a lawfully downloadable open-access PDF at a legitimate source.
- `free_to_read_not_redistributable` : readable on a publisher or PMC landing page but not lawfully fetchable; cite it and open the landing page, do not circumvent the access control.
- `subscription` : paywalled; cite only.
- `unavailable` : no legitimate full text exists.
- `unknown` : access could not be determined.

## Workflow steps

1. Gather the identifiers you have: DOIs, PMIDs, arXiv ids, or titles. Titles use a similarity threshold and a too-vague title may come back unresolved.
2. For a set of papers, call `paper_batch_resolve` to get one consolidated table of metadata, access status, OA links, and unresolved items. For a single paper, use `paper_resolve` or `paper_access_status`.
3. Read the access category per paper. For `oa_pdf` you may proceed to a lawful download via `paper_find_oa_pdf` then `paper_download_oa_pdf`. For `free_to_read_not_redistributable`, `subscription`, or `unavailable`, cite the paper and stop; never attempt a bypass.
4. To expand a topic, call `paper_citation_graph` to pull references and citing works, then loop those new identifiers back through `paper_batch_resolve`.
5. For each paper you can lawfully read, call `paper_summarize` to get a structured digest, then write the synthesis prose yourself with proper citations.

## Concrete examples

- Resolve a landmark methods paper: `paper_resolve("10.1371/journal.pmed.0020124")` returns the resolved record with title "Why Most Published Research Findings Are False".
- Resolve a preprint by arXiv id: `paper_resolve("1706.03762")` returns the arXiv record "Attention Is All You Need".
- Classify an open-access paper: `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS OA url.
- Classify a paywalled paper honestly: `paper_access_status(doi="10.1056/NEJMoa2034577")` returns `subscription` or `free_to_read_not_redistributable`; it is not downloaded and there is no bypass.
- Lawful download path: `paper_find_oa_pdf(arxiv="1706.03762")` then `paper_download_oa_pdf(url=...)` yields roughly a 2.1MB PDF with a sha256.
- The lawful gate proves itself: `paper_download_oa_pdf("https://sci-hub.se/...")` is refused with a PermissionError.

## Limitations

- Title resolution uses a similarity threshold of 0.55; a too-vague title may be reported as unresolved.
- `free_to_read_not_redistributable` items are intentionally not downloaded; open the landing page instead.
- Citation graph depth depends on Semantic Scholar and OpenAlex coverage for the given DOI.
- An API key that is missing only causes that one source to be skipped, never an error.

## Safety / access policy

This skill enforces a hard, code-level lawful-access policy (`policy.py`):

- No Sci-Hub, LibGen, SciDownl, scihub.py, shadow library, or mirror scraping, ever.
- No paywall bypass and no circumvention of any access control.
- No fake "open access" classification; access categories are reported honestly.
- No silent fallback to unauthorized sources.
- `paper_download_oa_pdf` only fetches a url whose host is on the OA allowlist and whose bytes are a real `%PDF`; anything else is refused.

Legitimate sources only: Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless), CORE (keyed), DOAJ, PubMed/NCBI E-utilities, Zenodo, institutional repositories, OA publishers, and the Elsevier entitled-fulltext API with a valid key. API keys are read by env-var name only (UNPAYWALL_EMAIL, CORE_API_KEY, NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY, ELSEVIER_API_KEY); the server auto-loads `~/.tooluniverse/.env` and the process environment always wins. Keys are never hard-coded or committed.

## Tested invocation

```
paper_access_status(doi="10.1371/journal.pone.0000308")
-> category: oa_pdf
-> provenance: PLOS open-access url
```

This is one of the verified live end-to-end checks. The server's test suite covers 22 offline policy/gate tests and 10 live end-to-end checks, and lists 8 tools over MCP stdio.
