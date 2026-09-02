# Lens 13: academic search upgrades
Source: subagent bc-1c26835a-bf96-5c49-afdf-541a37602cf9, dispatched 2026-09-02 from cloud run bc-2a7f9bf8-4a9a-4193-a2c3-4f80d21392f9; completion notification was lost, report recovered from the transcript on 2026-09-02.
Status: raw lens report — findings, not decisions. Decisions live in ../2026-09-02-search-research-tools-gemhunt.md.

# Lens report — Scholarly search/metadata upgrades (academic lane)

Scope: web + GitHub research only; no files modified. Ranked keyless-first. Dedup target = `scholarly-access` MCP, `huggingface paper_search`, ToolUniverse, e-nformation.ro institutional access, `oa-pdf-retrieval` + `scholarly-literature-review` skills, and the already-connected `paper-search-mcp` (57 tools, `KEEP` in `command-center/mcp-audit/disposition.json`).

## TL;DR — the 2-3 that actually fill gaps (no Sci-Hub anywhere)

| Gap | Pick | Why it wins |
|---|---|---|
| Open-access discovery | **F4 OpenAlex via `cyanheads/openalex-mcp-server`** (free key) + **F2 Europe PMC full-text XML** (keyless) | OpenAlex `best_oa_location` subsumes Unpaywall; Europe PMC gives OA full text as XML with no key. Both legal by construction. |
| Citation graph | **F1 OpenCitations** (keyless, third independent leg) + **F5 Semantic Scholar via Ai2 Asta MCP** (free key) | Lane currently leans on S2+OpenAlex only; OpenCitations adds self-citation flags and an independent CC0 index; Asta adds snippet search over 12M+ full texts. |
| Full-text QA | **F3 `arxiv-mcp-server`** (keyless, bounded LaTeX section reads) now; **F6 PaperQA2** (Apache-2.0) as the conditional heavy option | arXiv covers most ML/CS; PaperQA2 is the only mature cited-QA engine but burns LLM tokens and needs an embedding provider. |

## Dedup and risk notes on CURRENT (read before adopting anything)

- `scholarly-access` already wraps Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, S2, CORE, DOAJ, PubMed E-utilities, Zenodo (`tools/scholarly-access-mcp/scholarly_access/sources.py`, header comment: "LEGITIMATE scholarly sources only. No shadow libraries."). **But `tools/scholarly-access-mcp/README.md` still advertises "Sci-Hub (mirror failover) · LibGen (mirror failover)".** Code is clean; README has drifted. Worth fixing so no agent goes looking for that path.
- `openags/paper-search-mcp` (MIT, pushed 2026-08-17, 2.5k stars) is connected. Its README describes Sci-Hub as optional, but `server.py` has `download_with_fallback(..., use_scihub: bool = True)`. **Treat every download tool in that MCP as off-limits; use it for search/metadata only.** Its `search_openalex`/`search_europepmc`/`search_crossref`/`search_pubmed` already appear in `command-center/_wfa5_features.json`, so those sources are "covered" for search.
- OpenAlex moved from the keyless polite pool to **mandatory free API keys with a $1/day free budget** (≈10,000 list/filter calls, 1,000 search calls, 100 PDF/XML downloads; `search.semantic` is $0.01/call and draws from the same budget). `scholarly-access` identifies itself via `mailto` only, so its OpenAlex calls run on the anonymous tier. Getting a key and threading `OPENALEX_API_KEY` through is the single cheapest upgrade in this whole report. Source: https://developers.openalex.org/guides/authentication and https://openalex.org/settings/api.
- The `scholarly-access` note "keyless works, the provided key 403s" for Semantic Scholar matches S2's policy: keys unused for ~60 days are pruned, and the key must be sent as `x-api-key`. Re-request with an institutional email. Source: https://www.semanticscholar.org/product/api (form) and https://api.semanticscholar.org/api-docs/.
- "ancatmara openalex-mcp" from the brief does not exist (`gh api repos/ancatmara/openalex-mcp` → 404). Substituted with the two live OpenAlex MCPs in F4.

---

## F1 — OpenCitations REST API (keyless) — ADOPT

