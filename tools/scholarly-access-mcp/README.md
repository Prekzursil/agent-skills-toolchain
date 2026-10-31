---
title: README
type: note
permalink: dqverify-repo-20261013/tools/scholarly-access-mcp/readme
---

# Scholarly Access MCP

A comprehensive scholarly-retrieval MCP server. It resolves DOI / PMID / arXiv / title queries
and routes to **every available source** for maximum PDF coverage.

## Sources

OA: Crossref · OpenAlex · Unpaywall · Europe PMC · arXiv · Semantic Scholar · CORE · DOAJ ·
PubMed/NCBI E-utilities · Zenodo

Extended: Sci-Hub (mirror failover) · LibGen (mirror failover) · SciDownl-style direct DOI fetch ·
Publisher page scraping

## Tools (spec name → MCP tool name)

| spec | MCP tool | what |
|---|---|---|
| `paper.resolve` | `paper_resolve` | DOI/PMID/arXiv/title → canonical metadata + normalized ids + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata` | + abstract + references |
| `paper.find_oa_pdf` | `paper_find_oa_pdf` | PDF URL from any source (OA, Sci-Hub, LibGen, publisher page) |
| `paper.access_status` | `paper_access_status` | `oa_pdf` / `free_to_read_not_redistributable` / `subscription` / `unavailable` / `unknown` |
| `paper.citation_graph` | `paper_citation_graph` | references + citing works from metadata APIs |
| `paper.download_oa_pdf` | `paper_download_oa_pdf` | download a PDF from any URL → path + sha256 |
| `paper.summarize` | `paper_summarize` | structured digest from available metadata/abstract |
| `paper.batch_resolve` | `paper_batch_resolve` | resolve a list → table of access status + PDF links |

## Install & run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m scholarly_access.server   # stdio MCP server
```

## API keys (env-var NAME only)

`UNPAYWALL_EMAIL` (required for Unpaywall) · `CORE_API_KEY` (CORE) · `NCBI_API_KEY` (raises PubMed
limits) · `SEMANTIC_SCHOLAR_API_KEY` (optional) · `SCIHUB_MIRROR` (override default mirror) ·
`LIBGEN_MIRROR` (override default mirror).
Missing key ⇒ that source is skipped. The server auto-loads `~/.tooluniverse/.env`.

## MCP client registration

```json
"scholarly-access": {
  "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\scholarly-access-mcp\\.venv\\Scripts\\python.exe",
  "args": ["-m", "scholarly_access.server"],
  "env": {}
}
```

## Tests

```bash
.venv/Scripts/python -m pytest tests/test_policy.py -q
.venv/Scripts/python tests/test_live.py
.venv/Scripts/python list_tools.py
```