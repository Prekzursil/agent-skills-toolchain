---
name: consensus-tooluniverse-research
description: Use when downloading or systematically harvesting research from Consensus.app — extract each shared search browser-free from the page __NEXT_DATA__ payload, resolve every cited paper to a DOI and open-access PDF with ToolUniverse (Crossref, OpenAlex, Unpaywall, EuropePMC), organize by topic with a DOI-linked bibliography, capture the Consensus Meter graphs, and verify headline claims against primary sources. Bundles paste-ready AI-scope and user-scope instructions for mechanistic neuropharmacology and harm-reduction research.
---

# Consensus + ToolUniverse Research Harvest

Turn Consensus.app searches into an organized, DOI-linked, open-access paper library — deterministically
and without a browser — then verify the claims against primary literature with ToolUniverse.

**Why two tools:** Consensus gives the *human synthesis* (meter, claims-evidence tables) but keys papers by
an internal `hash_paper_id` with **no DOI**. ToolUniverse gives the *machine provenance* (DOI → OA full-text).
They compose; neither alone is enough. Full rationale: `references/BEST-METHOD.md`.

---

## When to use
- "Download / save these Consensus searches as text + the papers + the graph."
- "Build me a paper library on <topic> with PDFs and a bibliography."
- Any systematic literature harvest where you want primary-source PDFs + provenance, not just a summary.

## Prerequisites
- **ToolUniverse** installed (`import tooluniverse`; here: `D:\ToolUniverse\.venv`). `tu.load_tools()` before any call.
- Python `requests`. An email for the Unpaywall/OpenAlex `mailto` politeness param.
- Consensus shared-search URLs (`https://consensus.app/search/<slug>/<thread_id>/`) — public, no login.

---

## Pipeline (3 stages — scripts in `scripts/`)

### Stage 1 — extract text + paper list  (`scripts/extract_consensus.py`)
Deterministic, browser-free. `GET` the shared URL → parse `<script id="__NEXT_DATA__">` →
`props.pageProps.thread.interactions[]`. Per interaction: `analysis` (source markdown = the download),
`user_message`, `agent_trace.summary_stats` (retrieved→eligible→included), and paper objects
(`title`, `year`, `first_author`, `hash_paper_id`, `has_full_text`). Writes `<NN>_search.md`,
`papers.json`, `meta.json`, `_raw_thread.json` per search.
Then `scripts/clean_markdown.py` converts Consensus render-tags (`consensus_meter`, `search_strategy_diagram`,
`top_contributors`, …) to readable markdown and lifts meter questions + funnels into `meta.json`.

### Stage 2 — resolve + download papers, OA-only  (`scripts/resolve_and_download.py`)
1. Dedup all `papers.json` by `hash_paper_id` → master list.
2. **DOI:** `tu.run({"name":"Crossref_search_works","arguments":{"query":"<title> <author>","limit":3}})`,
   matched by title-similarity (≥0.80) + year (±1); fallback `openalex_search_works`.
   *(SemanticScholar 403s without an API key — deprioritize.)*
3. **OA:** `tu.run({"name":"Unpaywall_get_full_text_url","arguments":{"doi":doi,"email":EMAIL}})` →
   `is_oa` + `all_oa_locations`.
4. **Download tiers** (browser UA + `Referer`; OA-only): Unpaywall pdf locations → NCBI PMC OA package
   (`oa.fcgi`) → EuropePMC `fullTextXML`. Download once to `_library/`, copy into each citing
   `searches/<topic>/papers/`. Writes `master_bibliography.{json,csv}`, per-topic `references.md`,
   `_funnel_report.json`. Resumable via `_progress.json`.

### Stage 3 — the graph (Consensus Meter)
Render-time component — the Yes/Possibly/Mixed/No **percentages are not in the payload**. Capture the meter
**question** + **funnel** (deterministic, in `meta.json`) and a **screenshot** for the visual. The citation
**Graph** ("N seeds") is a distinct feature, not the meter.

---

## ToolUniverse tool reference (this pipeline)
| Need | Tool | Key args |
|---|---|---|
| Title → DOI | `Crossref_search_works` | `query`, `limit` |
| Title → DOI (fallback) | `openalex_search_works` | `search`, `mailto` |
| DOI → OA PDF | `Unpaywall_get_full_text_url` | `doi`, `email` |
| DOI → metadata/OA | `openalex_get_work_by_doi` | `doi`, `mailto` |
| OA full text (PMC) | `EuropePMC_get_fulltext` / REST `fullTextXML` | `pmcid` |
| Literature search | `EuropePMC_search_articles`, `PubMed_search_articles`, `openalex_literature_search` | `query`, `limit` |
| Citation *stance* (supports/contrasts) | `scite_get_tallies` (auth-gated, optional) | `pmid` |
| Citation *influence* (RCR) — **NOT** stance | `iCite_search_publications` | `pmid` |

For deeper entity work, delegate to the domain skills: `tooluniverse-literature-deep-research`,
`tooluniverse-neuroscience`, `tooluniverse-pharmacovigilance`, `tooluniverse-drug-drug-interaction`,
`tooluniverse-toxicology`, `tooluniverse-clinical-guidelines`, `tooluniverse-drug-mechanism-research`.

## Verify, don't just download
Re-check each search's headline meter-claim against the resolved primary papers (grade T1–T4; use
`iCite`/`scite` for support/contradiction) before treating it as settled — this turns "downloaded papers"
into "verified research".

---

## Caveats (calibrated on real runs)
- **Publisher Cloudflare walls** (MDPI/Wiley/Frontiers) 403 direct PDF GETs even for OA. Use UA+Referer+session;
  prefer EuropePMC/PMC/green-OA. Un-fetchable ones are logged with their OA URL (⛔) — the paper *is* OA, just
  bot-walled; download via browser if needed. Not a failure.
- **Recency lag:** brand-new papers may have a PMCID but no ingested full text yet.
- **OA-only, always.** "Every available PDF" = every legally open-access one. Never bypass paywalls; record
  paywalled papers with DOI + citation.
- Expect ~100% DOI resolution, ~50-60% OA, downloaded PDF a subset of OA.

## Output layout
```
<workspace>/
  00_INDEX.md  00_BEST-METHOD.md
  INSTRUCTIONS/{AI-SCOPE,USER-SCOPE}.md      # paste-ready research instructions
  searches/<NN>_<topic>/{<NN>_search.md, papers.json, meta.json, papers/{*.pdf, references.md}, graphs/}
  _library/        # deduped OA PDFs/XML by DOI
  _bibliography/   # master_bibliography.{json,csv} + _funnel_report.json
```

## Research conduct
Paste-ready operating instructions in `references/AI-SCOPE.md` (how the assistant works: look-up-don't-guess,
T1–T4 grading, mechanism-first, harm-reduction discipline) and `references/USER-SCOPE.md` (the user's
biochemistry/neuropharmacology focus). Load these when doing the actual research, not just the harvest.
