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
- **ToolUniverse** installed (`import tooluniverse`; `tu.load_tools()` before any call). `pip install requests tooluniverse` (or run with the ToolUniverse venv).
- Consensus shared-search URLs (`https://consensus.app/search/<slug>/<thread_id>/`) — public, no login.
- **Config (no hardcoding — the scripts read these):** `CONSENSUS_WS` = workspace dir (or `--ws`, default cwd);
  `UNPAYWALL_EMAIL` = your contact email (or `--email`; **required** by Unpaywall/OpenAlex, fails fast if unset).

## Run
```bash
export CONSENSUS_WS=/path/to/workspace
export UNPAYWALL_EMAIL=you@example.com
python scripts/extract_consensus.py --urls searches.txt   # one Consensus URL per line, OR pass URLs as args
python scripts/clean_markdown.py
python scripts/resolve_and_download.py                    # resumable; %PDF-verified; OA-only
```

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
2. **DOI:** `Crossref_search_works` (fallback `openalex_search_works`). **Acceptance test:** SequenceMatcher
   title-ratio ≥0.80 AND year ±1 AND **first-author surname present in the candidate's authors** (title+year
   alone can false-match a different author's same-named work). Records `match_score` + matched title — this
   is a resolution *rate*, not validated precision; spot-check. *(SemanticScholar 403/429s keyless — deprioritized.)*
3. **OA:** `tu.run({"name":"Unpaywall_get_full_text_url","arguments":{"doi":doi,"email":EMAIL}})` →
   `is_oa` + `all_oa_locations`.
4. **Download tiers** (browser UA + `Referer`; OA-only): Unpaywall pdf locations → NCBI PMC OA package
   (`oa.fcgi`) → EuropePMC `fullTextXML`. Download once to `_library/`, copy into each citing
   `searches/<topic>/papers/`. Writes `master_bibliography.{json,csv}`, per-topic `references.md`,
   `_funnel_report.json`. Resumable via `_progress.json`.

### Stage 2b — keyed recovery of bot-walled papers  (`scripts/resolve_and_download_v2.py`, optional)
Keyless v1 leaves OA-but-Cloudflare-walled papers as ⛔. v2 re-fetches them via **legitimate keyed sources**
(keys in `~/.tooluniverse/.env`, read by name — see `references/PAPER-RETRIEVAL-KEYS.md`):
**CORE → Elsevier** (the publisher's *own* entitled API) **→ Zenodo → DOAJ → Unpaywall-retry**, %PDF-verified.
Re-runs only the `blocked` (and entitled-paywalled) rows; **never bypasses a paywall** — no Sci-Hub/LibGen,
strictly OA + rights-holder-sanctioned access. Absent keys are skipped gracefully.

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

## Verify — the Consensus `analysis` is an UNVERIFIED secondary claim
The downloaded Consensus `analysis` is LLM-generated and can misattribute or overstate — never carry it as a
primary finding. To verify a headline/meter claim: extract the specific proposition, run a fresh
primary-literature query, judge support/contradict from the retrieved abstract/full text with a **quoted
passage + DOI**, and require ≥2 independent concordant T1/T2 **human** sources (no T1/T2 contradiction) before
stating it as fact. Grade every claim per `references/EVIDENCE-GRADING.md` (tier T1–T4 **and** human/animal/
in-vitro type — mechanism never settles a clinical dose/safety claim alone). For citation *stance* use
`scite_get_tallies`; `iCite` gives citation *influence* (RCR), **not** support/contradiction. Any
dosing/toxicity/interaction claim kept from Consensus without a resolved primary source stays labeled
`UNVERIFIED — Consensus synthesis`.

---

## Caveats (calibrated on real runs)
- **Publisher Cloudflare walls** (MDPI/Wiley/Frontiers) 403 direct PDF GETs even for OA. Use UA+Referer+session;
  prefer EuropePMC/PMC/green-OA. Un-fetchable ones are logged with their OA URL (⛔) — the paper *is* OA, just
  bot-walled; download via browser if needed. Not a failure.
- **Recency lag:** brand-new papers may have a PMCID but no ingested full text yet.
- **OA-only, always.** "Every available PDF" = every legally open-access one. Never bypass paywalls; record
  paywalled papers with DOI + citation.
- Expect ~100% DOI resolution *rate* (assigned, not validated precision), ~50-60% OA (corpus-dependent),
  downloaded PDF a subset of OA. `is_oa` conflates gold/green/bronze (bronze is revocable); XML captures are
  text-only (figures absent). Downloads are %PDF-magic-byte verified before counting (an HTML bot-wall page
  saved as `.pdf` is rejected, not counted).

## Output layout
```
<workspace>/                                   # ── GENERATED by the scripts ──
  searches/<NN>_<topic>/{<NN>_search.md, papers.json, meta.json, papers/{*.pdf, references.md}}
  _library/        # deduped OA PDFs/XML by DOI
  _bibliography/   # master_bibliography.{json,csv} + _funnel_report.json + _progress.json
                                               # ── PROVIDED (operator-placed, not generated) ──
  00_INDEX.md  00_BEST-METHOD.md  graphs/  INSTRUCTIONS/{AI-SCOPE,USER-SCOPE,EVIDENCE-GRADING}.md
```

## Research conduct
Paste-ready operating instructions: `references/AI-SCOPE.md` (how the assistant works: look-up-don't-guess,
mechanism-first-not-mechanism-as-proof, harm-reduction in-scope/decline boundary) and `references/USER-SCOPE.md`
(the user's biochemistry/neuropharmacology focus). Evidence grading is defined once in
`references/EVIDENCE-GRADING.md` (tier T1–T4 **×** human/animal/in-vitro type — mechanism never settles a
clinical dose/safety claim alone); both scope docs reference it. Load these when doing the actual research,
not just the harvest. Sibling domain skills in this repo: `ddi-admet-research`, `mechanistic-ddi-pipeline`,
`cheminformatics-rdkit`.
