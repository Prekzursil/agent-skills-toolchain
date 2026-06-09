---
name: oa-pdf-retrieval
description: Use when downloading an open-access paper PDF with verifiable provenance (allowlisted host, license, sha256) and honest access classification — classify with paper_access_status first, only fetch oa_pdf items via paper_find_oa_pdf then paper_download_oa_pdf, and cite rather than download free-to-read or subscription items.
---

# Open-Access PDF Retrieval

When a paper is only free-to-read (publisher or PMC landing page) or behind a subscription, this skill does NOT download it — it cites the landing page instead. The hard download gate is enforced in server code, not just convention.

## When to use

- You need a verifiable record of where a PDF came from (allowlisted host), under what license, with a sha256 checksum and byte count.
- You need to know, honestly, whether a paper is downloadable open access versus only free-to-read versus paywalled — and act correctly on each category.

## The MCP tools it uses

This skill is backed by the Scholarly Access MCP server (canonical code and README at C:/Users/Prekzursil/source/agent-skills-toolchain/tools/scholarly-access-mcp/). The two primary tools:

Supporting tools you may call first to classify or normalize:

- `paper_access_status(identifier | doi | arxiv)` — category in oa_pdf, free_to_read_not_redistributable, subscription, unavailable, unknown, plus provenance. Use this to decide whether downloading is even appropriate.
- `paper_resolve(identifier)` — normalize a DOI/PMID/arXiv/title to canonical metadata and ids before retrieval.

## The workflow steps

1. Resolve and classify first. Call `paper_access_status` (or `paper_resolve` then status) on the identifier. Read the returned category.
2. Branch on the category honestly:
   - `oa_pdf` — proceed to step 3.
   - `free_to_read_not_redistributable` — STOP. Do NOT download. Cite the landing-page provenance the tool returned. The item is readable on a publisher or PMC page but not legally fetchable.
   - `subscription` — STOP. Do NOT download. Cite the paper only.
3. Find the OA PDF URL. Call `paper_find_oa_pdf` with the DOI or arXiv id. Capture the returned `url`, `license`, and `source`.
4. Download through the gate. Call `paper_download_oa_pdf` with the allowlisted `url`, your chosen `dest_dir` and `filename`, and the `license` and `source` from step 3. Do not hand it a URL from any other origin.
5. Record provenance. From the tool result, record the saved path, sha256, byte count, license, and source.

## Concrete examples

Downloadable open access (arXiv) — full happy path:

- `paper_find_oa_pdf(arxiv="1706.03762")` returns an allowlisted arXiv PDF URL plus license, for "Attention Is All You Need".
- `paper_download_oa_pdf(url=<that arXiv url>, dest_dir=..., filename="attention.pdf", license=..., source="arxiv")` writes roughly a 2.1 MB PDF and returns its sha256.

Downloadable open access (publisher OA):

- `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS open-access URL — safe to find and download.

Correctly NOT downloaded (paywalled / free-to-read):

## Limitations

- `free_to_read_not_redistributable` items are intentionally never downloaded — open or cite the landing page instead.
- A few sources need API keys (read by env-var NAME only). A missing key means that source is silently skipped, never an error: `UNPAYWALL_EMAIL`, `CORE_API_KEY`, `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` (keyless works), `ELSEVIER_API_KEY`.
- A too-vague title may resolve as unresolved; provide a DOI/PMID/arXiv id when possible.

## Tested invocation

```text
# 1. Classify honestly
paper_access_status(doi="10.1371/journal.pone.0000308")
  -> category="oa_pdf", PLOS open-access URL + provenance

# 2.
paper_find_oa_pdf(arxiv="1706.03762")
  -> { url: <allowlisted arXiv PDF url>, license, source, evidence:[...] }

# 3.
paper_download_oa_pdf(url=<that arXiv url>, dest_dir="C:/tmp", filename="attention.pdf",
                      license=<from step 2>, source="arxiv")
  -> { path, sha256, bytes: ~2_100_000, license, source }

```