- **What:** Independent, CC0 citation index (COCI/OpenCitations Index). Endpoints for `citations/{doi}`, `references/{doi}`, `citation-count`, `reference-count`, `metadata`, each citation carrying `timespan`, `journal_sc`/`author_sc` self-citation flags.
- **Why this user:** Keyless, no account, no budget. Adds a third independent leg to `paper_citation_graph` (currently S2 + OpenAlex; see `.agents/skills/citation-mapping/SKILL.md`), so disagreement between indexes becomes detectable rather than silent. Anti-overfit: pure REST, trivially callable from a skill script; no MCP needed.
- **How to adopt:** Direct REST (`https://opencitations.net/index/api/v2/citations/doi:<DOI>`). Keyless. Rate limit 180 req/min (docs recommend an optional free access token in `authorization` header for priority; still free). Add as an optional cross-check in `scholarly-literature-review` / `citation-mapping` rather than a new server.
- **MCP status:** No maintained OpenCitations MCP found (`gh search repos "opencitations mcp"` → empty). Not a blocker; REST fits a skill helper.
- **Source:** https://opencitations.net/index/api/v2 ; https://opencitations.net/index
- **License:** Data CC0-1.0 (stated on site); API code not relevant (hosted).
- **Value × effort:** M × L. **Novelty:** High for this lane (no existing tool touches it). **Confidence:** M-H (API doc read this session; rate-limit figure from API page).

## F2 — Europe PMC REST + Annotations API (keyless) — ADOPT-lite (extend usage, no new server)

- **What:** Life-sciences index (PubMed + PMC + preprints + Agricola + patents). `fullTextXML` for OA articles, `citations`/`references` endpoints, and an Annotations API returning text-mined entities (genes, chemicals, diseases, accession numbers) per article.
- **Why this user:** Keyless; full text as structured XML is the best legal input for full-text QA in bio without touching PDFs. Both `scholarly-access` and `paper-search-mcp` already *search* Europe PMC, but neither surfaces `fullTextXML` sections or annotations. Complements ToolUniverse rather than duplicating it (ToolUniverse is tool-heavy, not a literature full-text reader).
- **How to adopt:** REST at `https://www.ebi.ac.uk/europepmc/webservices/rest/` (`/search`, `/PMC{id}/fullTextXML`, `/MED/{pmid}/citations`); Annotations at `https://www.ebi.ac.uk/europepmc/annotations_api/`. Keyless. No hard published limit; docs ask for ~1-2 req/s and identification via `email` param for heavy use. Extend the existing `scholarly-access` Europe PMC client or add a small skill script.
- **MCP status:** Only two zero-star community servers (`CoChatAI/europepmc-mcp-server` MIT, `QuentinCody/europepmc-mcp-server` no license). Skip both; not worth a new dependency.
- **Source:** https://europepmc.org/RestfulWebService ; https://europepmc.org/AnnotationsApi
- **License:** Service under EMBL-EBI terms; article content per-article (OA subset explicitly redistributable, licenses in metadata `license` field). No SPDX for the API.
- **Value × effort:** M × L. **Novelty:** Medium (source known, full-text/annotation endpoints unused). **Confidence:** H (docs read this session, saved locally).

## F3 — arXiv API + `blazickjp/arxiv-mcp-server` (keyless) — ADOPT

- **What:** arXiv Atom API for search/metadata; the MCP adds 19 tools: `search_papers`, `read_paper` (local, bounded), `read_paper_section`, `list_paper_latex_sections` / `get_paper_latex_section` (original LaTeX, no PDF parsing), `export_citations` (BibTeX), `watch_topic`, optional `semantic_search`.
- **Why this user:** Keyless end to end. Fills the full-text-QA gap for the ML/CS slice legally: LaTeX section reads are bounded and cheap, so an agent can answer "what does §4 say" without a RAG stack. MCP-first, actively maintained (pushed 2026-08-26, 3.1k stars). Overlap with `huggingface paper_search` (discovery/trending) and `paper-search-mcp read_arxiv_paper` (whole-PDF text) is only on *discovery*; the section-level LaTeX path is unique.
- **How to adopt:** `uv tool install arxiv-mcp-server` or `uvx arxiv-mcp-server` in an MCP config; set `ARXIV_STORAGE_PATH`. Keyless. arXiv API ToU: max 1 request every 3 s, single connection, `User-Agent` identifying you. Let the MCP handle throttling; don't parallelize arXiv calls from the agent.
- **Source:** https://github.com/blazickjp/arxiv-mcp-server ; https://info.arxiv.org/help/api/tou.html ; https://info.arxiv.org/help/api/user-manual.html
- **License:** `LICENSE` in repo → Apache-2.0 (verified via GitHub API). arXiv metadata CC0; paper bodies per-paper license.
- **Value × effort:** M-H × L. **Novelty:** Medium-High (LaTeX section reads + watches). **Confidence:** H.

