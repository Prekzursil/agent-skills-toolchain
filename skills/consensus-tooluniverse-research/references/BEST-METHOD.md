# Best Method — downloading Consensus searches, their papers, and their graphs

**Conclusion (TL;DR):** the most reliable, reproducible, browser-free pipeline is a **3-stage chain** —
1. **Text + paper list** → parse the Consensus page's server-rendered `__NEXT_DATA__` JSON (no scraping, no login).
2. **Papers (DOI → open-access PDF)** → **ToolUniverse** (`Crossref` → `OpenAlex` resolve; `Unpaywall` OA discovery) + a tiered HTTP downloader.
3. **Graph (Consensus Meter)** → it is a render-time component; capture the **question + funnel data** from the payload (deterministic) and a **screenshot** for the visual.

All three are implemented as scripts in `_workspace/` and double as the engine of the reusable skill.

---

## Methods evaluated

| Method | Text | Papers/DOIs | Graph | Verdict |
|---|---|---|---|---|
| **Browser `get_page_text`** (claude-in-chrome) | ✅ full | ❌ (no DOIs; refs panel collapsed) | ✅ visual (screenshot) | Works but **non-deterministic** — tabs re-ID on navigate, JS timeouts. Good fallback, poor primary. |
| **SSR `__NEXT_DATA__` parse** (HTTP GET) | ✅ source markdown (`analysis`) | ⚠️ paper list w/ title/year/author/`hash_paper_id` — **no DOI** | ⚠️ meter *question* + funnel only (render-time % not in payload) | **WINNER for text+paper-list.** Deterministic, scriptable, no login. |
| **ToolUniverse** (Crossref/OpenAlex/Unpaywall/EuropePMC) | — | ✅ DOI resolution + OA PDF discovery + download | — | **WINNER for papers.** Live, legal, the through-line for the research skill. |

**Why not a single tool:** Consensus gives the *human synthesis* (meter, claims-evidence tables) but keys papers by internal `hash_paper_id` with **no DOI**; ToolUniverse gives the *machine provenance* (DOI → OA full-text). They compose; neither alone is sufficient.

---

## The winning pipeline (implemented)

### Stage 1 — `_workspace/extract_consensus.py`  (text + paper list)
- `GET https://consensus.app/search/<slug>/<thread_id>/` → regex out `<script id="__NEXT_DATA__">` → `props.pageProps.thread.interactions[]`.
- Per interaction: `analysis` (source markdown = the download), `user_message` (query), `agent_trace.summary_stats` (retrieved→eligible→included funnel), and paper objects (`title`, `year`, `first_author`, `hash_paper_id`, `has_full_text`).
- Output: `searches/<NN>/<NN>_search.md`, `papers.json`, `meta.json`, `_raw_thread.json`.
- **No auth** (shared threads are public). Deterministic *given an unchanged Consensus `__NEXT_DATA__`
  schema + a fixed snapshot date* — it reads a live, unversioned service, so capture `_raw_thread.json`
  as the provenance archive. The retrieved→eligible→included counts are **Consensus's internal funnel,
  not a PRISMA systematic review** (no protocol, no pre-specified criteria, screening by an opaque model).

### Stage 1b — `_workspace/clean_markdown.py`  (formatting + graph manifest)
- Converts Consensus custom render-tags to readable markdown and lifts structured data into `meta.json`:
  `<consensus_meter generatedQueryOverride='Q'/>` → meter question; `<search_strategy_diagram .../>` → funnel; `<top_contributors authors=@@json@@.../>` → contributor list; `<figure_caption/>`, `<evidence_strength_indicator/>`, `<research_gap_heatmap_cell/>` → inline values.

### Stage 2 — `_workspace/resolve_and_download.py`  (papers, OA-only, via ToolUniverse)
- Dedup all `papers.json` by `hash_paper_id` → master unique list.
- **Resolve DOI:** `tu.run({"name":"Crossref_search_works", ...})` matched by title-similarity (≥0.80) + year (±1); fallback `openalex_search_works`. *(SemanticScholar 403s without an API key — deprioritized.)*
- **OA discovery:** `tu.run({"name":"Unpaywall_get_full_text_url", {"doi":..., "email":...}})` → `is_oa` + `all_oa_locations`.
- **Tiered download** (browser session + `Referer` to beat soft bot-walls; **OA-only**):
  1. each Unpaywall OA pdf location;
  2. PMCID → NCBI PMC OA package (`oa.fcgi`) → PDF;
  3. PMCID → EuropePMC `fullTextXML` (content capture when the PDF is bot-walled).
