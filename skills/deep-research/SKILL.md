---
name: deep-research
description: Multi-source deep research with a routing + caching + grading harness over firecrawl, exa, tavily, perplexity, scholarly-access, tooluniverse, huggingface, and context7 MCPs. Routes each sub-question to the best live provider, caches provider calls by query hash, grades every source by confidence, and delivers cited reports. Use when the user wants thorough, evidence-backed research.
---

# Deep Research

> **Drift-prone skill.** Firecrawl/Exa/Tavily MCP tool names, quotas, and
> result shapes change. Verify the configured MCP tools and current API docs
> before promising coverage or quoting live source counts. The routing table in
> `references/research_harness/routing.py` is the single choke-point to update,
> and the preflight step catches name/availability drift at runtime.

## Instrumentation (Wave B passenger, 2026-08-27 — no logic changes)

This skill measures **42% success over 90 uses** (worst popular skill). Hypothesis: long
multi-hop runs outlive their context/tool budget on this RAM-starved box, so partial runs log
as failures. To make that measurable instead of guessed: **each run should append phase
timestamps** (plan / search / deep-read / synthesize / deliver, plus abort point if any) as
one JSONL line per phase to `C:\Users\Prekzursil\.agents\logs\cursor-subagent-lifecycle.jsonl`
— the same log Cursor's `subagentStart`/`subagentStop` hooks write to — e.g.
`{"ts":"<ISO8601>","source":"deep-research","phase":"search","note":"..."}`. Do NOT change
the research logic based on the hypothesis until this log disproves or confirms it.

**Update (Wave 2 reliability set, 2026-09-02 — approved in the search/research SSOT plan, not
by the log):** every run now ends in exactly one terminal state (`Report.status`, see
"Terminal states" below) and the `deliver` line should carry it:
`{"ts":..., "source":"deep-research", "phase":"deliver", "status":"partial:budget"}`.
`report.summarize_statuses(...)` tallies `partial:*` apart from `failed`, which is the
measurement the hypothesis above was waiting for: a run that shipped a degraded report is no
longer logged as a failure.

Produce thorough, cited research reports from multiple sources. The base
workflow (understand to plan to search to deep-read to synthesize to deliver)
is unchanged; the **Research Harness (M-16)** below slots routing, caching,
source-confidence grading, a cited-report renderer, and a provider preflight
into that spine.

> This skill is vendored from the ECC `deep-research` skill and extended with
> the M-16 harness. The base ECC copy is left untouched.

## When to Activate

- User asks to research any topic in depth
- Competitive analysis, technology evaluation, or market sizing
- Due diligence on companies, investors, or technologies
- Any question requiring synthesis from multiple sources
- User says "research", "deep dive", "investigate", or "what's the current state of"

**Wrong lane?** `research-ops` is the thin router over this stack: it escalates *here* for
anything needing multiple sources, citations, or confidence grading, and routes elsewhere for a
single quick fact (the `exa` MCP) or research-before-*coding* (`search-first`). This skill is the
synthesis engine that router points at -- the full loop and output format live here, not there.

## MCP Requirements

At least one search provider. The harness routes across whichever of these are
live (see Preflight):