## F4 — OpenAlex API via `cyanheads/openalex-mcp-server` (free key, $1/day budget) — ADOPT

- **What:** 270M+ works, 8 entity types, `best_oa_location`/`open_access.oa_url` (Unpaywall data now lives here), `is_retracted` (Retraction Watch), `search.semantic`, full-text PDF/TEI XML downloads within budget. The cyanheads MCP exposes 5 tools (`search_entities`, `analyze_trends`, `resolve_name`, `get_citation_graph`, `describe_fields`) + 2 prompts, and **reports OpenAlex daily-budget spend/remaining on every call** so a paginated sweep can be priced before it 429s.
- **Why this user:** MCP-first and budget-aware, which matters now that OpenAlex is metered. Keyed but free; the key also unlocks legal OA full-text downloads (100/day) as a clean replacement for the `paper_find_oa_pdf` path the user avoids. Anti-overfit: hosted endpoint (`https://openalex.caseyjhand.com/mcp`) or `npx @cyanheads/openalex-mcp-server`; no bespoke wrapper.
- **How to adopt:** Create free key at https://openalex.org/settings/api → set `OPENALEX_API_KEY` (optional `OPENALEX_MAILTO`). Limits: free budget ≈10k list/filter + 1k search + 100 downloads per day; semantic search $0.01/call from the same budget; 429 on exhaustion. Prefer filters over `search.semantic` for bulk. Also pass the same key into `scholarly-access` (see risk notes).
- **Alternative considered:** `oksure/openalex-research-mcp` (MIT, pushed 2026-06-22, 47 stars) — more tools but no budget reporting and still documents the deprecated polite pool. Prefer cyanheads.
- **Source:** https://github.com/cyanheads/openalex-mcp-server ; https://docs.openalex.org/ ; https://developers.openalex.org/guides/authentication
- **License:** `LICENSE` → Apache-2.0 (verified). OpenAlex data CC0-1.0.
- **Value × effort:** H × L-M. **Novelty:** Medium (source known; keyed/budgeted tier + retraction filter + downloads are new to the lane). **Confidence:** H (README + pricing docs read this session).

## F5 — Semantic Scholar Graph API via Ai2 Asta MCP (free key) — ADOPT

