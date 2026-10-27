---
name: oa-pdf-retrieval
description: Use when downloading an open-access paper PDF with verified provenance (allowlisted host, license, sha256) via paper_find_oa_pdf and paper_download_oa_pdf ; do NOT use for mere metadata lookup or citation graphs (use scholarly-literature-review), or for biomedical ranking (use biomedical-paper-triage) ; returns downloaded PDF path with access classification.
---

# Open-Access PDF Retrieval

When a paper is only free-to-read (publisher or PMC landing page) or behind a subscription, this skill does NOT download it — it cites the landing page instead. The hard download gate is enforced in server code, not just convention.

## When to use

- You need a verifiable record of where a PDF came from (allowlisted host), under what license, with a sha256 checksum and byte count.
- You need to know, honestly, whether a paper is downloadable open access versus only free-to-read versus paywalled — and act correctly on each category.

## The MCP tools it uses

This skill is backed by the Scholarly Access MCP server (canonical code and README at C:/Users/agentuser/source/agent-skills-toolchain/tools/scholarly-access-mcp/). The two primary tools:

Supporting tools you may call first to classify or normalize:

- `paper_access_status(identifier | doi | arxiv)` — category in oa_pdf, free_to_read_not_redistributable, subscription, unavailable, unknown, plus provenance. Use this to decide whether downloading is even appropriate.
- `paper_resolve(identifier)` — normalize a DOI/PMID/arXiv/title to canonical metadata and ids before retrieval.

## The workflow steps

1. Resolve and classify first. Call `paper_access_status` (or `paper_resolve` then status) on the identifier. Read the returned category.
2. Branch on the category honestly:
   - `oa_pdf` — proceed to step 3.
   - `free_to_read_not_redistributable` — STOP. Do NOT download. Cite the landing-page provenance the tool returned. The item is readable on a publisher or PMC page but not legally fetchable.

### Concrete examples
### Limitations
### Tested invocation
### 1. Classify honestly
