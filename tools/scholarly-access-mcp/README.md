# Scholarly Access MCP

A **lawful** scholarly-retrieval MCP server. It resolves DOI / PMID / arXiv / title queries,
classifies access honestly, and routes **only** to legitimate open-access and rights-holder-entitled
sources. It is the compliant replacement for a Sci-Hub MCP.

> **Hard policy (enforced in `policy.py`, not just documented):** no Sci-Hub / LibGen / SciDownl /
> scihub.py / shadow-library / mirror scraping, ever; no paywall bypass; no fake "open access"
> classification; no silent fallback to unauthorized sources. `paper_download_oa_pdf` only fetches a
> URL whose host is on the OA allowlist and whose bytes are a real `%PDF`.

## Tools (spec name → MCP tool name)

| spec | MCP tool | what |
|---|---|---|
| `paper.resolve` | `paper_resolve` | DOI/PMID/arXiv/title → canonical metadata + normalized ids + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata` | + abstract + references (where legally available) |
| `paper.find_oa_pdf` | `paper_find_oa_pdf` | a **legal** OA PDF URL (allowlisted host) + license + evidence |
| `paper.access_status` | `paper_access_status` | `oa_pdf` / `free_to_read_not_redistributable` / `subscription` / `unavailable` / `unknown` |
| `paper.citation_graph` | `paper_citation_graph` | references + citing works from legal metadata APIs |
| `paper.download_oa_pdf` | `paper_download_oa_pdf` | download a legal OA PDF (hard-gated) → path + sha256 + license |
| `paper.summarize` | `paper_summarize` | structured digest from legally-available metadata/abstract |
| `paper.batch_resolve` | `paper_batch_resolve` | resolve a list → table of access status + OA links + unresolved |

> MCP tool names use underscores (not the spec's dots) for client compatibility; the mapping is 1:1.

## Legitimate sources

Crossref · OpenAlex · Unpaywall · Europe PMC · arXiv · Semantic Scholar (keyless) · CORE (keyed) ·
DOAJ · PubMed/NCBI E-utilities · Zenodo · institutional repositories · OA publishers · Elsevier
entitled-fulltext API (only with a valid key). **Access categories** are honest: a paper that is only
*free-to-read* behind a publisher/PMC bot-wall (not in the redistributable OA subset) is classified
`free_to_read_not_redistributable` — cite it, we do **not** circumvent the access control.

## Install & run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m scholarly_access.server   # stdio MCP server
```

## API keys (read by env-var NAME only — never hard-coded, never committed)

`UNPAYWALL_EMAIL` (required for Unpaywall) · `CORE_API_KEY` (CORE) · `NCBI_API_KEY` (raises PubMed
limits) · `SEMANTIC_SCHOLAR_API_KEY` (optional; keyless works) · `ELSEVIER_API_KEY` (entitled fulltext).
Missing key ⇒ that source is skipped, never an error. The server auto-loads `~/.tooluniverse/.env`
(override with `SCHOLARLY_ENV_FILE`); the process environment always wins.

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
.venv/Scripts/python -m pytest tests/test_policy.py -q   # 22 offline policy/gate tests
.venv/Scripts/python tests/test_live.py                  # 10 live end-to-end checks
.venv/Scripts/python list_tools.py                       # prints the 8-tool surface
```

## Limitations

- Title resolution uses a similarity threshold (0.55); a too-vague title may be reported unresolved.
- `free_to_read_not_redistributable` items are intentionally **not** downloaded — open the landing page.
- Citation graph depth depends on Semantic Scholar / OpenAlex coverage for the DOI.
