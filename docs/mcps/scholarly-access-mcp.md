# Scholarly Access MCP

A lawful scholarly-retrieval MCP server. It resolves DOI / PMID / arXiv / title queries, classifies access honestly, and routes only to legitimate open-access and rights-holder-entitled sources. It is the compliant replacement for a Sci-Hub MCP.

The canonical reference for this server is `tools/scholarly-access-mcp/README.md`. This document is a docs-mirror overview; when in doubt, the README wins.

## Purpose

Researchers and agents need to find, classify, and (where legal) download the full text of academic papers. Shadow-library MCPs (Sci-Hub, LibGen, and friends) do this by circumventing access controls — which is unlawful. This server provides the same useful surface (resolve → classify → find OA → download) while refusing, by design, to touch any unauthorized source. Every access decision is reported honestly: a paper that is only readable behind a publisher bot-wall is labeled as such and is never silently "downloaded" by circumvention.

## Architecture

The server is a small, layered Python package:

- **`policy.py`** — the guardrails. Enforces the hard policy in code (not just docs): an OA allowlist of permitted hosts, a denylist of shadow-library / mirror hosts, and a download hard-gate that requires both an allowlisted host and real `%PDF` bytes. Refusals raise `PermissionError`.
- **`sources.py`** — the source clients. Thin clients for each legitimate provider (Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar, CORE, DOAJ, PubMed/NCBI E-utilities, Zenodo, Elsevier entitled-fulltext). A missing API key means that source is skipped, never an error.
- **`logic.py`** — the orchestration. Normalizes identifiers, fans out to the source clients, merges/deduplicates results, computes confidence and the honest access category, and assembles per-candidate evidence (including any DENIED shadow URL that was seen and rejected).
- **`server.py`** — the FastMCP stdio entry point. Exposes the 8 tools over MCP stdio. Run as `python -m scholarly_access.server`.

## Legal access model

Access is classified into 5 honest categories:

| category | meaning |
|---|---|
| `oa_pdf` | downloadable open-access PDF at a legitimate source |
| `free_to_read_not_redistributable` | readable on a publisher/PMC landing page but not legally fetchable — cite it, do NOT circumvent |
| `subscription` | paywalled — cite only |
| `unavailable` | no legitimate full text exists |
| `unknown` | access could not be determined |

The download path is **hard-gated**. `paper_download_oa_pdf` only writes a file when the URL host is on the OA **allowlist** AND the fetched bytes are a real `%PDF`. Hosts on the shadow-library **denylist** (Sci-Hub / LibGen / SciDownl / scihub.py / mirrors) are refused with `PermissionError` before any network call. There is no silent fallback to an unauthorized source, no paywall bypass, and no fake "open access" classification.

## Supported sources

Crossref · OpenAlex · Unpaywall · Europe PMC · arXiv · Semantic Scholar (keyless) · CORE (keyed) · DOAJ · PubMed/NCBI E-utilities · Zenodo · institutional repositories · OA publishers · Elsevier entitled-fulltext API (only with a valid key).

## The 8 tools (spec dot-name → MCP underscore-name)

MCP tool names use underscores instead of the spec's dots for client compatibility; the mapping is 1:1.

| spec | MCP tool | what it does |
|---|---|---|
| `paper.resolve` | `paper_resolve(identifier)` | DOI/PMID/arXiv/title → canonical metadata + normalized ids (doi, pmid, arxiv, openalex) + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata(identifier)` | resolve + abstract + references (where legally available) |
| `paper.find_oa_pdf` | `paper_find_oa_pdf(identifier\|doi\|arxiv)` | a legal OA PDF URL (allowlisted host) + license + per-candidate evidence (including any DENIED shadow URL) |
| `paper.access_status` | `paper_access_status(identifier\|doi\|arxiv)` | one of the 5 access categories + provenance |
| `paper.citation_graph` | `paper_citation_graph(identifier\|doi, limit)` | references + citing works from Semantic Scholar / OpenAlex |
| `paper.download_oa_pdf` | `paper_download_oa_pdf(url, dest_dir, filename, license, source)` | hard-gated download → path + sha256 + bytes + license/source; refuses pirate / off-allowlist / non-PDF |
| `paper.summarize` | `paper_summarize(identifier\|doi)` | structured digest from legally-available metadata/abstract (the agent writes the prose) |
| `paper.batch_resolve` | `paper_batch_resolve(identifiers[])` | table of access status + OA links + metadata + unresolved items |

## Config / MCP client registration

Register the server with a command that points at the project venv's Python and runs the server module:

```json
"scholarly-access": {
  "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\scholarly-access-mcp\\.venv\\Scripts\\python.exe",
  "args": ["-m", "scholarly_access.server"],
  "env": {}
}
```

Status: config wired; the server loads at Claude Code restart. (In-session verification beyond loading is not claimed here — the canonical README documents the offline policy tests and live end-to-end checks.)

## API keys / environment variables (by NAME only)

Keys are read by environment-variable name only — never hard-coded, never committed. A missing key means that source is skipped, not an error.

- `UNPAYWALL_EMAIL` — required for Unpaywall.
- `CORE_API_KEY` — CORE.
- `NCBI_API_KEY` — raises PubMed/E-utilities rate limits.
- `SEMANTIC_SCHOLAR_API_KEY` — optional; keyless access works.
- `ELSEVIER_API_KEY` — Elsevier entitled fulltext.

The server auto-loads `~/.tooluniverse/.env` (override with `SCHOLARLY_ENV_FILE`); the process environment always wins.

## Examples (real, tested)

- `paper_resolve("10.1371/journal.pmed.0020124")` → resolved, title "Why Most Published Research Findings Are False".
- `paper_resolve("1706.03762")` → arXiv "Attention Is All You Need".
- `paper_access_status(doi="10.1371/journal.pone.0000308")` → `oa_pdf`, with a PLOS OA URL.
- `paper_access_status(doi="10.1056/NEJMoa2034577")` → `subscription` / `free_to_read_not_redistributable` (NOT downloaded, no bypass).
- `paper_find_oa_pdf(arxiv="1706.03762")` then `paper_download_oa_pdf(url)` → ~2.1 MB PDF + sha256.
- `paper_download_oa_pdf("https://sci-hub.se/...")` → REFUSED (`PermissionError`) — proves the lawful gate.

## Troubleshooting

- **A source returns nothing / is skipped:** check that its API key env var is set (see above). A missing key is silent by design — the source is simply omitted, not an error.
- **`paper_download_oa_pdf` raises `PermissionError`:** the URL host is on the shadow-library denylist or not on the OA allowlist, or the bytes are not a real `%PDF`. This is the lawful gate working as intended — find a legitimate OA URL via `paper_find_oa_pdf`.
- **A title won't resolve:** title resolution uses a similarity threshold (0.55); a too-vague title is reported unresolved. Prefer a DOI / PMID / arXiv id.
- **Server doesn't appear in the client:** confirm the `command` path points at the project venv Python and restart Claude Code so the MCP config reloads.
- **Env file not picked up:** the server reads `~/.tooluniverse/.env`; override with `SCHOLARLY_ENV_FILE`. Process environment variables take precedence over the file.

## Known limitations

- Title resolution uses a 0.55 similarity threshold; a too-vague title may be reported unresolved.
- `free_to_read_not_redistributable` items are intentionally NOT downloaded — open the landing page and cite.
- Citation-graph depth depends on Semantic Scholar / OpenAlex coverage for the given DOI.
- The server fetches only what is legally available; paywalled and shadow-library content is never retrieved.

---

Canonical reference: `tools/scholarly-access-mcp/README.md`.