- Download **once** into `_library/<safe_doi>.<ext>`, then copy into every citing `searches/<topic>/papers/`.
- Output: `_bibliography/master_bibliography.{json,csv}`, per-search `papers/references.md`, `_funnel_report.json`. **Resumable** via `_bibliography/_progress.json`.

### Stage 3 — the graph (Consensus Meter)
- The meter is rendered client-side; the Yes/Possibly/Mixed/No **percentages are not in the SSR payload**. Captured artifacts: the meter **question** + **funnel** (deterministic, in `meta.json`), plus a **screenshot** for the visual (in `searches/<NN>/graphs/`). The separate citation **Graph** ("50 seeds / N") is a distinct feature, not the meter.

---

## Hard-won caveats (calibrated on real papers)

- **Publisher Cloudflare walls.** Gold-OA publishers (MDPI, Wiley pdfdirect, Frontiers) often **403** a direct PDF GET even for OA content. Mitigations: browser UA + `Referer` + session; prefer EuropePMC/PMC/repository (green-OA) copies. Some remain auto-unfetchable → recorded as ⛔ with their OA URL for one-click manual/browser download. **This is not a failure** — the paper *is* OA, just bot-walled.
- **Recency lag.** Brand-new papers (e.g. Nov-2025) may have a PMCID but no ingested full-text yet → expect lower yield on the newest items.
- **OA-only, always.** "Every available PDF" = every **legally open-access** one (Unpaywall/EuropePMC/PMC/arXiv/bioRxiv). Paywalled papers are recorded with DOI + citation; **no paywall bypass.**
- **Realistic funnel** (see `_bibliography/_funnel_report.json`): DOI **resolution rate** ~100% (rate = a DOI was *assigned* via title-sim + year + author-surname match — precision is **not** separately validated; spot-check the `match_score` column); OA ~50-60% *on this neuropharm corpus* (field-dependent); auto-downloaded PDF a subset of OA (publisher bot-walls reduce it); the rest captured as **text-only XML (figures absent)** or logged with their OA URL.
- **`is_oa` is not ground truth.** Unpaywall conflates gold/green/bronze; bronze is publisher-revocable and the flag can be stale. The bibliography records `oa_status` — treat bronze as fragile.
- **SemanticScholar** throttles/blocks keyless requests (403/429) — deprioritized for Crossref/OpenAlex.

**Actual result (this corpus, 2026-06-06):** 506 unique → 496 DOI → 345 OA → **230 PDFs** (125 keyless v1 +
**105 keyed v2** via CORE / Elsevier-entitled / Zenodo / DOAJ — see `_funnel_report_v2.json`). The keyed v2
(`resolve_and_download_v2.py`, reads keys from `~/.tooluniverse/.env`) nearly doubled the PDF yield; Elsevier's
own entitled API was the single biggest contributor. ~161 OA papers remain bot-walled (logged with OA URLs)
and 105 paywalled non-Elsevier (cite-only). **No paywall bypass — OA + rights-holder-sanctioned access only.**

---

## Reproduce
Scripts live in `_workspace/` here (and in `scripts/` in the `consensus-tooluniverse-research` skill).
They are parameterized — no hardcoded paths/URLs/email:
```powershell
$py = "D:\ToolUniverse\.venv\Scripts\python.exe"
$env:CONSENSUS_WS   = "C:\Users\Prekzursil\Downloads\proof_empty"
$env:UNPAYWALL_EMAIL = "you@example.com"      # Unpaywall/OpenAlex require a contact email
& $py _workspace\extract_consensus.py --urls searches.txt   # one Consensus URL per line
& $py _workspace\clean_markdown.py                          # readable formatting + graph manifest
& $py _workspace\resolve_and_download.py                    # papers via ToolUniverse (resumable; %PDF-verified)
```
