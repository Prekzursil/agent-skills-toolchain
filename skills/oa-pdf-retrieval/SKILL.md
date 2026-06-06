---
name: oa-pdf-retrieval
description: Use when you need to find and download a lawful open-access PDF of a paper from an allowlisted source, recording its license, provenance, and sha256 checksum, while correctly refusing to download free-to-read or subscription items and citing those instead.
---

# Open-Access PDF Retrieval

Find and download ONLY lawful open-access PDFs of scholarly papers, recording license + provenance + sha256 checksum for each downloaded file. When a paper is only free-to-read (publisher or PMC landing page) or behind a subscription, this skill does NOT download it — it cites the landing page instead. The hard download gate is enforced in server code, not just convention.

## When to use

- You have a DOI, PMID, arXiv id, or title and want the actual PDF file on disk, lawfully.
- You need a verifiable record of where a PDF came from (allowlisted host), under what license, with a sha256 checksum and byte count.
- You need to know, honestly, whether a paper is downloadable open access versus only free-to-read versus paywalled — and act correctly on each category.

Do NOT use this skill to bypass a paywall, scrape a mirror, or fetch from any shadow library. Those are hard-refused.

## The MCP tools it uses

This skill is backed by the Scholarly Access MCP server (canonical code and README at C:/Users/Prekzursil/source/agent-skills-toolchain/tools/scholarly-access-mcp/). The two primary tools:

- `paper_find_oa_pdf(identifier | doi | arxiv)` — returns a LEGAL open-access PDF URL whose host is on the OA allowlist, plus the license and per-candidate evidence (including any DENIED shadow-library URL it considered and rejected).
- `paper_download_oa_pdf(url, dest_dir, filename, license, source)` — the HARD-GATED download. It only writes a file when the URL host is on the OA allowlist AND the response bytes begin with a real %PDF marker. It returns the saved path, sha256, byte count, and the license/source you recorded. It refuses (raises PermissionError) on any pirate or off-allowlist URL, and refuses non-PDF bytes.

Supporting tools you may call first to classify or normalize:

- `paper_access_status(identifier | doi | arxiv)` — category in oa_pdf, free_to_read_not_redistributable, subscription, unavailable, unknown, plus provenance. Use this to decide whether downloading is even appropriate.
- `paper_resolve(identifier)` — normalize a DOI/PMID/arXiv/title to canonical metadata and ids before retrieval.

## The workflow steps

1. Resolve and classify first. Call `paper_access_status` (or `paper_resolve` then status) on the identifier. Read the returned category.
2. Branch on the category honestly:
   - `oa_pdf` — proceed to step 3.
   - `free_to_read_not_redistributable` — STOP. Do NOT download. Cite the landing-page provenance the tool returned. The item is readable on a publisher or PMC page but not legally fetchable.
   - `subscription` — STOP. Do NOT download. Cite the paper only.
   - `unavailable` or `unknown` — STOP. Report that no lawful full text was found; do not guess at a URL.
3. Find the OA PDF URL. Call `paper_find_oa_pdf` with the DOI or arXiv id. Capture the returned `url`, `license`, and `source`. Inspect the per-candidate evidence; if a shadow-library URL appears, confirm it is marked DENIED (it will be) and never pass it onward.
4. Download through the gate. Call `paper_download_oa_pdf` with the allowlisted `url`, your chosen `dest_dir` and `filename`, and the `license` and `source` from step 3. Do not hand it a URL from any other origin.
5. Record provenance. From the tool result, record the saved path, sha256, byte count, license, and source. These constitute the lawful provenance record for the downloaded PDF.

## Concrete examples

Downloadable open access (arXiv) — full happy path:

- `paper_find_oa_pdf(arxiv="1706.03762")` returns an allowlisted arXiv PDF URL plus license, for "Attention Is All You Need".
- `paper_download_oa_pdf(url=<that arXiv url>, dest_dir=..., filename="attention.pdf", license=..., source="arxiv")` writes roughly a 2.1 MB PDF and returns its sha256.

Downloadable open access (publisher OA):

- `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS open-access URL — safe to find and download.

Correctly NOT downloaded (paywalled / free-to-read):

- `paper_access_status(doi="10.1056/NEJMoa2034577")` returns `subscription` (or `free_to_read_not_redistributable`). The skill does NOT download it and does NOT attempt any bypass — it cites the paper only.

Hard gate proven:

- `paper_download_oa_pdf("https://sci-hub.se/...")` is REFUSED with a PermissionError. The lawful gate rejects shadow-library and off-allowlist URLs even if you pass one by mistake.

## Limitations

- Only PDFs whose host is on the OA allowlist and whose bytes are a real %PDF will download. Everything else is refused by design.
- `free_to_read_not_redistributable` items are intentionally never downloaded — open or cite the landing page instead.
- A few sources need API keys (read by env-var NAME only). A missing key means that source is silently skipped, never an error: `UNPAYWALL_EMAIL`, `CORE_API_KEY`, `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` (keyless works), `ELSEVIER_API_KEY`.
- A too-vague title may resolve as unresolved; provide a DOI/PMID/arXiv id when possible.

## Safety / access policy

This skill enforces a HARD policy that lives in the server's `policy.py`, not merely in this document:

- NO Sci-Hub, LibGen, SciDownl, scihub.py, any shadow library, or mirror scraping — ever.
- NO paywall bypass and NO circumvention of any access control.
- NO fake "open access" classification; access categories are reported honestly.
- NO silent fallback to unauthorized sources.
- `paper_download_oa_pdf` ONLY fetches a URL whose host is on the OA allowlist AND whose bytes are a real %PDF; it refuses pirate, off-allowlist, or non-PDF responses.

Legitimate sources only: Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless), CORE (keyed), DOAJ, PubMed/NCBI E-utilities, Zenodo, institutional repositories, OA publishers, and the Elsevier entitled-fulltext API (valid key only). For anything classified as free-to-read or subscription, cite the source — do not circumvent.

## Tested invocation

```text
# 1. Classify honestly
paper_access_status(doi="10.1371/journal.pone.0000308")
  -> category="oa_pdf", PLOS open-access URL + provenance

# 2. Find the lawful OA PDF URL (arXiv worked example)
paper_find_oa_pdf(arxiv="1706.03762")
  -> { url: <allowlisted arXiv PDF url>, license, source, evidence:[...] }

# 3. Download through the hard gate
paper_download_oa_pdf(url=<that arXiv url>, dest_dir="C:/tmp", filename="attention.pdf",
                      license=<from step 2>, source="arxiv")
  -> { path, sha256, bytes: ~2_100_000, license, source }

# Gate proof (must refuse):
paper_download_oa_pdf("https://sci-hub.se/...") -> PermissionError (REFUSED)
```
