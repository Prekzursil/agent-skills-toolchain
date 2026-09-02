# Scholarly Access MCP

A lawful scholarly-retrieval MCP server. It resolves DOI / PMID / arXiv / title queries,
classifies access **honestly**, and routes only to open-access and rights-holder-entitled
sources. What the code enforces (`scholarly_access/policy.py`, tested offline):

- **No shadow libraries, ever.** Any URL containing a denylisted fragment (Sci-Hub, LibGen,
  SciDownl, Anna's Archive, Z-Library, ...) is a hard error, wherever it came from.
- **No paywall bypass, no silent fallback.** A paywalled paper is reported as `subscription`;
  a copy that is merely free-to-read behind a publisher/PMC page is
  `free_to_read_not_redistributable`, never mislabelled as a downloadable OA PDF.
- **Downloads are hard-gated.** `paper_download_oa_pdf` only fetches a URL a legitimate resolver
  returned, whose host is on the OA allowlist, and whose bytes start with `%PDF`. URLs are never
  constructed.
- **Every failure is truthful.** The per-source tools return the upstream HTTP status; nothing is
  retried against another host.

> The estate also carries the third-party `paper-search-mcp`. Its **download tools are
> off-limits here** — `download_with_fallback(use_scihub=True)` and any other shadow-library
> path — use it for search/metadata only. Downloads go through `paper_download_oa_pdf` below.

## Sources (all legitimate)

Crossref · OpenAlex (`OPENALEX_API_KEY` optional) · Unpaywall · Europe PMC (search, full-text
XML of the OA subset, text-mined annotations) · arXiv · Semantic Scholar (keyless graph API) ·
CORE (`CORE_API_KEY`) · DOAJ · PubMed/NCBI E-utilities · Zenodo · OpenCitations Index + Meta
(keyless, CC0).

## Tools (spec name → MCP tool name)

| spec | MCP tool | what |
|---|---|---|
| `paper.resolve` | `paper_resolve` | DOI/PMID/arXiv/title → canonical metadata + normalized ids + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata` | + abstract + references (where legally available) |
| `paper.find_oa_pdf` | `paper_find_oa_pdf` | one **allowlisted** OA PDF URL + license/source, with a verdict for every candidate (denied / off-allowlist / allowlisted) |
| `paper.access_status` | `paper_access_status` | `oa_pdf` / `free_to_read_not_redistributable` / `subscription` / `unavailable` / `unknown` |
| `paper.citation_graph` | `paper_citation_graph` | references + citing works (Semantic Scholar, OpenAlex fallback) |
| `paper.download_oa_pdf` | `paper_download_oa_pdf` | hard-gated download of an allowlisted, real `%PDF` → path + sha256 |
| `paper.summarize` | `paper_summarize` | structured digest from legally-available metadata/abstract |
| `paper.batch_resolve` | `paper_batch_resolve` | resolve a list → table of access status + OA links |
| `paper.citations_for_doi` | `paper_citations_for_doi` | works that **cite** a DOI (OpenCitations Index, newest first, `limit` ≤ 100) |
| `paper.references_for_doi` | `paper_references_for_doi` | works a DOI **cites** (OpenCitations Index, `limit` ≤ 100) |
| `paper.europepmc_fulltext` | `paper_europepmc_fulltext` | plain-text sections of an **open-access** article (Europe PMC full-text XML), capped with `truncated` |
| `paper.europepmc_annotations` | `paper_europepmc_annotations` | text-mined annotations (genes/proteins, diseases, chemicals, ...) for a PMCID or PMID, optional `type` filter |

`python list_tools.py` prints this surface from the running server; `tests/test_server.py` pins it.

### The keyless per-source tools

All four share one envelope. Success: `{"ok": true, "source": ..., ...}`. Failure:
`{"ok": false, "source": ..., "error": ..., "upstream_status": <int|null>, "url": ...}` —
`upstream_status` is the real HTTP status (`null` when no response arrived: timeout, DNS). Bad
input (not a DOI / not a PMCID) is refused **before** any request is made. Every request carries a
30 s timeout.

- **`paper_citations_for_doi` / `paper_references_for_doi`** — each row has the citing/cited DOI,
  title, date, `timespan`, `oci`, the first-author surname, and **`self_citation_suspect`**: a
  **heuristic** that is `true` when the cited and citing works share a first-author surname
  (surnames from OpenCitations Meta, diacritics folded), `false` when both are known and differ,
  `null` when either is unknown. Common surnames give false positives; self-citation by a non-first
  author gives false negatives. OpenCitations' own `author_sc` (any shared author id) and
  `journal_sc` flags are passed through as `opencitations_author_sc` / `opencitations_journal_sc`.
  The Index has no `limit` parameter: rows are sorted newest-first server-side and capped
  client-side (`total_upstream`, `truncated`). Meta failures degrade to `warnings`, not errors.
  Data: CC0.
- **`paper_europepmc_fulltext`** — Europe PMC serves full-text XML only for its open-access
  subset. Anything else is a `404`, reported as such with a `reason`; nothing is fetched from
  anywhere else. A PMCID must carry the `PMC` prefix — bare digits are a PMID and are refused
  rather than silently prefixed (that would fetch a different article). Sections are the abstract
  plus each top-level `<sec>` (nested subsections flattened), `max_chars` 1 000–200 000
  (default 60 000).
- **`paper_europepmc_annotations`** — accepts `PMC1234567` or a bare PMID. Europe PMC answers an
  empty annotations list both when there are none and when the `type` name is unknown to it, so
  an empty result is not proof of absence (valid names: <https://europepmc.org/AnnotationsApi>).

Upstream endpoints, probed 2026-09-02:

| endpoint | shape |
|---|---|
| `GET https://api.opencitations.net/index/v2/{citations,references}/doi:{doi}?sort=desc(creation)` | JSON list of `{oci, citing, cited, creation, timespan, journal_sc, author_sc}`; `citing`/`cited` are space-separated id lists (`omid:… doi:… pmid:…`). The documented `opencitations.net/index/api/v2/…` path 301s here. |
| `GET https://api.opencitations.net/meta/v1/metadata/doi:{a}__doi:{b}` | JSON list of `{id, title, author, pub_date, venue, …}`; `author` = `Surname, Given [omid:…]; …` |
| `GET https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML` | JATS `<article>` for OA PMCIDs; HTTP 404 otherwise |
| `GET https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds?articleIds={PMC:PMCID\|MED:PMID}&format=JSON[&type=…]` | JSON list, one `{source, extId, pmcid, annotations:[…]}` per article; `[]` for an unknown id |

## Install & run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m scholarly_access.server   # stdio MCP server
```

## API keys (env-var NAME only; values are never logged or echoed)

| variable | used for | if missing |
|---|---|---|
| `UNPAYWALL_EMAIL` | Unpaywall (required by them); also the `mailto` polite-pool id sent to Crossref/OpenAlex and the User-Agent | Unpaywall skipped; other calls anonymous |
| `OPENALEX_API_KEY` | OpenAlex meters a free daily budget per key. Sent as `Authorization: Bearer <key>` on **every** OpenAlex call (OpenAlex documents the `api_key` query parameter and the header as working identically — <https://developers.openalex.org/guides/authentication>; the header keeps the key out of URLs and logs). `mailto` is still sent alongside. | calls run on the smaller anonymous budget |
| `CORE_API_KEY` | CORE v3 search (`Authorization: Bearer`) | CORE skipped |
| `NCBI_API_KEY` | raises PubMed E-utilities rate limits | default limits |

Every tool that consults OpenAlex (`paper_resolve` for DOIs/titles and everything built on it;
`paper_citation_graph` when it falls back to OpenAlex) reports **`openalex_authenticated: true|false`**
in its result so the caller knows which budget the call ran on.

Semantic Scholar is called **keyless** (the graph API works without a key; a key this estate once
held returned 403). `SEMANTIC_SCHOLAR_API_KEY` is not read by this package — it is only referenced,
by name, by the separate Asta MCP registration in `.agents/agents.json`.

Missing key ⇒ that source is skipped, never a failure. The server auto-loads `~/.tooluniverse/.env`
(override with `SCHOLARLY_ENV_FILE`); the process environment always wins.

## MCP client registration

```json
"scholarly-access": {
  "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\scholarly-access-mcp\\.venv\\Scripts\\python.exe",
  "args": ["-m", "scholarly_access.server"],
  "env": {}
}
```

## Tests and gates

```bash
pip install -e . pytest pytest-cov basedpyright       # what CI installs (no extras are defined)
python -m pytest -q                                   # offline: every HTTP call is a fake
python -m pytest --cov=scholarly_access --cov-branch --cov-fail-under=100   # CI gate
basedpyright scholarly_access                         # CI type gate
python -m pytest tests/test_policy.py -q              # the offline policy/gate tests alone
python tests/test_live.py                             # MANUAL, needs network (auto-ignored by pytest)
python list_tools.py
```