- **What:** Official Ai2-hosted MCP over the S2 graph: 225M+ papers, 2.4B+ citation edges, author graph, and a **snippet search endpoint over 12M+ full-text publications (285M passages)**. IDs accepted: S2, CorpusId, DOI, ARXIV, PMID, PMCID, ACL, MAG.
- **Why this user:** MCP-first, first-party, streamable HTTP. Snippet search is the missing "search inside full text" primitive for non-arXiv papers without any PDF handling — and it is fully legal (OA corpus). Replaces the flaky direct-key path that `scholarly-access` reports 403s on.
- **How to adopt:** Register `https://asta-tools.allen.ai/mcp/v1` with header `x-api-key: <key>` (key form: https://share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm; institutional email helps). Clients that can't set headers bridge via `mcp-remote`. Direct Graph API for scripts: unauthenticated shared pool (heavily contended), keyed 1 req/s; keys pruned after ~60 days of inactivity → 403.
- **Source:** https://allenai.org/asta/resources/mcp ; https://api.semanticscholar.org/api-docs/ ; https://www.semanticscholar.org/product/api
- **License:** Hosted service under Ai2/S2 API terms (no SPDX); S2 dataset ODC-BY-1.0 with attribution. Optional instruction-pack skill `Agents365-ai/asta-skill` exists but is unnecessary.
- **Value × effort:** H × L. **Novelty:** High for the lane (snippet search; first-party MCP). **Confidence:** H (official docs; cross-checked with community skill).

## F6 — PaperQA2 (`Future-House/paper-qa`) — ADOPT-conditional (full-text QA, heavy)

- **What:** Agentic RAG over a local folder of papers with per-claim citations; `pqa ask "..."` CLI or Python `Docs` API. Metadata enrichment via Crossref/S2/Unpaywall/OpenAlex (all legal). LLMs via LiteLLM; default embeddings OpenAI + NumPy vector store, swappable to local (e.g. Ollama via LiteLLM).
- **Why this user:** It is the only mature, maintained (pushed 2026-08-26, 9.1k stars) engine that produces cited answers across many PDFs — the true "full-text QA" gap. Fits legally: feed it PDFs already obtained via institutional access or OA. Anti-overfit caveat: it is a pipeline, not an MCP; community MCP wrappers exist but are thin and unmaintained, so run it as a CLI/skill step and don't hard-wire it into every workflow.
- **How to adopt:** `pip install paper-qa`; point `PQA_HOME`/paper dir at the institutional/OA download folder; set LLM + embedding provider env (`OPENAI_API_KEY` or a LiteLLM local config). No API key for the tool itself; cost is tokens. Keep `scholarly-access paper_summarize` for single-paper summaries.
- **Source:** https://github.com/Future-House/paper-qa ; paper: https://arxiv.org/abs/2409.13740
- **License:** `LICENSE` → Apache-2.0 (verified).
- **Value × effort:** H × M. **Novelty:** High. **Confidence:** H on capability/license; M on local-embedding ergonomics (documented but not tested here).

## F7 — CORE API v3 (free key) — SKIP as new tool; config-only

- **What:** Aggregated repository content, `fullText` field and `has_full_text:true` filter, ~300M metadata records.
- **Why not more:** Already a source inside both `scholarly-access` and `paper-search-mcp`. Coverage is largely repository copies that OpenAlex/Unpaywall also locate. Free key required; limit read this session as 150 req per 15-min window (≈10/min), which is tight for sweeps.
- **How to adopt (only this):** register at https://core.ac.uk/services/api and set `CORE_API_KEY` so the existing client stops silently degrading. No new MCP.
- **Source:** https://api.core.ac.uk/docs/v3 ; https://core.ac.uk/services/api
- **License:** API under CORE terms; content per-record. **Value × effort:** L × L. **Novelty:** Low. **Confidence:** M (limit figure from docs; verify in dashboard).

---

## Skipped (dedup or dead) — with reasons

| Item | Verdict | Why |
|---|---|---|
| Unpaywall REST (keyless w/ email, 100k calls/day) | SKIP | Already in `scholarly-access` (`paper_find_oa_pdf`, which user avoids). Runs on OpenAlex codebase now; `best_oa_location` in F4 returns the same data. https://unpaywall.org/products/api |
| Crossref REST (keyless, polite pool via `mailto`, ~50 req/s) | SKIP | Already primary resolver in `scholarly-access` and `paper-search-mcp search_crossref`. Only note: use `update-to`/`is-update-to` relations for retraction notices if F4's `is_retracted` isn't enough. https://api.crossref.org/swagger-ui/index.html |
| PapersWithCode | SKIP (dead) | Shut down July 2025; redirects to Hugging Face Trending Papers, which `huggingface paper_search` already covers. |
| `JackKuo666/PubMed-MCP-Server` (MIT, last push 2025-05-08) / `JackKuo666/bioRxiv-MCP-Server` (no license file, last push 2025-03-18) | SKIP (stale, license risk) | ToolUniverse + `paper-search-mcp search_pubmed`/`search_biorxiv` + Europe PMC (F2, which indexes bioRxiv/medRxiv preprints) cover this. NCBI E-utilities are keyless at 3 req/s (10 with free key) if a direct call is ever needed. https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| `oksure/openalex-research-mcp` | SKIP (superseded) | See F4; cyanheads is newer, Apache-2.0, budget-aware. |
| "ancatmara openalex-mcp" | SKIP (nonexistent) | 404 on GitHub. |
| Any Sci-Hub/LibGen path (`paper-search-mcp download_with_fallback`, stale README lines in `scholarly-access`) | HARD SKIP | User constraint; both F4 (OpenAlex downloads) and F2 (Europe PMC XML) are the legal replacements, plus existing e-nformation.ro access. |

## Adoption order (cheapest legal wins first)

1. Get an OpenAlex key; set `OPENALEX_API_KEY` in `scholarly-access` and add `cyanheads/openalex-mcp-server` (F4).
2. Register Asta MCP with a fresh S2 key (F5). Retire the 403ing direct key.
3. Add `arxiv-mcp-server` (F3) — zero credentials.
4. Add OpenCitations (F1) and Europe PMC `fullTextXML`/annotations (F2) as REST helpers inside the existing skills — zero credentials.
5. Trial PaperQA2 (F6) on one institutional-PDF folder before wiring it into `scholarly-literature-review`.
6. Set `CORE_API_KEY` (F7) only if repository-copy recall is observed to matter.