- **firecrawl** — `firecrawl_search`, `firecrawl_scrape`, `firecrawl_research_search_github` (primary web); `firecrawl_agent` (research agent, **metered**, on the `deep_research`/`council` fallback chains)
- **exa** (plugin `mcp__plugin_exa_exa__*`) — `web_search_exa`, `web_fetch_exa` (neural/semantic); `agent_create_run` (+ its `agent_wait_for_run` / `agent_get_run_output` companions; **metered**; supersedes the deprecated `deep_researcher_start`/`_check` pair, which is NOT routed)
- **tavily** — `tavily_search`, `tavily_extract` (web/news fallback); `tavily_research` (research agent, **metered**)
- **perplexity** (cookie/session-auth web MCP, `jacob-bd/perplexity-web-mcp`) — `pplx_smart_query`, `pplx_ask` (synthesized **cited** answers via the user's Pro/Max plan; drives the `synthesis` capability + high-priority web corroboration); `pplx_deep_research` (sync; async pair `pplx_deep_research_start` -> `pplx_research_status`) and `pplx_council` drive the `deep_research` / `council` capabilities (G-5b) and are **metered** — check `pplx_usage` first and spend them only in the budget's `explore` regime. Uses the `__Secure-next-auth.session-token` cookie supplied to the server as `PERPLEXITY_SESSION_TOKEN` — no paid API key. Gray-area/ToS-adjacent (like the IG/FB cookie MCPs); session can rate-limit/expire (~30d). Preflight routes around it when down or rate-limited and it is **never retried within a run** (`preflight.retry_allowed`, `NO_RETRY_SERVERS`); the fix is the owner action below, not a retry.
- **scholarly-access** — `paper_resolve`, `paper_fetch_metadata`, `paper_summarize` (OA academic)
- **tooluniverse** — `find_tools`, `execute_tool` (bio/pharma, 1264-tool library)
- **huggingface** — `paper_search` (ML/arXiv papers)
- **context7** — `resolve-library-id`, `query-docs` (library/API docs)
- **searxng** (key-free self-hosted metasearch, `mcp-searxng`, `SEARXNG_URL` env) — `searxng_web_search` (no API key, no quota; high-priority **key-free** web corroborator and the `longtail` primary). The SAME tool with `categories=science` is the keyless third `academic` lane (arxiv, crossref, google scholar, openalex, pubmed, semantic scholar — or spell it `engines="arxiv,google scholar,pubmed,semantic scholar,openalex,crossref"` on an instance that renamed the category). Several science engines **ignore `time_range`**; run `searxng_instance_info` to verify which engines the instance has enabled before trusting recency from this lane.
- **cve-mcp** (key-free local MCP, NVD/CIRCL/OSV/CISA-KEV/ExploitDB) — `nvd_get`, `nvd_search`, `kev_search` (the `vuln` capability for CVE/exploit/CVSS/KEV questions; exact cve-mcp@0.2.0 schema names)
- **search-hub** (the local hub; not in the routing table) — `read_url` (readability extraction) and `wayback_available` / `wayback_snapshots` (dead-link recovery) back the *snippet windows + Wayback fallback* borrow below.

**OWNER-ACTION (G-5b):** refresh `PERPLEXITY_SESSION_TOKEN` in `.agents/local.json` when
Perplexity probes down or rate-limited — the cookie expires ~30 days and a cloud agent cannot
refresh it. Until then every `synthesis` / `deep_research` / `council` sub-question is routed to
the next live provider on its chain (Exa/Firecrawl/Tavily research agents, then the
`academic` / `synthesis` / `web` fallback capabilities) and the Methodology section says so.

Parked (`~/.mcp.disabled.json`): `scrapegraph`, `apify` — the harness routes
around them. Never call `mcp__sci-hub__*`; avoid `paper_find_oa_pdf` per the
standing regression note. Both are hard-excluded by the router. No dark-web /
onion provider is routed to; any `.onion` source that reaches grading is
force-flagged UNVERIFIED regardless of corroboration.

OpenRouter is **not** a research search provider and must not replace Firecrawl,
Exa, or native Max. T0 summarization of sources **already fetched** by the
harness MAY use the `openrouter-routing` sidecar (allowlisted free/cheap chat
completion). `web` / `deep_read` stay on MCP providers. Do not use `:online`
(deprecated) or `openrouter:web_search` as a search MCP substitute.

## Workflow

### Step 1: Understand the Goal

Ask 1-2 quick clarifying questions:
- "What's your goal — learning, making a decision, or writing something?"
- "Any specific angle or depth you want?"

If the user says "just research it" — skip ahead with reasonable defaults.

### Step 2: Plan the Research

Break the topic into 3-5 research sub-questions. Example:
- Topic: "Impact of AI on healthcare"
  - What are the main AI applications in healthcare today?
  - What clinical outcomes have been measured?
  - What are the regulatory challenges?
  - What companies are leading this space?
  - What's the market size and growth trajectory?

Then order and size them (`harness.plan_research`, Lens 12 find 8): declare
`depends_on` for a sub-question that needs another answered first ("market size of
X" after "what is X") — the plan is executed in dependency order via `graphlib`, so
when a run is cut short the prerequisites are the parts that finished and the partial
report is coherent rather than random. Each sub-question gets an **effort class**
`fact` / `compare` / `deep` = **3 / 8 / 15** tool calls (heuristic, overridable per
index with `efforts=`); `plan.total_allotment` sizes the run `Budget(max_calls=...)`.
Open the run ledger now (`checkpoint.open_run`): if a ledger for this plan hash already
holds progress, pass its `completed` sub-questions as `completed_subquestions=` and the
plan skips them (`plan.skipped`).

### Step 2.5: Preflight (which providers are live)

Before dispatch, probe each routable provider once (a cheap tools-list or
minimal call) and mark it live / down / quota-exhausted. Route only to live
providers; record any that were down for the Methodology section. Preflight is
READ-ONLY and never disturbs the live GUI IDA MCP on `:13337`. See
`research_harness.preflight`.

**No-retry rule (G-5b):** a provider that probes `quota` is never retried in the run,
and `perplexity` (cookie/session-auth) is never retried once it is anything but live
(`retry_allowed(status)` is `False`): route around it via the capability's chain and
`CAPABILITY_FALLBACKS`, record it under "Providers down at preflight", and leave the
cookie refresh to the owner action above. Retrying only burns wall-clock and, on the
metered deep-research lanes, quota.

### Step 3: Execute Multi-Source Search (harness-routed)

For EACH sub-question, classify its capability and dispatch to the highest-ranked
live provider for that capability (see the Routing Table below). For high-stakes
sub-questions, query the **top-2** providers (different indexes) so the grader
can cross-corroborate. Wrap every provider call in the **query-hash cache** so an
identical sub-question across runs is a hit, not re-burned quota.

The loop carries four pieces of state, all stdlib and all on disk or in one object:

1. **Budget** (`budget.Budget`): prepend `budget.status_line()` to every loop turn
   (`Budget: 11/20 calls, 6 min left, regime=converge`). Regimes: `explore` (<60 %,
   metered tools allowed), `converge` (60-85 %, no metered tools, finish what is open),
   `finalize` (>85 %, "beast mode": no new searches, render NOW with
   `budget.terminal_status` = `partial:budget`, or `partial:timeout` when the wall clock
   is the binding axis).
2. **Run ledger** (`checkpoint`): append `record_tool_output` per provider call and
   `record_subquestion_done` (status `answered` / `open`) per sub-question, and
   `record_partial_report` after every synthesis round. It is append-only JSONL keyed by
   the plan hash and **fails closed** on a corrupt line (truncate to the last good record,
   append a `corruption` record, drop everything after). A killed run resumes at the next
   unanswered sub-question; most resumed calls are cache hits.
3. **Loop guard** (`loopguard.LoopGuard`): `observe(query)` before each search; a query
   with token-Jaccard >= 0.8 against a recent one is a repeat, and after `max_repeats`
   the guard trips — stop searching and render with `partial:loop`. `observe_results`
   also trips on two rounds with zero new URLs for the same sub-question.
4. **Compaction** (`compact`): keep the last **3** tool outputs raw in the working
   context; `compact_outputs` / `compact_ledger` replaces older ones with a deterministic
   digest (lead sentence, size, up to 3 URLs — no LLM call). Trigger it when
   `should_compact(...)` says the raw outputs exceed ~32k estimated tokens.

Metered tools (`pplx_deep_research`, `pplx_deep_research_start`, `pplx_council`,
`agent_create_run`, `firecrawl_agent`, `tavily_research`; `routing.is_metered`) are only
called in the `explore` regime and only after the quota protocol (`pplx_usage` /
`search_usage`) says there is quota to spend.

**Search strategy:**
- Use 2-3 different keyword variations per sub-question
- Aim for 15-30 unique sources total
- Prioritize per the source tiers (academic/official > reputable news > forums)

### Step 4: Deep-Read Key Sources

For the most promising URLs, fetch full content with the `deep_read` capability
(firecrawl `firecrawl_scrape` -> exa `web_fetch_exa` -> tavily `tavily_extract`).
Read 3-5 key sources in full; do not rely only on search snippets. Keep raw
payloads sandboxed to disk (the cache stores them); only the derived finding
enters the conversation.

### Step 4.5: Sufficiency gate + contradiction check (per sub-question)

Grade every source, then ask whether the sub-question has *enough*
(`sufficiency.gate`, Lens 12 find 6): **>= 2 sources graded >= B with >= 1 of them
corroborated** -> `write`. Otherwise run exactly **one** bounded, deterministic
follow-up query (`follow_up_query`: question lead stripped, entities quoted, a
"primary source" hint appended) and re-grade; still short -> `mark_open`, record the
sub-question `open` in the ledger, and the run's terminal state becomes
`partial:sources`. This turns "write anyway" into "one targeted retry, else declare
open" — RAG systems hallucinate more than they abstain when the retrieved set is thin.

Then run the claims through `conflicts.resolve_claims(claims, grades)` (find 9): when
two citations of one claim quote *different* values of the same kind (a number with
the same unit, two dates, two bare numbers) the claim's verdict becomes
`contradicted` — checked but not supported, and not an audit failure on its own — and
the report gets a **Disputed** callout listing every value with its citation and
provenance tag plus the grading-preferred one (tier first, then recency). Never
silently pick a number; show both.

### Step 5: Synthesize and Write Report (graded + cited)

Assemble the report with the cited-report renderer
(`research_harness.report.render`). The renderer **always emits a report**: a run that
hit its budget, its loop guard, or the sufficiency bar still ships everything it has,
with the terminal state in the header and the gaps named up front. Template:

```markdown
# [Topic]: Research Report
*Generated: [date] | Sources: [N] | Providers: [firecrawl, scholarly-access, ...] | Confidence: [High/Medium/Low]*
*Cache: [H hits / M misses] | Stale-allowed: [yes/no] | Status: [complete | partial:budget | ...]*

## Executive Summary
[3-5 sentence overview]

## Unanswered sub-questions        <- only when Status != complete
The run ended `partial:sources`; the following sub-questions were not answered ...
- [open sub-question]

## 1. [First Major Theme]
- Claim [1] `[A.corrob x2.2026]`
- Claim [2] `[C.single.2024 - UNVERIFIED]`

## Key Takeaways
- [Actionable insight]

## Disputed claims                 <- only when a claim is `contradicted`
> **Disputed:** [claim] - sources disagree: 500 wh/kg [1] `[A.corrob x2.2026]`; 400 wh/kg [2] `[C.single.2020 - UNVERIFIED]` (preferred: [1], by tier then recency).

## Sources
1. [Title](url) - tier A - provider (year)
2. ...

## Methodology
Sub-questions investigated, providers routed-to (and any fallback capability that
answered), cache hit/miss counts, providers that were DOWN at preflight, and the
terminal state.
```

The header `Confidence` is **derived** from the distribution of claim tiers, not
hand-waved. The Methodology section honestly lists routed providers, cache
hit/miss, and any provider down at preflight.

#### Terminal states

Every run ends in exactly one `Report.status` (`report.REPORT_STATUSES`):

| Status | Meaning | Set by |
|---|---|---|
| `complete` | every sub-question met the sufficiency bar | default; may not carry `open_subquestions` |
| `partial:budget` | the call/token budget reached `finalize` | `Budget.terminal_status` |
| `partial:timeout` | the wall clock was the binding budget axis | `Budget.terminal_status` |
| `partial:sources` | the sufficiency gate left >= 1 sub-question open | `GateDecision.status` |
| `partial:loop` | the loop guard tripped on repeated queries / no progress | `LoopGuard.status` |
| `failed` | nothing usable — still rendered, with every sub-question listed as open | the loop, on an unrecoverable error |

`partial:*` is **degraded success**, not failure: `summarize_statuses` counts it apart
from `failed` (`complete_rate` vs `delivered_rate`). When several signals fire, the
first one that stopped the loop wins; `seal(ledger, status)` closes the ledger with it.

### Step 6: Deliver

- **Short topics**: Post the full report in chat
- **Long reports**: Post the executive summary + key takeaways, save full report to a file

### Step 7: Persist to durable memory (basic-memory bridge)

Every cited report is a durable research artifact — write it to the
`basic-memory` MCP vault so it survives context compaction and is
semantically recallable later, instead of being re-researched from scratch.

After delivering, call `mcp__basic-memory__write_note` with:

- **title**: `research <topic> <YYYY-MM-DD>`
- **folder**: `research` (keeps the report findable via the same prefix)
- **tags**: `research-report`, the confidence tier, and the providers routed-to
- **content**: the full cited report (the `report.render` output) — the
  graded claims `[tier.corroboration.year]` and the `## Sources` list are the
  load-bearing part to preserve, so recall returns the evidence, not just prose.

This is a documentation convention, not harness code: the harness renders the
report; the agent is responsible for the `write_note` push. On a later related
question, **recall first** (`mcp__basic-memory__search_notes` /
`build_context` for `research <topic>`) before re-running the harness — a cache
hit at the memory layer beats any provider round-trip. Skip the write only if
`basic-memory` is unavailable or stalls (never block delivery on it).

## Research Harness (M-16)

A thin, stateless orchestration layer (no new MCP server, no daemon) shipped as a
Python package at `references/research_harness/`. Four components plus preflight,
and — since the Wave 2 reliability set — six small stdlib modules that give a run
state on disk, a budget, a terminal status, a loop guard, compaction, a sufficiency
gate and a `contradicted` verdict. Everything is pure Python, offline-testable, and
LLM-free (every "digest"/"follow-up"/"verdict" below is a deterministic function).

### 1. Capability to provider routing (`routing.py`)

A **data-driven** table maps a capability (not a tool name) to an ordered list of
providers (primary first), with a source-tier prior for grading. A provider is
`server.tool`, optionally with baked-in default params in parentheses
(`Provider.params` / `default_params`), which is how one tool serves two lanes:

| Capability | Ordered providers (primary first) |
|---|---|
| `web` | firecrawl.firecrawl_search -> perplexity.pplx_smart_query -> searxng.searxng_web_search -> exa.web_search_exa -> tavily.tavily_search |
| `synthesis` | perplexity.pplx_smart_query -> exa.web_search_exa -> firecrawl.firecrawl_search |
| `neural` | exa.web_search_exa -> firecrawl.firecrawl_search |
| `academic` | scholarly-access.paper_resolve -> huggingface.paper_search -> searxng.searxng_web_search(categories=science) |
| `bio` | tooluniverse.find_tools -> scholarly-access.paper_resolve |
| `code` | exa.web_search_exa -> firecrawl.firecrawl_research_search_github -> context7.query-docs |
| `library_docs` | context7.query-docs -> exa.web_search_exa |
| `deep_read` | firecrawl.firecrawl_scrape -> exa.web_fetch_exa -> tavily.tavily_extract |
| `vuln` | cve-mcp.nvd_get -> cve-mcp.nvd_search -> cve-mcp.kev_search |
| `longtail` | searxng.searxng_web_search -> exa.web_search_exa |
| `deep_research` | perplexity.pplx_deep_research -> exa.agent_create_run -> firecrawl.firecrawl_agent -> tavily.tavily_research |
| `council` | perplexity.pplx_council -> exa.agent_create_run -> firecrawl.firecrawl_agent |

**Capability fallbacks** (`CAPABILITY_FALLBACKS`, walked by `resolve_with_fallback`
when a capability's own chain has no live provider; the answering capability is
recorded on the decision as `fallback_capability` so the Methodology section can say
so): `deep_research` -> `academic` -> `web`; `council` -> `synthesis` -> `web`;
`vuln` -> `web`.

`classify_capability(subquestion)` is a cheap, conservative keyword classifier
(keywords like cve/cvss/exploit/kev/0-day/rce -> vuln; paper/study/doi -> academic;
gene/protein/drug -> bio; repo/github -> code; api docs/sdk -> library_docs;
council/multi-model/panel of models -> council; deep research/comprehensive report/
full landscape -> deep_research; obscure/long-tail/rarely-documented -> longtail;
explain/compare/consensus -> synthesis; else web). The security-specific `vuln` rule
runs first; domain rules win over the mode rules (`council`, `deep_research`) and over
synthesis phrasing (synthesis is the last rule), so "deep research on CVE-…" is still a
`vuln` question; raw link/extraction stays on firecrawl/exa while synthesized **cited**
answers route to Perplexity. The key-free additions: **searxng** (self-hosted
metasearch) is the high-priority key-free corroborator on `web`, the `longtail`
primary, and — with `categories=science` — the keyless third `academic` lane (Lens 14:
ENABLE, not build; see the caveats in MCP Requirements); **cve-mcp** drives `vuln`.
`resolve_providers(capability, live_servers, top_n)` returns ordered live providers;
Sci-Hub, the regressed `paper_find_oa_pdf`, and parked servers are hard-excluded.
`is_metered(provider)` flags the quota-spending tools (`METERED_TOOLS`); the async
companions of a routed tool are recorded in `ASYNC_COMPANIONS`, not routed.

### 2. Query-hash cache (`cache.py`)

SHA-256 of a normalized `{capability, provider, query, params}` envelope keys each
`{hash}.json` entry (a direct application of `content-hash-cache-pattern` with one
extension: **TTL**). Default cache dir `~/.research-harness/cache`. Per-capability
TTL: web/news ~24h, code/docs ~7d, academic/bio ~30d. Corruption or expiry == miss.
`fetch_with_cache(...)` is the service-layer wrapper; pass `cache_enabled=False`
(the `--no-cache` escape hatch) for "must be current" runs.

### 3. Source-confidence grading (`grading.py`)

`confidence(claim) = f(source_tier, corroboration_count, recency)`, fully
deterministic. Source tier = best of a domain-authority prior (.gov/.edu/doi.org
plus the security authorities nvd.nist.gov/cisa.gov/first.org/osv.dev/exploit-db.com
-> A; wikipedia/github/major-news -> B; else C) and the routing provider prior
(scholarly-access/context7/tooluniverse/**cve-mcp** -> A; firecrawl/exa/tavily/
huggingface/**searxng** -> B). A single source is flagged UNVERIFIED; >=2
independent sources are corroborated; within ~12 months boosts recency. A
dark-web / `.onion` source is **force-flagged UNVERIFIED and capped at Low**
regardless of corroboration (`is_dark_web`). Each source gets a provenance tag
like `[A.corrob x2.2026]`; the report header confidence is derived from the grade
distribution.

### 4. Cited-report output (`report.py`)

`render(Report(...))` assembles findings into markdown with inline **numbered**
citations (`[1]`), a tiered references section, per-claim provenance tags, and a
Methodology section reporting routed providers + cache hit/miss + providers down
at preflight. `Report.status` (the terminal state, validated against
`REPORT_STATUSES`) and `Report.open_subquestions` drive the "Unanswered sub-questions"
section; `Report.disputes` (pre-rendered `Dispute.callout` strings) drives "Disputed
claims". A `complete` report may not carry open sub-questions; the renderer never
refuses to render a partial one. `summarize_statuses([...])` tallies runs with
`partial:*` counted apart from `failed`.

Claim contracts live in `claims.py` (`SUPPORT_VERDICTS` now includes `contradicted`;
`audit_claims` treats it as checked-not-supported and not an issue) and
calibration vocab in `calibration.py`; `academic.py` holds the academic-lane helpers.

### Preflight + plan glue (`preflight.py`, `harness.py`)

`run_preflight(probe, servers)` probes each routable server (probe injected,
read-only) and returns live/down/quota statuses; `live_servers(...)` feeds the
router; `retry_allowed(status)` encodes the no-retry rule (`quota` never;
`NO_RETRY_SERVERS` = `perplexity` never once non-live). `plan_research(
subquestions, statuses, top_n, depends_on, efforts, completed_subquestions)` in
`harness.py` is the pure glue that ties preflight + routing + the sub-question DAG
into a research plan:
decisions come back in dependency order with their original `index`, `effort`,
`call_allotment` and any `fallback_capability`; `plan.total_allotment` sizes the budget.

### 5. Budget + regimes (`budget.py`)

`Budget(max_calls, max_seconds=None, max_tokens=None)` tracks three axes, derives
the **binding axis** (most consumed) and the regime — `explore` < 60 %, `converge`
60-85 %, `finalize` > 85 % — and exposes `allows_new_search`, `allows_metered`,
`can_afford(calls)` and `terminal_status` (`partial:budget`, or `partial:timeout` when
seconds bind). `spend(calls=, tokens=)` never raises on overspend (the loop may be
mid-call); `estimate_tokens(text)` is the ~4-chars/token heuristic; `EFFORT_CALLS` maps
`fact` / `compare` / `deep` -> 3 / 8 / 15. The clock is injected, so tests never sleep.

### 6. Run ledger + resume (`checkpoint.py`)

Append-only JSONL under `~/.research-harness/ledgers/`, one file per plan hash
(`plan_hash(subquestions, capabilities)`) and generation. Events: `plan`, `subq_done`
(`answered` / `open`), `tool_output`, `report_partial`, `sealed`, `corruption`.
`open_run(ledger_dir, subquestions)` finds or starts the active ledger and returns a
`ResumeState` (`pending`, `completed`, `open_subquestions`, `seed_report`); a sealed
ledger is never resumed (the next run gets a new generation file, so the audit trail is
kept). `load_ledger` **fails closed**: the first corrupt/torn line truncates the file to
the last good record, appends a `corruption` record, and drops every later line even
if well-formed. The query cache is per-query and TTL'd; the ledger is per-run and
ordered — distinct layers.

### 7. Loop guard + compaction (`loopguard.py`, `compact.py`)

`LoopGuard(max_repeats=2)` hashes each query and compares token-Jaccard against the
recent window (threshold 0.8); an exact or near repeat counts, and after `max_repeats`
the guard trips (`tripped`, `status` = `partial:loop`). `observe_results(index, urls)`
trips on `no_progress_rounds` consecutive rounds with zero new URLs for one
sub-question. `compact_outputs(outputs, keep_latest=3)` keeps the newest 3 tool outputs
raw and replaces the rest with a `Digest` (deterministic lead sentence + size + up to 3
URLs, never longer than the original); `compact_ledger` does the same over ledger
records; `should_compact` fires at ~32k estimated tokens.

### 8. Sufficiency gate + contradictions (`sufficiency.py`, `conflicts.py`)

`gate(subquestion, grades, attempts=, seen=)` -> `write` / `follow_up` (one bounded
reformulated query) / `mark_open` (`GateDecision.status` = `partial:sources`); the bar is
`judge_sufficiency`: >= 2 sources graded >= B and >= 1 corroborated. `resolve_claims(
claims, grades)` runs `detect_conflict` over each claim's evidence spans
(`extract_values` normalises numbers + units, percents, currencies and dates), marks
conflicting claims `contradicted`, and returns `Dispute` objects whose `callout` is the
"Disputed" blockquote for the report (both values, provenance, the tier-then-recency
preferred citation).

### Using the package

```python
import sys
sys.path.insert(0, "references")  # or install the package
from research_harness import (
    run_preflight, plan_research, fetch_with_cache, Budget, LoopGuard,
    open_run, record_subquestion_done, record_partial_report, seal,
    gate, resolve_claims, compact_outputs, should_compact,
    Source, grade_source, build_citations, Report, render,
)
from pathlib import Path

statuses = run_preflight(my_probe)                       # which MCPs are live
ledger, state = open_run(Path.home() / ".research-harness/ledgers", subquestions)
plan = plan_research(subquestions, statuses,             # DAG order + effort classes
                     completed_subquestions=state.completed)
budget = Budget(max_calls=plan.total_allotment, max_seconds=20 * 60)
guard = LoopGuard()
for decision in plan.decisions:                          # skip what the ledger answered
    if not budget.allows_new_search or guard.tripped:
        break                                            # beast mode / loop: render now
    # ... observe(query) on the guard, call live providers via fetch_with_cache(...),
    # ... record_tool_output(ledger.path, ...), grade each Source, then
    # ... gate(...) -> write / follow_up / mark_open; record_subquestion_done(ledger.path, ...)
    # ... record_partial_report(ledger.path, render(report_so_far))   # report-as-state
status = budget.terminal_status or guard.status or gate_status or "complete"
claims, disputes = resolve_claims(claims, grades_by_citation)
md = render(Report(..., status=status, open_subquestions=open_sqs,
                   disputes=tuple(d.callout for d in disputes)))
seal(ledger.path, status)
```

Run the tests: `cd references && python -m pytest -q` (pure logic, fake provider
responses, no live network).

## Technique borrows (prose, no code — Lens 3 order, Lens 12 items folded in)

Techniques lifted from the deep-research frameworks surveyed in the 2026-09-02 gem hunt
(Jina node-DeepResearch, Tongyi WebResearcher / TTD-DR, smolagents, local-deep-research,
LangChain Open Deep Research, STORM, dzhng/deep-research, MindSearch). Each is a rule
the agent applies in the loop above; where a harness function exists it is named, the
rest is discipline. Order is Lens 3's borrow order (highest lift on the measured 42 %
partial-run failure first).

### Budget + beast mode (Jina)

**When to use:** every run. Set `Budget(max_calls=plan.total_allotment, max_seconds=...)`
before the first search and print `status_line()` at the top of each loop turn. In
`explore` spend freely (metered tools allowed); in `converge` stop opening new
sub-questions and no metered tools; in `finalize` — "beast mode" — do **not** start
another search: answer from what the ledger holds, mark the rest open, render with
`partial:budget` / `partial:timeout`. A forced finish with gaps beats a run that dies
mid-fetch on sub-question 7 of 8 with nothing delivered.

### Evolving report (report-as-state; WebResearcher / TTD-DR)

**When to use:** any run longer than ~3 sub-questions, and always when resuming. Treat
the `Report` as the loop's state, not the transcript: each round receives
`render(report_so_far)` + this round's fused sources only; after the round append the
new `Theme` / `Claim` / `Citation` entries and `record_partial_report(...)` to the
ledger. Checkpointing and compaction fall out for free (the last `report_partial` seeds
a resume), and the context footprint stays bounded regardless of run length.

### Snippet windows + Wayback fallback (smolagents)

**When to use:** deep-reading a long page for one fact, and any 404 / paywall / dead
link. Do not pull whole pages into context: `deep_read` the URL into the cache, then
extract a **window** (the matching passage plus ~2 sentences either side) around the
query terms and cite that span. When the live fetch fails, ask the local hub for
`wayback_available` / `wayback_snapshots` and read the nearest-dated snapshot via
`read_url` — cite it with the snapshot date, graded as the original domain but flagged
"archived" in the claim text. Never substitute a search snippet for a read when a claim
is numeric or dated.

### Academic route (local-deep-research)

**When to use:** paper/study/DOI/preprint questions, and any claim that a primary source
should back. Route `academic`: keyed OA resolvers first, then the keyless SearXNG
science lane (`categories=science`). Fuse the lanes with the existing RRF rather than
picking one, prefer the DOI-resolved record when both return the same paper, and
remember the lane's two caveats: several science engines ignore `time_range`, and only
`searxng_instance_info` tells you which engines are actually enabled.

### Contracts (think / compression / hard-limit; LangChain ODR)

**When to use:** every tool call. Three loop contracts: **think** — before a search,
write one line of what is known, what is missing, and why this query closes the gap
(if it does not, skip the call); **compression** — after each sub-question, compress
its findings into the report (the evolving-report step) and let `compact_outputs`
digest the raw outputs; **hard limit** — the per-sub-question `call_allotment` (3 / 8 /
15) is a ceiling, not a target; when it is spent the sub-question goes through the
sufficiency gate as-is.

### Hedge filter before best-of-2 (Context Rot)

**When to use:** high-stakes sub-questions where the top-2 providers both returned a
candidate answer. Before aggregating, drop any candidate that hedges or gives up
("unable to determine", "could not find", "possibly", "it is unclear") or that carries
no `EvidenceSpan`; the survivors vote. If none survive, fall back to the unfiltered
pair and mark the sub-question `partial`. Give-up terminations correlate with wrong
answers; filtering them is the cheapest test-time compute that fits the budget.

### CoVe-style bounded re-check (Chain-of-Verification / ReClaim)

**When to use:** `fact` claims whose value is a number or date and whose grade is below
High, when the budget is still in `explore` or `converge`. Generate one independent
verification question that does not restate the draft ("What energy density did <source>
report for <cell>?"), answer it from a fresh retrieval (usually a cache hit), and compare
values with `extract_values`: match -> keep; mismatch -> `contradicted` with a Disputed
callout. At most N re-checks per run (`Budget.can_afford`); write cite-before-claim so
every sentence is grounded in the reference it names.

### Volatility axis on `ttl_for` (FreshLLMs)

**When to use:** when planning sub-questions, tag each as never- / slow- / fast-changing
(or false-premise). "Population of France" and "current CEO of X" must not share a TTL:
for fast-changing questions treat the cache TTL as hours and pass `cache_enabled=False`
if in doubt, order evidence recency-first, and stamp the claim "as of <date>"; for
never-changing ones a week-old cache hit is fine and a refetch is wasted budget. The
capability TTLs in `cache.TTL_BY_CAPABILITY` are the default, not the ceiling.

### Perspectives (STORM)

**When to use:** broad or contested topics ("state of X", "impact of Y") when planning
sub-questions. Before decomposing, list 3-4 perspectives that would ask different
questions about the topic (e.g. practitioner, regulator, sceptic, historian) and derive
at least one sub-question from each; then dedupe. This widens coverage beyond the
obvious first-page framing and surfaces the disagreements the `contradicted` verdict is
there to record.

### Learnings recursion (dzhng/deep-research)

**When to use:** after each sub-question round, when budget remains in `explore`. Write
2-3 one-line **learnings** (concrete, sourced facts) plus the follow-up questions they
raise; feed only the follow-ups that a `depends_on` chain or an open sub-question needs
back into the plan. Depth is bounded by the effort class, breadth by the budget; a
learning that raises no question that the report needs is recorded, not pursued.

### DAG order (MindSearch)

**When to use:** whenever one sub-question's answer shapes another's query. Declare
`depends_on` so `plan_research` executes prerequisites first (`graphlib`); a run cut
short by budget or loop guard then ships the foundations and lists the dependents as
open, rather than a random subset. Sub-questions with no dependency keep input order.

### Curation

**When to use:** before synthesis, on the fused source set. Curate rather than pile up:
dedupe by canonical URL (strip tracking params, unify `http`/`https` and `www`), cap
sources per host (2-3, so one site cannot manufacture "corroboration" with itself),
drop tier-C sources that no other source corroborates unless they are the only coverage
of an open sub-question (then keep them, flagged UNVERIFIED), and prefer the primary
record over an aggregator when both say the same thing. What survives is what the gate
grades and the report cites.

## Parallel Research with Subagents

For broad topics, use Claude Code's Task tool to parallelize:

```
Launch 3 research agents in parallel:
1. Agent 1: Research sub-questions 1-2
2. Agent 2: Research sub-questions 3-4
3. Agent 3: Research sub-question 5 + cross-cutting themes
```

Each agent searches, reads sources, and returns findings. The main session
synthesizes into the final report. Pass the routing table + grading rubric into
each agent's prompt so grades stay consistent.

## Quality Rules

1. **Every claim needs a source.** No unsourced assertions.
2. **Cross-reference.** If only one source says it, the grader flags it UNVERIFIED.
3. **Recency matters.** Prefer sources from the last 12 months; the grader boosts them.
4. **Acknowledge gaps.** The Methodology section lists providers that were down.
5. **No hallucination.** If you don't know, say "insufficient data found."
6. **Separate fact from inference.** Label estimates, projections, and opinions clearly.

## Examples

```
"Research the current state of nuclear fusion energy"
"Deep dive into Rust vs Go for backend services in 2026"
"Research the best strategies for bootstrapping a SaaS business"
"What's happening with the US housing market right now?"
"Investigate the competitive landscape for AI code editors"
```
